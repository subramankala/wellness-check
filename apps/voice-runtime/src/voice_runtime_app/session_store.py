from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock

from shared_types import (
    ConversationTurn,
    DispositionLock,
    RuntimeSessionState,
    SessionReviewStatus,
    SessionBootstrap,
    SessionStatus,
    StructuredSymptomInput,
    StructuredSymptomUpdate,
)


class RuntimeSessionStore(ABC):
    @abstractmethod
    def create_session(
        self,
        session_bootstrap: SessionBootstrap,
        symptom_input: StructuredSymptomInput,
    ) -> RuntimeSessionState:
        raise NotImplementedError

    @abstractmethod
    def get_session(self, session_id: str) -> RuntimeSessionState | None:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self) -> list[RuntimeSessionState]:
        raise NotImplementedError

    @abstractmethod
    def update_session(
        self,
        session_id: str,
        incoming_turn: ConversationTurn,
        symptom_update: StructuredSymptomUpdate | None,
    ) -> RuntimeSessionState:
        raise NotImplementedError

    @abstractmethod
    def lock_disposition(
        self,
        session_id: str,
        lock: DispositionLock,
    ) -> RuntimeSessionState:
        raise NotImplementedError

    @abstractmethod
    def save_session(self, state: RuntimeSessionState) -> None:
        raise NotImplementedError

    @abstractmethod
    def reset_session(self, session_id: str) -> RuntimeSessionState:
        raise NotImplementedError


def _non_empty(value: str | None) -> bool:
    return value is not None and value.strip() != ""


class InMemoryRuntimeSessionStore(RuntimeSessionStore):
    def __init__(self) -> None:
        self._sessions: dict[str, RuntimeSessionState] = {}
        self._lock = Lock()

    def create_session(
        self,
        session_bootstrap: SessionBootstrap,
        symptom_input: StructuredSymptomInput,
    ) -> RuntimeSessionState:
        state = RuntimeSessionState(
            session=session_bootstrap,
            status=SessionStatus.ACTIVE,
            symptom_input=symptom_input,
        )
        with self._lock:
            self._sessions[session_bootstrap.session_id] = state
        return state

    def get_session(self, session_id: str) -> RuntimeSessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def list_sessions(self) -> list[RuntimeSessionState]:
        with self._lock:
            return list(self._sessions.values())

    def update_session(
        self,
        session_id: str,
        incoming_turn: ConversationTurn,
        symptom_update: StructuredSymptomUpdate | None,
    ) -> RuntimeSessionState:
        with self._lock:
            state = self._sessions[session_id]
            state.turns.append(incoming_turn)
            if symptom_update is None:
                return state

            if _non_empty(symptom_update.patient_id):
                state.symptom_input.patient_id = symptom_update.patient_id.strip()

            if _non_empty(symptom_update.chief_complaint):
                state.symptom_input.chief_complaint = symptom_update.chief_complaint.strip()

            if _non_empty(symptom_update.symptom_summary):
                state.symptom_input.symptom_summary = symptom_update.symptom_summary.strip()

            for signal in symptom_update.observed_signals:
                normalized = signal.strip()
                if normalized and normalized not in state.symptom_input.observed_signals:
                    state.symptom_input.observed_signals.append(normalized)

            for key, value in symptom_update.answers.items():
                normalized = value.strip()
                if normalized:
                    state.symptom_input.answers[key] = normalized

            return state

    def lock_disposition(
        self,
        session_id: str,
        lock: DispositionLock,
    ) -> RuntimeSessionState:
        with self._lock:
            state = self._sessions[session_id]
            state.disposition_lock = lock
            state.status = SessionStatus.COMPLETED
            return state

    def save_session(self, state: RuntimeSessionState) -> None:
        with self._lock:
            self._sessions[state.session.session_id] = state

    def reset_session(self, session_id: str) -> RuntimeSessionState:
        with self._lock:
            state = self._sessions[session_id]
            state.status = SessionStatus.ACTIVE
            state.turns = []
            state.symptom_input.symptom_summary = ""
            state.symptom_input.observed_signals = []
            state.symptom_input.answers = {}
            state.question_progress.asked_questions = []
            state.question_progress.answered_questions = []
            state.question_progress.current_next_question = None
            state.latest_safety_result = None
            state.latest_triage_result = None
            state.latest_extraction_result = None
            state.extraction_history = []
            state.disposition_lock = None
            state.machine_recommended_disposition = None
            state.final_effective_disposition = None
            state.review_status = SessionReviewStatus.PENDING_REVIEW
            state.override_record = None
            state.human_takeover = False
            state.handoff_payload = None
            state.documentation_payload = None
            state.handoff_versions = []
            state.documentation_versions = []
            return state
