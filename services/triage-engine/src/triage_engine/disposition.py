from __future__ import annotations

from protocols_lib import ProtocolDefinition
from shared_types import Disposition, SeverityLevel


def resolve_disposition(
    protocol: ProtocolDefinition,
    text_corpus: str,
) -> tuple[SeverityLevel, Disposition, str]:
    lowered = text_corpus.lower()

    for hint in protocol.disposition_mapping_hints:
        if any(term.lower() in lowered for term in hint.when_any):
            return hint.severity_level, hint.disposition, hint.rationale

    if Disposition.CLINIC_FOLLOWUP in protocol.allowed_dispositions:
        return (
            SeverityLevel.NORMAL,
            Disposition.CLINIC_FOLLOWUP,
            "defaulted to clinic follow-up from allowed dispositions",
        )

    return (
        SeverityLevel.NORMAL,
        protocol.allowed_dispositions[0],
        "defaulted to first allowed disposition",
    )
