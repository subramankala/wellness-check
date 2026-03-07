from __future__ import annotations

from shared_types import SafetyAction, SeverityLevel


def allowed_actions_for_severity(severity_level: SeverityLevel) -> list[SafetyAction]:
    if severity_level is SeverityLevel.EMERGENCY:
        return [SafetyAction.IMMEDIATE_EMERGENCY_ESCALATION]
    if severity_level is SeverityLevel.URGENT:
        return [
            SafetyAction.CONTINUE_PROTOCOL_QUESTIONS,
            SafetyAction.EXPEDITE_CLINICIAN_REVIEW,
        ]
    return [SafetyAction.CONTINUE_PROTOCOL_QUESTIONS]
