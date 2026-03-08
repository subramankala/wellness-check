from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from shared_types import (
    CareActivityConfirmationStatus,
    CareActivityInstance,
    DailyMedicationLog,
    MedicationPlan,
    MedicationReminder,
)


def parse_hhmm(value: str) -> tuple[int, int]:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"invalid scheduled_time '{value}', expected HH:MM")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"invalid scheduled_time '{value}', expected 00:00-23:59")
    return hour, minute


def ensure_daily_reminders(plan: MedicationPlan, log: DailyMedicationLog) -> DailyMedicationLog:
    existing_by_entry = {reminder.schedule_entry_id: reminder for reminder in log.reminders}
    patient_tz = ZoneInfo(plan.timezone)
    for entry in plan.medications:
        hour, minute = parse_hhmm(entry.scheduled_time)
        scheduled_local = datetime.fromisoformat(f"{log.date}T00:00:00").replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
            tzinfo=patient_tz,
        )
        scheduled_utc = scheduled_local.astimezone(UTC).isoformat()
        existing = existing_by_entry.get(entry.entry_id)
        if existing is not None:
            # Keep window state, but correct schedule fields to local wall-clock interpretation.
            existing.scheduled_datetime = scheduled_utc
            existing.local_scheduled_time = scheduled_local.isoformat()
            existing.meal_constraint = entry.meal_constraint
            existing.priority = entry.priority
            existing.criticality_level = entry.criticality_level
            continue
        log.reminders.append(
            MedicationReminder(
                reminder_id=f"rem_{plan.patient_id}_{log.date}_{entry.entry_id}",
                patient_id=plan.patient_id,
                plan_id=plan.plan_id,
                schedule_entry_id=entry.entry_id,
                medication_name=entry.medication_name,
                scheduled_datetime=scheduled_utc,
                meal_constraint=entry.meal_constraint,
                priority=entry.priority,
                criticality_level=entry.criticality_level,
                status="upcoming",
                local_scheduled_time=scheduled_local.isoformat(),
            )
        )
    log.reminders.sort(key=lambda item: item.scheduled_datetime)
    return log


def ensure_daily_care_activity_instances(plan: MedicationPlan, log: DailyMedicationLog) -> DailyMedicationLog:
    existing_by_activity = {instance.activity_id: instance for instance in log.care_activity_instances}
    patient_tz = ZoneInfo(plan.timezone)
    for activity in plan.care_activities:
        hour, minute = parse_hhmm(activity.schedule)
        scheduled_local = datetime.fromisoformat(f"{log.date}T00:00:00").replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
            tzinfo=patient_tz,
        )
        scheduled_utc = scheduled_local.astimezone(UTC).isoformat()
        existing = existing_by_activity.get(activity.activity_id)
        if existing is not None:
            # Preserve in-day caregiver adaptations (move/delay) for existing instances.
            existing.title = activity.title
            existing.category = activity.category
            existing.duration_minutes = activity.duration_minutes
            existing.instruction = activity.instruction
            existing.frequency = activity.frequency
            existing.priority = activity.priority
            existing.confirmation_required = activity.confirmation_required
            existing.escalation_policy = activity.escalation_policy
            continue
        log.care_activity_instances.append(
            CareActivityInstance(
                instance_id=f"care_{plan.patient_id}_{log.date}_{activity.activity_id}",
                patient_id=plan.patient_id,
                plan_id=plan.plan_id,
                activity_id=activity.activity_id,
                title=activity.title,
                category=activity.category,
                scheduled_datetime=scheduled_utc,
                local_scheduled_time=scheduled_local.isoformat(),
                duration_minutes=activity.duration_minutes,
                instruction=activity.instruction,
                frequency=activity.frequency,
                priority=activity.priority,
                confirmation_required=activity.confirmation_required,
                escalation_policy=activity.escalation_policy,
                status="upcoming",
            )
        )
    log.care_activity_instances.sort(key=lambda item: item.scheduled_datetime)
    return log


def classify_reminder_status(
    reminder: MedicationReminder,
    at: datetime,
    completion_reminder_ids: set[str],
) -> str:
    if reminder.reminder_id in completion_reminder_ids:
        return "completed"

    scheduled = datetime.fromisoformat(reminder.scheduled_datetime)
    if at < scheduled:
        return "upcoming"
    if at <= scheduled + timedelta(minutes=30):
        return "due"
    return "overdue"


def classify_care_activity_status(
    instance: CareActivityInstance,
    at: datetime,
    completed_instance_ids: set[str],
    skipped_instance_ids: set[str],
) -> str:
    if instance.instance_id in completed_instance_ids:
        return "completed"
    if instance.instance_id in skipped_instance_ids:
        return "skipped"

    scheduled = datetime.fromisoformat(instance.scheduled_datetime)
    if at < scheduled:
        return "upcoming"
    if at <= scheduled + timedelta(minutes=30):
        return "due"
    return "overdue"


def normalize_care_confirmation(incoming_text: str) -> CareActivityConfirmationStatus | None:
    text = incoming_text.strip().lower()
    if text in {"done", "completed", "complete"}:
        return CareActivityConfirmationStatus.DONE
    if text in {"delayed", "later"}:
        return CareActivityConfirmationStatus.DELAYED
    if text in {"skipped", "skip"}:
        return CareActivityConfirmationStatus.SKIPPED
    return None
