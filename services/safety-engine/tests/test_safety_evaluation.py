from safety_engine.allowed_actions import allowed_actions_for_severity
from safety_engine.main import evaluate_safety
from shared_types import SafetyAction, SeverityLevel, StructuredSymptomInput


def test_severe_shortness_of_breath_emergency_case() -> None:
    payload = StructuredSymptomInput(
        patient_id="p-4",
        protocol_id="post_op_fever_v1",
        chief_complaint="post op symptoms",
        symptom_summary="I have severe shortness of breath",
        observed_signals=[],
        answers={},
    )

    result = evaluate_safety(payload)
    assert result.severity_level == SeverityLevel.EMERGENCY
    assert "severe_shortness_of_breath" in result.triggered_rules


def test_confusion_emergency_case() -> None:
    payload = StructuredSymptomInput(
        patient_id="p-5",
        protocol_id="post_op_fever_v1",
        chief_complaint="post op symptoms",
        symptom_summary="new confusion and disoriented behavior",
        observed_signals=[],
        answers={},
    )

    result = evaluate_safety(payload)
    assert result.severity_level == SeverityLevel.EMERGENCY
    assert "confusion" in result.triggered_rules


def test_allowed_actions_restricted_for_emergency() -> None:
    actions = allowed_actions_for_severity(SeverityLevel.EMERGENCY)
    assert actions == [SafetyAction.IMMEDIATE_EMERGENCY_ESCALATION]
