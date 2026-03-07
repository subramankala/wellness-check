from __future__ import annotations

import os
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from shared_types import (
    AnsweredField,
    AuditEvent,
    Disposition,
    DispositionLock,
    DocumentationCreateRequest,
    ExtractionResult,
    FinalDispositionDecision,
    HealthResponse,
    HandoffCreateRequest,
    HumanOverrideRecord,
    HumanOverrideRequest,
    ReviewActionType,
    RuntimeEvaluationRequest,
    RuntimeEvaluationResponse,
    RuntimeSessionStartRequest,
    RuntimeSessionState,
    RuntimeSessionTurnRequest,
    SafetyResult,
    SessionBootstrap,
    SessionDetailView,
    SessionReviewStatus,
    SessionReviewStatusUpdateRequest,
    SessionStatus,
    SessionSummaryView,
    SeverityLevel,
    StructuredSymptomInput,
    StructuredSymptomUpdate,
    TurnInputMode,
    TriageResult,
    TurnProcessingResult,
    UserUtteranceInput,
    configure_logging,
    get_logger,
)
from voice_runtime_app.extractor.deterministic_extractor import DeterministicTurnExtractor
from voice_runtime_app.internal_clients import (
    DocumentationClient,
    HandoffRouterClient,
    SafetyEngineClient,
    TriageEngineClient,
)
from voice_runtime_app.session_store import InMemoryRuntimeSessionStore

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("voice_runtime", layer="realtime-conversation")

app = FastAPI(title="voice-runtime")

SUPPORTED_PROTOCOL_ID = "post_op_fever_v1"
EXTRACTION_HISTORY_LIMIT = 20
SESSION_STORE = InMemoryRuntimeSessionStore()
SAFETY_CLIENT = SafetyEngineClient()
TRIAGE_CLIENT = TriageEngineClient()
HANDOFF_CLIENT = HandoffRouterClient()
DOCUMENTATION_CLIENT = DocumentationClient()
EXTRACTOR = DeterministicTurnExtractor()


@app.on_event("startup")
def on_startup() -> None:
    logger.info("voice_runtime_started")
    # TODO(credentials): wire Twilio media stream ingress credentials and signature verification.
    # TODO(credentials): wire OpenAI Realtime API session bootstrap and auth.


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _append_audit_event(
    state: RuntimeSessionState,
    event_type: ReviewActionType,
    message: str,
    actor_id: str = "system",
    actor_name: str = "runtime",
    metadata: dict[str, str] | None = None,
) -> None:
    state.audit_events.append(
        AuditEvent(
            event_id=f"evt_{uuid4().hex}",
            event_type=event_type,
            timestamp=_now_iso(),
            actor_id=actor_id,
            actor_name=actor_name,
            message=message,
            metadata=metadata or {},
        )
    )


def _build_summary(state: RuntimeSessionState) -> SessionSummaryView:
    severity = state.latest_safety_result.severity_level if state.latest_safety_result else None
    return SessionSummaryView(
        session_id=state.session.session_id,
        protocol_id=state.session.protocol_id,
        session_status=state.status,
        review_status=state.review_status,
        latest_severity=severity,
        machine_recommended_disposition=state.machine_recommended_disposition,
        final_effective_disposition=state.final_effective_disposition,
        human_takeover=state.human_takeover,
    )


def _build_detail(state: RuntimeSessionState) -> SessionDetailView:
    return SessionDetailView(summary=_build_summary(state), session_state=state)


def _map_triage_to_final_disposition(triage_result: TriageResult) -> FinalDispositionDecision:
    if triage_result.disposition is Disposition.SELF_CARE:
        return FinalDispositionDecision.SELF_CARE
    if triage_result.disposition is Disposition.CLINIC_FOLLOWUP:
        return FinalDispositionDecision.CALLBACK
    if triage_result.disposition is Disposition.URGENT_CARE:
        return FinalDispositionDecision.URGENT_NURSE_HANDOFF
    return FinalDispositionDecision.EMERGENCY_INSTRUCTION


def _merge_decision(
    safety_result: SafetyResult,
    triage_result: TriageResult,
) -> FinalDispositionDecision | None:
    if not triage_result.ready_for_disposition:
        return None

    triage_decision = _map_triage_to_final_disposition(triage_result)

    if safety_result.severity_level is SeverityLevel.EMERGENCY:
        return FinalDispositionDecision.EMERGENCY_INSTRUCTION

    if safety_result.severity_level is SeverityLevel.URGENT and triage_decision in {
        FinalDispositionDecision.SELF_CARE,
        FinalDispositionDecision.CALLBACK,
    }:
        return FinalDispositionDecision.URGENT_NURSE_HANDOFF

    return triage_decision


