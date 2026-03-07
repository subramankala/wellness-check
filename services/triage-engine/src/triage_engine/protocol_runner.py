from __future__ import annotations

from protocols_lib import ProtocolDefinition
from shared_types import Disposition, SeverityLevel, StructuredSymptomInput, TriageResult

from triage_engine.disposition import resolve_disposition
from triage_engine.question_selector import select_next_required_question


def run_protocol(protocol: ProtocolDefinition, symptom_input: StructuredSymptomInput) -> TriageResult:
    text_corpus = " ".join(
        [
            symptom_input.chief_complaint,
            symptom_input.symptom_summary,
            " ".join(symptom_input.observed_signals),
            " ".join(symptom_input.answers.values()),
        ]
    )
    lowered = text_corpus.lower()
    matched_red_flags = [flag for flag in protocol.red_flags if flag.lower() in lowered]

    next_required = select_next_required_question(protocol=protocol, symptom_input=symptom_input)
    missing_required = []
    if next_required is not None:
        missing_required = [
            question.key
            for question in protocol.required_questions
            if not symptom_input.answers.get(question.key, "").strip()
        ]

    if matched_red_flags:
        emergency_disposition = (
            Disposition.CALL_911
            if Disposition.CALL_911 in protocol.allowed_dispositions
            else Disposition.EMERGENCY_DEPARTMENT
        )
        return TriageResult(
            patient_id=symptom_input.patient_id,
            protocol_id=protocol.protocol_id,
            severity_level=SeverityLevel.EMERGENCY,
            disposition=emergency_disposition,
            next_required_question=next_required,
            missing_required_questions=missing_required,
            triggered_red_flags=matched_red_flags,
            ready_for_disposition=True,
            rationale="red flags detected; emergency disposition selected",
        )

    if next_required is not None:
        return TriageResult(
            patient_id=symptom_input.patient_id,
            protocol_id=protocol.protocol_id,
            severity_level=SeverityLevel.NORMAL,
            disposition=None,
            next_required_question=next_required,
            missing_required_questions=missing_required,
            triggered_red_flags=[],
            ready_for_disposition=False,
            rationale="required triage questions remain unanswered",
        )

    severity, disposition, rationale = resolve_disposition(protocol=protocol, text_corpus=text_corpus)
    return TriageResult(
        patient_id=symptom_input.patient_id,
        protocol_id=protocol.protocol_id,
        severity_level=severity,
        disposition=disposition,
        next_required_question=None,
        missing_required_questions=[],
        triggered_red_flags=[],
        ready_for_disposition=True,
        rationale=rationale,
    )
