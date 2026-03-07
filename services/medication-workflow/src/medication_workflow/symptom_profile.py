from __future__ import annotations

from shared_types import SideEffectCheckin, SymptomEscalationLevel, SymptomEscalationProfile


EMERGENCY_FLAGS = ["chest_pain", "breathlessness", "confusion", "near_fainting"]
URGENT_FLAGS = ["bleeding", "severe_weakness"]
FOLLOW_UP_FLAGS = ["dizziness", "swelling", "weakness", "nausea"]


def evaluate_symptom_escalation(checkin: SideEffectCheckin) -> SymptomEscalationProfile:
    triggered: list[str] = []
    for flag in EMERGENCY_FLAGS + URGENT_FLAGS + FOLLOW_UP_FLAGS:
        if getattr(checkin, flag, False):
            triggered.append(flag)

    if any(getattr(checkin, flag, False) for flag in EMERGENCY_FLAGS):
        return SymptomEscalationProfile(
            patient_id=checkin.patient_id,
            checkin_time=checkin.checkin_time,
            escalation_level=SymptomEscalationLevel.EMERGENCY_ESCALATION,
            triggered_flags=triggered,
            rationale="Emergency symptom indicators reported during check-in",
        )

    if any(getattr(checkin, flag, False) for flag in URGENT_FLAGS):
        return SymptomEscalationProfile(
            patient_id=checkin.patient_id,
            checkin_time=checkin.checkin_time,
            escalation_level=SymptomEscalationLevel.URGENT_SYMPTOM_TRIAGE_RECOMMENDED,
            triggered_flags=triggered,
            rationale="Urgent symptom indicators reported during check-in",
        )

    if any(getattr(checkin, flag, False) for flag in FOLLOW_UP_FLAGS):
        return SymptomEscalationProfile(
            patient_id=checkin.patient_id,
            checkin_time=checkin.checkin_time,
            escalation_level=SymptomEscalationLevel.CLINICIAN_REVIEW_RECOMMENDED,
            triggered_flags=triggered,
            rationale="Concerning symptoms reported; clinician review recommended",
        )

    if checkin.feeling.strip().lower() in {"okay", "fine", "good"}:
        return SymptomEscalationProfile(
            patient_id=checkin.patient_id,
            checkin_time=checkin.checkin_time,
            escalation_level=SymptomEscalationLevel.WATCH,
            triggered_flags=triggered,
            rationale="No high-risk symptom indicators",
        )

    return SymptomEscalationProfile(
        patient_id=checkin.patient_id,
        checkin_time=checkin.checkin_time,
        escalation_level=SymptomEscalationLevel.CAREGIVER_FOLLOW_UP,
        triggered_flags=triggered,
        rationale="General discomfort reported; caregiver follow-up advised",
    )
