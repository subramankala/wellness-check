from __future__ import annotations

import re

from shared_types import (
    ExtractionConfidence,
    ExtractionResult,
    ExtractedField,
    RuntimeSessionState,
    StructuredSymptomUpdate,
    TurnInputMode,
)
from voice_runtime_app.extractor.base import TurnExtractor


class DeterministicTurnExtractor(TurnExtractor):
    """Rule-based extractor for post_op_fever_v1 utterances.

    TODO(extraction): replace/augment with model-backed extraction while preserving this interface.
    """

    _TEMP_PATTERN = re.compile(r"\b(9[5-9](?:\.\d)?|10\d(?:\.\d)?|11\d(?:\.\d)?)\s*(?:f|fahrenheit)?\b")

    def extract(self, utterance: str, session_state: RuntimeSessionState) -> ExtractionResult:
        text = utterance.strip()
        lowered = text.lower()

        structured_update = StructuredSymptomUpdate()
        extracted_fields: list[ExtractedField] = []
        notes: list[str] = []

        if "fever" in lowered:
            structured_update.observed_signals.append("fever")
            extracted_fields.append(
                ExtractedField(
                    field_path="observed_signals",
                    value="fever",
                    confidence=ExtractionConfidence.HIGH,
                )
            )

        temp_match = self._TEMP_PATTERN.search(lowered)
        if temp_match is not None:
            temperature = temp_match.group(1)
            structured_update.answers["fever_temp_f"] = temperature
            extracted_fields.append(
                ExtractedField(
                    field_path="answers.fever_temp_f",
                    value=temperature,
                    confidence=ExtractionConfidence.HIGH,
                )
            )

        if "yesterday" in lowered:
            structured_update.answers["onset_hint"] = "since yesterday"
            extracted_fields.append(
                ExtractedField(
                    field_path="answers.onset_hint",
                    value="since yesterday",
                    confidence=ExtractionConfidence.MEDIUM,
                )
            )

        if "wound" in lowered and "red" in lowered:
            structured_update.observed_signals.append("wound redness")
            structured_update.answers["wound_appearance"] = "redness around incision"
            extracted_fields.append(
                ExtractedField(
                    field_path="observed_signals",
                    value="wound redness",
                    confidence=ExtractionConfidence.HIGH,
                )
            )
            extracted_fields.append(
                ExtractedField(
                    field_path="answers.wound_appearance",
                    value="redness around incision",
                    confidence=ExtractionConfidence.HIGH,
                )
            )

        if any(term in lowered for term in {"can\'t breathe", "cannot breathe", "shortness of breath"}):
            structured_update.observed_signals.append("severe shortness of breath")
            extracted_fields.append(
                ExtractedField(
                    field_path="observed_signals",
                    value="severe shortness of breath",
                    confidence=ExtractionConfidence.HIGH,
                )
            )

        if any(term in lowered for term in {"confused", "confusion", "disoriented"}):
            structured_update.observed_signals.append("confusion")
            extracted_fields.append(
                ExtractedField(
                    field_path="observed_signals",
                    value="confusion",
                    confidence=ExtractionConfidence.HIGH,
                )
            )

        if any(term in lowered for term in {"heavy bleeding", "bleeding heavily"}):
            structured_update.observed_signals.append("heavy bleeding")
            extracted_fields.append(
                ExtractedField(
                    field_path="observed_signals",
                    value="heavy bleeding",
                    confidence=ExtractionConfidence.HIGH,
                )
            )

        if any(term in lowered for term in {"vomiting", "throwing up"}):
            structured_update.observed_signals.append("uncontrolled vomiting")
            extracted_fields.append(
                ExtractedField(
                    field_path="observed_signals",
                    value="uncontrolled vomiting",
                    confidence=ExtractionConfidence.MEDIUM,
                )
            )

        existing_summary = session_state.symptom_input.symptom_summary.strip()
        if text and not existing_summary:
            structured_update.symptom_summary = text
            extracted_fields.append(
                ExtractedField(
                    field_path="symptom_summary",
                    value=text,
                    confidence=ExtractionConfidence.MEDIUM,
                )
            )
        elif text and existing_summary and text.lower() not in existing_summary.lower():
            structured_update.symptom_summary = f"{existing_summary}; {text}"
            notes.append("appended utterance to existing symptom_summary")

        unmatched_text = ""
        if not extracted_fields:
            unmatched_text = text
            notes.append("no structured fields extracted")

        return ExtractionResult(
            mode=TurnInputMode.UTTERANCE_TEXT,
            utterance_text=text,
            extracted_fields=extracted_fields,
            structured_update=structured_update,
            unmatched_text=unmatched_text,
            extraction_notes=notes,
        )