def _seed_symptom_input(payload: RuntimeSessionStartRequest) -> StructuredSymptomInput:
    if payload.initial_symptom_input is not None:
        return payload.initial_symptom_input

    patient_id = payload.session.caller_id or payload.session.session_id
    return StructuredSymptomInput(
        patient_id=patient_id,
        protocol_id=payload.session.protocol_id,
        chief_complaint="post operative fever",
        symptom_summary="",
        observed_signals=[],
        answers={},
    )


def _sync_question_progress(state: RuntimeSessionState, turn_index: int) -> None:
    triage_result = state.latest_triage_result
    if triage_result is None:
        return

    state.question_progress.current_next_question = triage_result.next_required_question
    if triage_result.next_required_question is not None:
        key = triage_result.next_required_question.key
        if key not in state.question_progress.asked_questions:
            state.question_progress.asked_questions.append(key)

    answered_by_key = {field.key: field for field in state.question_progress.answered_questions}
    for key, value in state.symptom_input.answers.items():
        normalized = value.strip()
        if not normalized:
            continue
        if key in answered_by_key:
            answered_by_key[key].value = normalized
            answered_by_key[key].turn_index = turn_index
        else:
            state.question_progress.answered_questions.append(
                AnsweredField(key=key, value=normalized, turn_index=turn_index)
            )


def _merge_updates(
    extracted: StructuredSymptomUpdate | None,
    direct: StructuredSymptomUpdate | None,
) -> StructuredSymptomUpdate | None:
    if extracted is None and direct is None:
        return None

    merged = StructuredSymptomUpdate()
    for candidate in [extracted, direct]:
        if candidate is None:
            continue
        if candidate.patient_id and candidate.patient_id.strip():
            merged.patient_id = candidate.patient_id.strip()
        if candidate.chief_complaint and candidate.chief_complaint.strip():
            merged.chief_complaint = candidate.chief_complaint.strip()
        if candidate.symptom_summary and candidate.symptom_summary.strip():
            merged.symptom_summary = candidate.symptom_summary.strip()
        for signal in candidate.observed_signals:
            normalized = signal.strip()
            if normalized and normalized not in merged.observed_signals:
                merged.observed_signals.append(normalized)
        for key, value in candidate.answers.items():
            normalized = value.strip()
            if normalized:
                merged.answers[key] = normalized
    return merged


def _store_extraction_result(state: RuntimeSessionState, extraction_result: ExtractionResult) -> None:
    state.latest_extraction_result = extraction_result
    state.extraction_history.append(extraction_result)
    if len(state.extraction_history) > EXTRACTION_HISTORY_LIMIT:
        state.extraction_history = state.extraction_history[-EXTRACTION_HISTORY_LIMIT:]


def _create_or_update_artifacts(
    state: RuntimeSessionState,
    disposition: FinalDispositionDecision,
    triage_result: TriageResult,
    safety_result: SafetyResult,
) -> None:
    previous_handoff = state.handoff_versions[-1] if state.handoff_versions else None
    next_handoff_version = previous_handoff.version + 1 if previous_handoff else 1

    handoff = HANDOFF_CLIENT.create(
        HandoffCreateRequest(
            session=state.session,
            symptom_input=state.symptom_input,
            final_disposition=disposition,
            safety_result=safety_result,
            triage_result=triage_result,
        )
    )
    handoff.version = next_handoff_version
    handoff.supersedes_version = previous_handoff.version if previous_handoff else None
    state.handoff_payload = handoff
    state.handoff_versions.append(handoff)
    _append_audit_event(
        state,
        ReviewActionType.HANDOFF_CREATED,
        "handoff payload created",
        metadata={"version": str(handoff.version), "disposition": disposition.value},
    )

    previous_doc = state.documentation_versions[-1] if state.documentation_versions else None
    next_doc_version = previous_doc.version + 1 if previous_doc else 1

    documentation = DOCUMENTATION_CLIENT.create(
        DocumentationCreateRequest(
            session=state.session,
            symptom_input=state.symptom_input,
            final_disposition=disposition,
            safety_result=safety_result,
            triage_result=triage_result,
        )
    )
    documentation.version = next_doc_version
    documentation.supersedes_version = previous_doc.version if previous_doc else None
    state.documentation_payload = documentation
    state.documentation_versions.append(documentation)
    _append_audit_event(
        state,
        ReviewActionType.DOCUMENTATION_CREATED,
        "documentation payload created",
        metadata={"version": str(documentation.version), "disposition": disposition.value},
    )


