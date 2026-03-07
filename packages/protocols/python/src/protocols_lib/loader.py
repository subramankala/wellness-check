from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, model_validator

from shared_types import Disposition, SeverityLevel, TriageQuestion


class ProtocolLoadError(ValueError):
    """Raised when a protocol file cannot be loaded or validated."""


class EligibilityCriterion(BaseModel):
    key: str
    description: str


class DispositionMappingHint(BaseModel):
    when_any: list[str] = Field(min_length=1)
    disposition: Disposition
    severity_level: SeverityLevel
    rationale: str


class ProtocolDefinition(BaseModel):
    protocol_id: str
    version: int
    chief_complaint: str
    eligibility_criteria: list[EligibilityCriterion] = Field(default_factory=list)
    required_questions: list[TriageQuestion] = Field(min_length=1)
    optional_follow_up_questions: list[TriageQuestion] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    allowed_dispositions: list[Disposition] = Field(min_length=1)
    disposition_mapping_hints: list[DispositionMappingHint] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_allowed_dispositions(self) -> "ProtocolDefinition":
        unique_count = len(set(self.allowed_dispositions))
        if unique_count != len(self.allowed_dispositions):
            raise ValueError("allowed_dispositions must not contain duplicates")
        for hint in self.disposition_mapping_hints:
            if hint.disposition not in self.allowed_dispositions:
                raise ValueError(
                    "disposition_mapping_hints contains a disposition not in allowed_dispositions"
                )
        return self


def _resolve_protocol_path(protocol_id: str) -> Path:
    filename = protocol_id if protocol_id.endswith(".yaml") else f"{protocol_id}.yaml"
    root = Path(__file__).resolve().parents[3]
    return root / "protocols" / filename


def load_protocol(protocol_id: str) -> ProtocolDefinition:
    path = _resolve_protocol_path(protocol_id)
    if not path.exists():
        raise ProtocolLoadError(f"protocol '{protocol_id}' not found at {path}")

    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ProtocolLoadError(f"invalid YAML for protocol '{protocol_id}': {exc}") from exc

    if not isinstance(payload, dict):
        raise ProtocolLoadError(
            f"protocol '{protocol_id}' must be a YAML mapping with required fields"
        )

    try:
        protocol = ProtocolDefinition.model_validate(payload)
    except ValidationError as exc:
        raise ProtocolLoadError(f"protocol '{protocol_id}' failed schema validation: {exc}") from exc

    if protocol.protocol_id != protocol_id.replace(".yaml", ""):
        raise ProtocolLoadError(
            f"protocol_id mismatch: file requested '{protocol_id}' but contains '{protocol.protocol_id}'"
        )

    return protocol
