from __future__ import annotations

import os

from fastapi import FastAPI

from safety_engine.allowed_actions import allowed_actions_for_severity
from safety_engine.hard_stops import detect_hard_stops
from safety_engine.policy_trace import PolicyTraceCollector
from safety_engine.urgent_rules import detect_urgent_rules
from shared_types import (
    HealthResponse,
    SafetyResult,
    SeverityLevel,
    StructuredSymptomInput,
    configure_logging,
    get_logger,
)

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("safety_engine", layer="deterministic-safety-policy")

app = FastAPI(title="safety-engine")


def evaluate_safety(payload: StructuredSymptomInput) -> SafetyResult:
    text_corpus = " ".join(
        [
            payload.chief_complaint,
            payload.symptom_summary,
            " ".join(payload.observed_signals),
            " ".join(payload.answers.values()),
        ]
    )

    trace = PolicyTraceCollector()
    hard_stop_matches = detect_hard_stops(text_corpus=text_corpus, trace=trace)

    if hard_stop_matches:
        severity = SeverityLevel.EMERGENCY
        triggered_rules = hard_stop_matches
    else:
        urgent_matches = detect_urgent_rules(text_corpus=text_corpus, trace=trace)
        severity = SeverityLevel.URGENT if urgent_matches else SeverityLevel.NORMAL
        triggered_rules = urgent_matches

    allowed_actions = allowed_actions_for_severity(severity)
    return SafetyResult(
        patient_id=payload.patient_id,
        severity_level=severity,
        triggered_rules=triggered_rules,
        allowed_actions=allowed_actions,
        policy_trace=trace.entries(),
    )


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="safety-engine", status="ok")


@app.post("/safety/evaluate", response_model=SafetyResult)
def evaluate(payload: StructuredSymptomInput) -> SafetyResult:
    result = evaluate_safety(payload)
    logger.info(
        "safety_evaluated",
        patient_id=payload.patient_id,
        severity_level=result.severity_level,
        triggered_rules=result.triggered_rules,
    )
    return result