def _evaluate_state(state: RuntimeSessionState, turn_index: int) -> TurnProcessingResult:
    safety_result = SAFETY_CLIENT.evaluate(state.symptom_input)
    state.latest_safety_result = safety_result
    _append_audit_event(
        state,
        ReviewActionType.SAFETY_EVALUATED,
        "safety evaluation completed",
        metadata={"severity": safety_result.severity_level.value},
    )

    triage_result = TRIAGE_CLIENT.evaluate(state.symptom_input)
    state.latest_triage_result = triage_result
    _append_audit_event(
        state,
        ReviewActionType.TRIAGE_EVALUATED,
        "triage evaluation completed",
        metadata={"ready": str(triage_result.ready_for_disposition)},
    )

    _sync_question_progress(state=state, turn_index=turn_index)

    final_disposition = _merge_decision(safety_result=safety_result, triage_result=triage_result)
    disposition_locked_this_turn = False

    if final_disposition is not None and state.disposition_lock is None:
        disposition_locked_this_turn = True
        state = SESSION_STORE.lock_disposition(
            state.session.session_id,
            DispositionLock(
                final_disposition=final_disposition,
                locked_turn_index=turn_index,
                lock_reason="triage complete with safety precedence",
            ),
        )
        state.machine_recommended_disposition = final_disposition
        if state.override_record is None:
            state.final_effective_disposition = final_disposition

        _append_audit_event(
            state,
            ReviewActionType.DISPOSITION_LOCKED,
            "machine disposition locked",
            metadata={"machine_disposition": final_disposition.value},
        )

        effective = state.final_effective_disposition or final_disposition
        _create_or_update_artifacts(
            state=state,
            disposition=effective,
            triage_result=triage_result,
            safety_result=safety_result,
        )

    SESSION_STORE.save_session(state)
    return TurnProcessingResult(
        session_state=state,
        final_disposition=state.final_effective_disposition,
        disposition_locked_this_turn=disposition_locked_this_turn,
        next_required_question=triage_result.next_required_question,
    )


def _get_session_or_404(session_id: str) -> RuntimeSessionState:
    state = SESSION_STORE.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="session not found")
    return state


def _empty_debug_state(protocol_id: str) -> RuntimeSessionState:
    return RuntimeSessionState(
        session=SessionBootstrap(
            request_id="extract_debug",
            session_id="extract_debug",
            channel="debug",
            protocol_id=protocol_id,
        ),
        status=SessionStatus.ACTIVE,
        symptom_input=StructuredSymptomInput(
            patient_id="debug",
            protocol_id=protocol_id,
            chief_complaint="post operative fever",
            symptom_summary="",
            observed_signals=[],
            answers={},
        ),
    )


def _disposition_rank(disposition: FinalDispositionDecision) -> int:
    ranks = {
        FinalDispositionDecision.SELF_CARE: 1,
        FinalDispositionDecision.CALLBACK: 2,
        FinalDispositionDecision.URGENT_NURSE_HANDOFF: 3,
        FinalDispositionDecision.EMERGENCY_INSTRUCTION: 4,
    }
    return ranks[disposition]


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="voice-runtime", status="ok")


@app.get("/runtime/sessions", response_model=list[SessionSummaryView])
def list_runtime_sessions() -> list[SessionSummaryView]:
    return [_build_summary(state) for state in SESSION_STORE.list_sessions()]


@app.get("/runtime/session/{session_id}/detail", response_model=SessionDetailView)
def get_runtime_session_detail(session_id: str) -> SessionDetailView:
    return _build_detail(_get_session_or_404(session_id))


@app.post("/runtime/extract", response_model=ExtractionResult)
def debug_extract(payload: UserUtteranceInput) -> ExtractionResult:
    protocol_id = payload.protocol_id or SUPPORTED_PROTOCOL_ID
    state = _empty_debug_state(protocol_id)
    if payload.session_id:
        existing = SESSION_STORE.get_session(payload.session_id)
        if existing is not None:
            state = existing
    result = EXTRACTOR.extract(payload.utterance_text, state)
    logger.info("runtime_extract", session_id=payload.session_id, extracted=len(result.extracted_fields))
    return result


