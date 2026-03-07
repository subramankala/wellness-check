from __future__ import annotations

from uuid import uuid4

from medication_workflow.symptom_profile import evaluate_symptom_escalation
from shared_types import (
    AdherenceAlert,
    DailyMedicationLog,
    DoseStatus,
    MedicationCriticality,
    SideEffectCheckin,
    SymptomEscalationLevel,
)


def generate_alerts(log: DailyMedicationLog) -> tuple[list[AdherenceAlert], list]:
    alerts: list[AdherenceAlert] = []
    escalations = []

    confirmations_by_reminder: dict[str, list[DoseStatus]] = {}
    for confirmation in log.confirmations:
        confirmations_by_reminder.setdefault(confirmation.reminder_id, []).append(confirmation.dose_status)

    reminders_by_id = {item.reminder_id: item for item in log.reminders}

    for reminder in log.reminders:
        statuses = confirmations_by_reminder.get(reminder.reminder_id, [])
        latest_status = statuses[-1] if statuses else None

        if reminder.criticality_level is MedicationCriticality.CRITICAL and latest_status in {
            None,
            DoseStatus.SKIPPED,
            DoseStatus.UNSURE,
        }:
            if reminder.status == "overdue" or latest_status in {DoseStatus.SKIPPED, DoseStatus.UNSURE}:
                alerts.append(
                    AdherenceAlert(
                        alert_id=f"alert_{uuid4().hex}",
                        patient_id=log.patient_id,
                        date=log.date,
                        severity="high",
                        category="missed_critical_dose",
                        message=f"Critical medication missed or unconfirmed: {reminder.medication_name}",
                        caregiver_alert=True,
                        clinician_review_recommended=True,
                        urgent_symptom_triage_recommended=False,
                    )
                )

    missed_count = sum(
        1 for confirmation in log.confirmations if confirmation.dose_status in {DoseStatus.SKIPPED, DoseStatus.UNSURE}
    )
    if missed_count >= 2:
        alerts.append(
            AdherenceAlert(
                alert_id=f"alert_{uuid4().hex}",
                patient_id=log.patient_id,
                date=log.date,
                severity="medium",
                category="repeated_missed_doses",
                message="Multiple doses were missed or uncertain today",
                caregiver_alert=True,
                clinician_review_recommended=True,
                urgent_symptom_triage_recommended=False,
            )
        )

    for confirmation in log.confirmations:
        reminder = reminders_by_id.get(confirmation.reminder_id)
        if reminder is None:
            continue
        if (
            confirmation.dose_status is DoseStatus.TAKEN
            and confirmation.meal_condition_satisfied is False
            and reminder.criticality_level is MedicationCriticality.CRITICAL
        ):
            alerts.append(
                AdherenceAlert(
                    alert_id=f"alert_{uuid4().hex}",
                    patient_id=log.patient_id,
                    date=log.date,
                    severity="high",
                    category="meal_rule_violation_critical_med",
                    message="Critical medication taken without required meal rule",
                    caregiver_alert=True,
                    clinician_review_recommended=True,
                    urgent_symptom_triage_recommended=False,
                )
            )

    for checkin in log.side_effect_checkins:
        escalation = _classify_checkin(checkin)
        escalations.append(escalation)
        if escalation.escalation_level is SymptomEscalationLevel.CLINICIAN_REVIEW_RECOMMENDED:
            alerts.append(
                AdherenceAlert(
                    alert_id=f"alert_{uuid4().hex}",
                    patient_id=log.patient_id,
                    date=log.date,
                    severity="medium",
                    category="concerning_symptoms",
                    message="Concerning symptoms reported in side-effect check-in",
                    caregiver_alert=True,
                    clinician_review_recommended=True,
                    urgent_symptom_triage_recommended=False,
                )
            )
        elif escalation.escalation_level is SymptomEscalationLevel.URGENT_SYMPTOM_TRIAGE_RECOMMENDED:
            alerts.append(
                AdherenceAlert(
                    alert_id=f"alert_{uuid4().hex}",
                    patient_id=log.patient_id,
                    date=log.date,
                    severity="high",
                    category="urgent_symptoms",
                    message="Urgent symptoms reported in side-effect check-in",
                    caregiver_alert=True,
                    clinician_review_recommended=True,
                    urgent_symptom_triage_recommended=True,
                )
            )
        elif escalation.escalation_level is SymptomEscalationLevel.EMERGENCY_ESCALATION:
            alerts.append(
                AdherenceAlert(
                    alert_id=f"alert_{uuid4().hex}",
                    patient_id=log.patient_id,
                    date=log.date,
                    severity="critical",
                    category="emergency_symptoms",
                    message="Emergency symptoms reported in side-effect check-in",
                    caregiver_alert=True,
                    clinician_review_recommended=True,
                    urgent_symptom_triage_recommended=True,
                )
            )

    unique_keys: set[tuple[str, str]] = set()
    deduped: list[AdherenceAlert] = []
    for alert in alerts:
        key = (alert.category, alert.message)
        if key not in unique_keys:
            unique_keys.add(key)
            deduped.append(alert)
    return deduped, escalations


def _classify_checkin(checkin: SideEffectCheckin):
    return evaluate_symptom_escalation(checkin)
