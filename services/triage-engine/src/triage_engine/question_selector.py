from __future__ import annotations

from protocols_lib import ProtocolDefinition
from shared_types import StructuredSymptomInput, TriageQuestion


def select_next_required_question(
    protocol: ProtocolDefinition,
    symptom_input: StructuredSymptomInput,
) -> TriageQuestion | None:
    for question in protocol.required_questions:
        answer = symptom_input.answers.get(question.key, "")
        if question.required and not answer.strip():
            return question
    return None
