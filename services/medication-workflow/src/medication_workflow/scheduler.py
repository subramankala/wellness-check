from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from shared_types import DailyMedicationLog, MedicationPlan, MedicationReminder


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
        if entry.entry_id in existing_by_entry:
            continue
        hour, minute = parse_hhmm(entry.scheduled_time)
        scheduled_local = datetime.fromisoformat(f"{log.date}T00:00:00").replace(
            hour=hour,
            minute=minute,
            second=0,
            microsecond=0,
            tzinfo=patient_tz,
        )
        log.reminders.append(
            MedicationReminder(
                reminder_id=f"rem_{plan.patient_id}_{log.date}_{entry.entry_id}",
                patient_id=plan.patient_id,
                plan_id=plan.plan_id,
                schedule_entry_id=entry.entry_id,
                medication_name=entry.medication_name,
                scheduled_datetime=scheduled_local.astimezone(UTC).isoformat(),
                meal_constraint=entry.meal_constraint,
                priority=entry.priority,
                criticality_level=entry.criticality_level,
                status="upcoming",
                local_scheduled_time=scheduled_local.isoformat(),
            )
        )
    log.reminders.sort(key=lambda item: item.scheduled_datetime)
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
