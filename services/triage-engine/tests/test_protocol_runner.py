from protocols_lib import load_protocol
from shared_types import Disposition, SeverityLevel, StructuredSymptomInput
from triage_engine.protocol_runner import run_protocol


def test_complete_mild_post_op_fever_case() -> None:
    protocol = load_protocol("post_op_fever_v1")
    symptom_input = StructuredSymptomInput(
        patient_id="p-2",
        protocol_id="post_op_fever_v1",
        chief_complaint="post op fever",
        symptom_summary="mild fever yesterday, feels better now",
        observed_signals=["low grade fever"],
        answers={
            "fever_temp_f": "100.4",
            "postop_day": "4",
            "wound_appearance": "clean and dry",
        },
    )

    result = run_protocol(protocol=protocol, symptom_input=symptom_input)
    assert result.ready_for_disposition is True
    assert result.severity_level == SeverityLevel.NORMAL
    assert result.disposition == Disposition.CLINIC_FOLLOWUP


def test_fever_and_wound_redness_urgent_case() -> None:
    protocol = load_protocol("post_op_fever_v1")
    symptom_input = StructuredSymptomInput(
        patient_id="p-3",
        protocol_id="post_op_fever_v1",
        chief_complaint="post op fever",
        symptom_summary="persistent fever and wound redness today",
        observed_signals=["wound redness", "persistent fever"],
        answers={
            "fever_temp_f": "102.2",
            "postop_day": "5",
            "wound_appearance": "redness around incision",
        },
    )

    result = run_protocol(protocol=protocol, symptom_input=symptom_input)
    assert result.ready_for_disposition is True
    assert result.severity_level == SeverityLevel.URGENT
    assert result.disposition == Disposition.URGENT_CARE
