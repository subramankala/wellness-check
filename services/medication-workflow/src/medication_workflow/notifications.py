from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from shared_types import AdherenceAlert, AlertOutcome, CaregiverNotificationEvent


def notifications_from_alerts(patient_id: str, date: str, alerts: list[AdherenceAlert]) -> list[CaregiverNotificationEvent]:
    events: list[CaregiverNotificationEvent] = []
    now = datetime.now(UTC).isoformat()

    for alert in alerts:
        action: AlertOutcome | str = AlertOutcome.CAREGIVER_ALERT
        if alert.urgent_symptom_triage_recommended:
            action = AlertOutcome.URGENT_SYMPTOM_TRIAGE_RECOMMENDED
        elif alert.clinician_review_recommended:
            action = AlertOutcome.CLINICIAN_REVIEW_RECOMMENDED

        events.append(
            CaregiverNotificationEvent(
                event_id=f"notify_{uuid4().hex}",
                patient_id=patient_id,
                date=date,
                event_type=alert.category,
                severity=alert.severity,
                message=alert.message,
                action=action,
                created_at=now,
            )
        )
    return events
