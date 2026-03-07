from protocols_lib import load_protocol
from shared_types import StructuredSymptomInput
from triage_engine.question_selector import select_next_required_question


def test_select_next_required_question() -> None:
    protocol = load_protocol("post_op_fever_v1")
    symptom_input = StructuredSymptomInput(
        patient_id="p-1",
        protocol_id="post_op_fever_v1",
        chief_complaint="post op fever",
        symptom_summary="mild fever",
        answers={"fever_temp_f": "100.5"},
    )

    next_question = select_next_required_question(protocol=protocol, symptom_input=symptom_input)
    assert next_question is not None
    assert next_question.key == "postop_day"
