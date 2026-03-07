from __future__ import annotations

from documentation_service.main import create_documentation
from handoff_router.main import create_handoff
from safety_engine.main import evaluate_safety
from shared_types import (
    DocumentationCreateRequest,
    DocumentationPayload,
    HandoffCreateRequest,
    HandoffPayload,
    SafetyResult,
    StructuredSymptomInput,
    TriageResult,
)
from triage_engine.protocol_loader import load_protocol_for_request
from triage_engine.protocol_runner import run_protocol


class SafetyEngineClient:
    def evaluate(self, payload: StructuredSymptomInput) -> SafetyResult:
        return evaluate_safety(payload)


class TriageEngineClient:
    def evaluate(self, payload: StructuredSymptomInput) -> TriageResult:
        protocol = load_protocol_for_request(payload.protocol_id)
        return run_protocol(protocol=protocol, symptom_input=payload)


class HandoffRouterClient:
    def create(self, payload: HandoffCreateRequest) -> HandoffPayload:
        return create_handoff(payload)


class DocumentationClient:
    def create(self, payload: DocumentationCreateRequest) -> DocumentationPayload:
        return create_documentation(payload)