@app.post("/runtime/evaluate", response_model=RuntimeEvaluationResponse)
def evaluate_runtime(payload: RuntimeEvaluationRequest) -> RuntimeEvaluationResponse:
    if payload.session.protocol_id != SUPPORTED_PROTOCOL_ID:
        raise HTTPException(status_code=400, detail="unsupported protocol_id")

    safety_result = SAFETY_CLIENT.evaluate(payload.symptom_input)
    triage_result = TRIAGE_CLIENT.evaluate(payload.symptom_input)
    final_disposition = _merge_decision(safety_result=safety_result, triage_result=triage_result)

    handoff_payload = None
    documentation_payload = None
    if final_disposition is not None:
        temp_state = RuntimeSessionState(
            session=payload.session,
            status=SessionStatus.COMPLETED,
            symptom_input=payload.symptom_input,
            latest_safety_result=safety_result,
            latest_triage_result=triage_result,
            machine_recommended_disposition=final_disposition,
            final_effective_disposition=final_disposition,
        )
        _create_or_update_artifacts(temp_state, final_disposition, triage_result, safety_result)
        handoff_payload = temp_state.handoff_payload
        documentation_payload = temp_state.documentation_payload

    response = RuntimeEvaluationResponse(
        session=payload.session,
        safety_result=safety_result,
        triage_result=triage_result,
        final_disposition=final_disposition,
        next_required_question=triage_result.next_required_question,
        handoff_payload=handoff_payload,
        documentation_payload=documentation_payload,
        notes=[],
    )

    logger.info(
        "runtime_evaluated",
        session_id=payload.session.session_id,
        severity_level=safety_result.severity_level,
        final_disposition=final_disposition,
        triage_ready=triage_result.ready_for_disposition,
    )
    return response


@app.post("/runtime/session/start", response_model=TurnProcessingResult)
def start_runtime_session(payload: RuntimeSessionStartRequest) -> TurnProcessingResult:
    if payload.session.protocol_id != SUPPORTED_PROTOCOL_ID:
        raise HTTPException(status_code=400, detail="unsupported protocol_id")

    symptom_input = _seed_symptom_input(payload)
    state = SESSION_STORE.create_session(payload.session, symptom_input)
    _append_audit_event(state, ReviewActionType.SESSION_STARTED, "session started")
    result = _evaluate_state(state=state, turn_index=0)
    logger.info("runtime_session_started", session_id=payload.session.session_id)
    return result


@app.post("/runtime/session/turn", response_model=TurnProcessingResult)
def process_runtime_turn(payload: RuntimeSessionTurnRequest) -> TurnProcessingResult:
    state = _get_session_or_404(payload.session_id)

    if state.status is SessionStatus.COMPLETED and state.disposition_lock is not None:
        SESSION_STORE.update_session(payload.session_id, payload.turn, None)
        frozen_state = _get_session_or_404(payload.session_id)
        return TurnProcessingResult(
            session_state=frozen_state,
            final_disposition=frozen_state.final_effective_disposition,
            disposition_locked_this_turn=False,
            next_required_question=frozen_state.question_progress.current_next_question,
        )

    has_structured = payload.symptom_update is not None
    has_utterance = payload.utterance_input is not None
    if not has_structured and not has_utterance:
        raise HTTPException(
            status_code=400,
            detail="turn requires symptom_update, utterance_input, or both",
        )

    extraction_result: ExtractionResult | None = None
    extracted_update: StructuredSymptomUpdate | None = None
    turn_mode = TurnInputMode.STRUCTURED_UPDATES

    if has_utterance and payload.utterance_input is not None:
        if (
            payload.utterance_input.protocol_id is not None
            and payload.utterance_input.protocol_id != state.session.protocol_id
        ):
            raise HTTPException(status_code=400, detail="utterance protocol_id does not match session")
        extraction_result = EXTRACTOR.extract(payload.utterance_input.utterance_text, state)
        extracted_update = extraction_result.structured_update
        turn_mode = TurnInputMode.UTTERANCE_TEXT

    if has_structured and has_utterance:
        turn_mode = TurnInputMode.MIXED

    if extraction_result is not None:
        extraction_result.mode = turn_mode
        _store_extraction_result(state, extraction_result)
        _append_audit_event(
            state,
            ReviewActionType.EXTRACTION_APPLIED,
            "utterance extracted into structured fields",
            metadata={"mode": turn_mode.value, "count": str(len(extraction_result.extracted_fields))},
        )

    merged_update = _merge_updates(extracted_update, payload.symptom_update)
    updated_state = SESSION_STORE.update_session(
        session_id=payload.session_id,
        incoming_turn=payload.turn,
        symptom_update=merged_update,
    )
    result = _evaluate_state(updated_state, turn_index=len(updated_state.turns))
    logger.info(
        "runtime_turn_processed",
        session_id=payload.session_id,
        turn_mode=turn_mode,
        disposition_locked_this_turn=result.disposition_locked_this_turn,
        final_disposition=result.final_disposition,
    )
    return result


