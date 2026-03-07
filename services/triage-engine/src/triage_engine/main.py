from __future__ import annotations

import os

from fastapi import FastAPI

from shared_types import HealthResponse, StructuredSymptomInput, TriageResult, configure_logging, get_logger
from triage_engine.protocol_loader import load_protocol_for_request
from triage_engine.protocol_runner import run_protocol

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("triage_engine", layer="deterministic-safety-policy")

app = FastAPI(title="triage-engine")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="triage-engine", status="ok")


@app.post("/triage/evaluate", response_model=TriageResult)
def evaluate_triage(payload: StructuredSymptomInput) -> TriageResult:
    protocol = load_protocol_for_request(payload.protocol_id)
    result = run_protocol(protocol=protocol, symptom_input=payload)
    logger.info(
        "triage_evaluated",
        patient_id=payload.patient_id,
        protocol_id=payload.protocol_id,
        severity_level=result.severity_level,
        disposition=result.disposition,
        ready_for_disposition=result.ready_for_disposition,
    )
    return result
