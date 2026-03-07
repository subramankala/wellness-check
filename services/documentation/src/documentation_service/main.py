from __future__ import annotations

import os

from fastapi import FastAPI

from shared_types import (
    DocumentationCreateRequest,
    DocumentationPayload,
    HealthResponse,
    configure_logging,
    get_logger,
)

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("documentation_service", layer="operational-handoff")

app = FastAPI(title="documentation-service")


def create_documentation(payload: DocumentationCreateRequest) -> DocumentationPayload:
    disposition = payload.final_disposition.value if payload.final_disposition is not None else "pending"
    clinician_summary = (
        f"Post-op fever workflow evaluated. Safety={payload.safety_result.severity_level.value}; "
        f"TriageReady={payload.triage_result.ready_for_disposition}; FinalDisposition={disposition}."
    )
    patient_summary = (
        "Your symptoms were reviewed using a deterministic protocol. "
        f"Current recommendation: {disposition}."
    )
    structured_note = {
        "session_id": payload.session.session_id,
        "patient_id": payload.symptom_input.patient_id,
        "protocol_id": payload.session.protocol_id,
        "chief_complaint": payload.symptom_input.chief_complaint,
        "safety_severity": payload.safety_result.severity_level.value,
        "triage_rationale": payload.triage_result.rationale,
        "final_disposition": disposition,
        "triggered_safety_rules": payload.safety_result.triggered_rules,
        "missing_required_questions": payload.triage_result.missing_required_questions,
    }
    return DocumentationPayload(
        clinician_summary=clinician_summary,
        patient_summary=patient_summary,
        structured_note=structured_note,
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="documentation", status="ok")


@app.post("/documentation/create", response_model=DocumentationPayload)
def create(payload: DocumentationCreateRequest) -> DocumentationPayload:
    note = create_documentation(payload)
    logger.info(
        "documentation_created",
        patient_id=payload.symptom_input.patient_id,
        final_disposition=payload.final_disposition,
    )
    return note