@app.get("/runtime/session/{session_id}", response_model=RuntimeSessionState)
def get_runtime_session(session_id: str) -> RuntimeSessionState:
    return _get_session_or_404(session_id)


@app.post("/runtime/session/{session_id}/override", response_model=SessionDetailView)
def apply_human_override(session_id: str, payload: HumanOverrideRequest) -> SessionDetailView:
    state = _get_session_or_404(session_id)

    # TODO(authz): enforce role-based permission checks before allowing overrides.
    if not payload.reviewer_id.strip() or not payload.reviewer_name.strip() or not payload.rationale.strip():
        raise HTTPException(status_code=400, detail="reviewer identity and rationale are required")

    machine = state.machine_recommended_disposition
    if machine is None:
        raise HTTPException(status_code=409, detail="machine recommendation not locked yet")

    old_effective = state.final_effective_disposition or machine
    new_effective = payload.new_disposition
    delta = _disposition_rank(new_effective) - _disposition_rank(old_effective)
    acuity_change = "same"
    if delta > 0:
        acuity_change = "up"
    elif delta < 0:
        acuity_change = "down"

    record = HumanOverrideRecord(
        reviewer_id=payload.reviewer_id.strip(),
        reviewer_name=payload.reviewer_name.strip(),
        reviewed_at=_now_iso(),
        machine_recommended_disposition=machine,
        overridden_disposition=new_effective,
        override_rationale=payload.rationale.strip(),
        acuity_change=acuity_change,
        human_takeover=payload.human_takeover,
    )

    state.override_record = record
    state.final_effective_disposition = new_effective
    state.human_takeover = payload.human_takeover
    state.review_status = (
        SessionReviewStatus.HUMAN_TAKEOVER if payload.human_takeover else SessionReviewStatus.REVIEWED
    )

    _append_audit_event(
        state,
        ReviewActionType.HUMAN_OVERRIDE_APPLIED,
        "human override applied",
        actor_id=record.reviewer_id,
        actor_name=record.reviewer_name,
        metadata={
            "from": old_effective.value,
            "to": new_effective.value,
            "acuity_change": acuity_change,
        },
    )

    if state.disposition_lock is not None and state.latest_triage_result and state.latest_safety_result:
        _create_or_update_artifacts(
            state=state,
            disposition=new_effective,
            triage_result=state.latest_triage_result,
            safety_result=state.latest_safety_result,
        )

    SESSION_STORE.save_session(state)
    return _build_detail(state)


@app.post("/runtime/session/{session_id}/review-status", response_model=SessionDetailView)
def update_review_status(
    session_id: str,
    payload: SessionReviewStatusUpdateRequest,
) -> SessionDetailView:
    state = _get_session_or_404(session_id)

    if not payload.reviewer_id.strip() or not payload.reviewer_name.strip():
        raise HTTPException(status_code=400, detail="reviewer identity is required")

    state.review_status = payload.review_status
    if payload.review_status is SessionReviewStatus.HUMAN_TAKEOVER:
        state.human_takeover = True

    _append_audit_event(
        state,
        ReviewActionType.REVIEW_STATUS_UPDATED,
        "review status updated",
        actor_id=payload.reviewer_id.strip(),
        actor_name=payload.reviewer_name.strip(),
        metadata={"review_status": payload.review_status.value, "note": payload.note or ""},
    )
    SESSION_STORE.save_session(state)
    return _build_detail(state)


@app.post("/runtime/session/{session_id}/reset", response_model=TurnProcessingResult)
def reset_runtime_session(session_id: str) -> TurnProcessingResult:
    _get_session_or_404(session_id)
    reset_state = SESSION_STORE.reset_session(session_id)
    _append_audit_event(reset_state, ReviewActionType.SESSION_RESET, "session reset")
    result = _evaluate_state(state=reset_state, turn_index=0)
    logger.info("runtime_session_reset", session_id=session_id)
    return result


@app.websocket("/ws/conversation")
async def conversation_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    logger.info("conversation_connected")
    try:
        while True:
            message = await websocket.receive_text()
            logger.info("conversation_message", size=len(message))
            await websocket.send_text("ack")
    except WebSocketDisconnect:
        logger.info("conversation_disconnected")
