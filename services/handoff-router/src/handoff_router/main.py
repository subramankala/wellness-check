from __future__ import annotations

import os

from fastapi import FastAPI

from shared_types import (
    FinalDispositionDecision,
    HandoffCreateRequest,
    HandoffPayload,
    HealthResponse,
    configure_logging,
    get_logger,
)

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("handoff_router", layer="operational-handoff")

app = FastAPI(title="handoff-router")


def create_handoff(payload: HandoffCreateRequest) -> HandoffPayload:
    disposition = payload.final_disposition

    if disposition is FinalDispositionDecision.CALLBACK:
        return HandoffPayload(
            handoff_required=True,
            disposition=disposition,
            destination="callback_queue",
            priority="standard",
            reason="protocol selected callback follow-up",
            metadata={"session_id": payload.session.session_id},
        )

    if disposition is FinalDispositionDecision.URGENT_NURSE_HANDOFF:
        return HandoffPayload(
            handoff_required=True,
            disposition=disposition,
            destination="urgent_nurse_queue",
            priority="urgent",
            reason="urgent severity requires nurse handoff",
            metadata={"session_id": payload.session.session_id},
        )

    if disposition is FinalDispositionDecision.EMERGENCY_INSTRUCTION:
        return HandoffPayload(
            handoff_required=True,
            disposition=disposition,
            destination="emergency_dispatch",
            priority="emergency",
            reason="emergency severity requires immediate escalation",
            metadata={"session_id": payload.session.session_id},
        )

    return HandoffPayload(
        handoff_required=False,
        disposition=disposition,
        destination="none",
        priority="none",
        reason="self-care disposition does not require operational handoff",
        metadata={"session_id": payload.session.session_id},
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="handoff-router", status="ok")


@app.post("/handoff/create", response_model=HandoffPayload)
def create(payload: HandoffCreateRequest) -> HandoffPayload:
    handoff = create_handoff(payload)
    logger.info(
        "handoff_created",
        patient_id=payload.symptom_input.patient_id,
        disposition=payload.final_disposition,
        destination=handoff.destination,
    )
    return handoff
