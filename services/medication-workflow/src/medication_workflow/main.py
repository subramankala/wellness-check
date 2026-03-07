from __future__ import annotations

import os
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query, Request, Response

from medication_workflow.alerts import generate_alerts
from medication_workflow.notifications import notifications_from_alerts
from medication_workflow.scheduler import classify_reminder_status, ensure_daily_reminders, parse_hhmm
from medication_workflow.store import MedicationWorkflowStore
from medication_workflow.transport import (
    MessageTransport,
    MockMessageTransport,
    OutboundMessageRequest,
    WhatsAppMessageTransport,
)
from shared_types import (
    AdherenceAlert,
    AdministrationWindow,
    AdvanceSimulatedTimeRequest,
    ChannelType,
    CaregiverActionRecommendation,
    CaregiverNotificationEvent,
    CaregiverSummary,
    DeliveryStatus,
    DailyMedicationExportResponse,
    DailyMedicationLog,
    DaySimulationReport,
    DoseConfirmation,
    DoseConfirmationRequest,
    DoseStatus,
    DueNowResponse,
    HealthResponse,
    MedicationMessageRecord,
    MedicationCriticality,
    MedicationDashboardView,
    MedicationPlan,
    MedicationPlanExportResponse,
    MedicationPlanImportRequest,
    MedicationReminder,
    MedicationTimelineItem,
    MedicationTimelineResponse,
    MedicationTodayView,
    MessageConfirmationRequest,
    MessageKind,
    PatientRecord,
    RecipientRole,
    ReviewActionType,
    SendDueRemindersResponse,
    SendOverdueFollowupsResponse,
    SetSimulatedTimeRequest,
    SideEffectCheckin,
    SideEffectCheckinRequest,
    SimulatedTimeState,
    UpdateMedicationScheduleEntryRequest,
    configure_logging,
    get_logger,
)

try:
    from twilio.request_validator import RequestValidator
except Exception:  # pragma: no cover - optional import path
    RequestValidator = None  # type: ignore[assignment]

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("medication_workflow", layer="operational-handoff")

app = FastAPI(title="medication-workflow")
STORE = MedicationWorkflowStore()


def _build_transport() -> MessageTransport:
    provider = os.getenv("MEDICATION_TRANSPORT_PROVIDER", "mock").lower()
    if provider == "twilio":
        return WhatsAppMessageTransport.from_env()
    return MockMessageTransport()


MESSAGE_TRANSPORT = _build_transport()


def _transport_channel_type() -> ChannelType:
    return ChannelType.WHATSAPP if isinstance(MESSAGE_TRANSPORT, WhatsAppMessageTransport) else ChannelType.MOCK_TEXT


def _patient_timezone(patient: PatientRecord, plan: MedicationPlan) -> str:
    return patient.timezone or plan.timezone or "UTC"


def _zoneinfo(timezone_name: str) -> ZoneInfo:
    return ZoneInfo(timezone_name)


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _localize_iso(utc_iso: str, tz: ZoneInfo) -> str:
    return datetime.fromisoformat(utc_iso).astimezone(tz).isoformat()


def _local_day_from_utc(at_utc: datetime, tz: ZoneInfo) -> str:
    return at_utc.astimezone(tz).date().isoformat()


def _parse_query_datetime(at: str | None, tz: ZoneInfo) -> datetime:
    if at is None:
        return STORE.now()
    parsed = datetime.fromisoformat(at)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=tz)
    return parsed.astimezone(UTC)


def _localize_reminder(reminder: MedicationReminder, tz: ZoneInfo) -> MedicationReminder:
    return reminder.model_copy(update={"local_scheduled_time": _localize_iso(reminder.scheduled_datetime, tz)})


def _localize_reminders(reminders: list[MedicationReminder], tz: ZoneInfo) -> list[MedicationReminder]:
    return [_localize_reminder(item, tz) for item in reminders]


def _is_morning_slot(slot_time: str) -> bool:
    hour = int(slot_time.split(":")[0])
    return 6 <= hour <= 10


def _recipient_address(patient: PatientRecord, recipient_role: RecipientRole) -> str:
    if recipient_role is RecipientRole.PATIENT:
        if patient.patient_contact.strip():
            return patient.patient_contact
        return patient.caregiver_contact
    return patient.caregiver_contact


def _twilio_signature_enabled() -> bool:
    return os.getenv("TWILIO_VALIDATE_SIGNATURES", "true").lower() == "true"


def _public_webhook_url(request: Request) -> str:
    configured_base = os.getenv("TWILIO_PUBLIC_WEBHOOK_BASE_URL", "").strip().rstrip("/")
    if configured_base:
        query = f"?{request.url.query}" if request.url.query else ""
        return f"{configured_base}{request.url.path}{query}"
    return str(request.url)


def _validate_twilio_request_signature(request: Request, form_data: dict[str, str]) -> bool:
    if not _twilio_signature_enabled():
        return True
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        return False
    if RequestValidator is None:
        return False
    signature = request.headers.get("X-Twilio-Signature", "")
    validator = RequestValidator(auth_token)
    return bool(validator.validate(_public_webhook_url(request), form_data, signature))


def _pilot_mode_enabled() -> bool:
    return os.getenv("MEDICATION_PILOT_MODE", "false").lower() == "true"


def _csv_set(name: str) -> set[str]:
    raw = os.getenv(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _pilot_allowed_patient(patient_id: str) -> bool:
    allowed = _csv_set("MEDICATION_PILOT_ALLOWED_PATIENT_IDS")
    return not allowed or patient_id in allowed


def _normalize_phone(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("whatsapp:"):
        normalized = normalized[len("whatsapp:") :]
    return normalized


def _pilot_allowed_number(number: str) -> bool:
    allowed = {_normalize_phone(item) for item in _csv_set("MEDICATION_PILOT_ALLOWED_NUMBERS")}
    return not allowed or _normalize_phone(number) in allowed


def _pilot_allowed_channel(channel_type: ChannelType) -> bool:
    allowed = _csv_set("MEDICATION_PILOT_ALLOWED_CHANNELS")
    return not allowed or channel_type.value in allowed


def _pilot_max_sends_per_day() -> int:
    return int(os.getenv("MEDICATION_PILOT_MAX_SENDS_PER_DAY", "100"))


def _enforce_pilot_send_guard(
    *,
    patient: PatientRecord,
    log: DailyMedicationLog,
    day: str,
    recipient_address: str,
    channel_type: ChannelType,
) -> None:
    if not _pilot_mode_enabled():
        return
    if not _pilot_allowed_patient(patient.patient_id):
        raise HTTPException(status_code=403, detail="pilot mode: patient not allowed")
    if not _pilot_allowed_number(recipient_address):
        raise HTTPException(status_code=403, detail="pilot mode: recipient number not allowed")
    if not _pilot_allowed_channel(channel_type):
        raise HTTPException(status_code=403, detail="pilot mode: channel not allowed")
    sends_today = sum(1 for message in log.messages if message.date == day)
    if sends_today >= _pilot_max_sends_per_day():
        raise HTTPException(status_code=429, detail="pilot mode: max sends per day reached")


def _today_date_string() -> str:
    return STORE.now().date().isoformat()


def _refresh_day_state(plan: MedicationPlan, log: DailyMedicationLog, at: datetime) -> DailyMedicationLog:
    ensure_daily_reminders(plan, log)

    completion_ids = {
        confirmation.reminder_id
        for confirmation in log.confirmations
        if confirmation.dose_status in {DoseStatus.TAKEN, DoseStatus.DELAYED}
    }

    for reminder in log.reminders:
        reminder.status = classify_reminder_status(reminder, at=at, completion_reminder_ids=completion_ids)

    alerts, escalations = generate_alerts(log)
    log.alerts = alerts
    log.symptom_escalations = escalations
    log.notifications = notifications_from_alerts(log.patient_id, log.date, alerts)
    return log


def _find_reminder(log: DailyMedicationLog, schedule_entry_id: str, scheduled_datetime: str) -> MedicationReminder | None:
    for reminder in log.reminders:
        if (
            reminder.schedule_entry_id == schedule_entry_id
            and reminder.scheduled_datetime == scheduled_datetime
        ):
            return reminder
    return None


def _get_plan_or_404(patient_id: str) -> MedicationPlan:
    plan = STORE.get_plan(patient_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="medication plan not found")
    return plan


def _get_patient_or_404(patient_id: str) -> PatientRecord:
    patient = STORE.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="patient not found")
    return patient


def _assert_patient_and_plan(patient_id: str) -> tuple[PatientRecord, MedicationPlan]:
    return _get_patient_or_404(patient_id), _get_plan_or_404(patient_id)


def _validate_plan_entries(plan: MedicationPlan) -> None:
    entry_ids: set[str] = set()
    medication_time_keys: set[tuple[str, str]] = set()

    valid_priority = {"routine", "important", "critical"}

    for entry in plan.medications:
        parse_hhmm(entry.scheduled_time)

        if entry.entry_id in entry_ids:
            raise HTTPException(status_code=400, detail=f"duplicate entry_id '{entry.entry_id}'")
        entry_ids.add(entry.entry_id)

        key = (entry.medication_name.strip().lower(), entry.scheduled_time)
        if key in medication_time_keys:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"duplicate medication/time collision for '{entry.medication_name}' at {entry.scheduled_time}"
                ),
            )
        medication_time_keys.add(key)

        if not entry.dose_instructions.strip():
            raise HTTPException(status_code=400, detail=f"dose instructions required for '{entry.medication_name}'")

        if entry.priority not in valid_priority:
            raise HTTPException(status_code=400, detail=f"invalid priority '{entry.priority}'")

        if entry.display_name.strip() == "":
            entry.display_name = entry.medication_name

        instructions = entry.dose_instructions.lower()
        mentions_meal_dependency = any(token in instructions for token in ["meal", "food", "empty stomach"])
        if mentions_meal_dependency and entry.meal_constraint.value == "none":
            raise HTTPException(
                status_code=400,
                detail=f"meal constraint required for '{entry.medication_name}'",
            )

        if entry.criticality_level is MedicationCriticality.CRITICAL and not entry.missed_dose_policy.strip():
            raise HTTPException(
                status_code=400,
                detail=f"missing missed-dose policy for critical medication '{entry.medication_name}'",
            )


def _append_alert_events(patient_id: str, day: str, alerts: list[AdherenceAlert]) -> None:
    for alert in alerts:
        STORE.append_event(
            patient_id=patient_id,
            date=day,
            event_type=ReviewActionType.MEDICATION_ALERT_RAISED,
            message=alert.message,
            metadata={"category": alert.category, "severity": alert.severity},
        )


def _build_summary(
    patient_id: str,
    day: str,
    log: DailyMedicationLog,
    *,
    local_now: datetime,
    patient_timezone: str,
    final_day: bool = False,
) -> CaregiverSummary:
    total = len(log.reminders)
    taken = sum(1 for item in log.confirmations if item.dose_status is DoseStatus.TAKEN)
    skipped = sum(1 for item in log.confirmations if item.dose_status is DoseStatus.SKIPPED)
    delayed = sum(1 for item in log.confirmations if item.dose_status is DoseStatus.DELAYED)
    unsure = sum(1 for item in log.confirmations if item.dose_status is DoseStatus.UNSURE)
    completed_so_far = sum(1 for item in log.reminders if item.status == "completed")
    due_so_far = sum(1 for item in log.reminders if item.status in {"due", "overdue", "completed"})
    overdue_so_far = sum(1 for item in log.reminders if item.status == "overdue")

    current_progress_rate = round((completed_so_far / due_so_far) * 100, 2) if due_so_far else None
    final_day_adherence_rate = round((completed_so_far / total) * 100, 2) if total and final_day else None
    adherence_rate = final_day_adherence_rate if final_day_adherence_rate is not None else (current_progress_rate or 0.0)

    actions: list[str] = []
    if any(alert.clinician_review_recommended for alert in log.alerts):
        actions.append("clinician_review_recommended")
    if any(alert.caregiver_alert for alert in log.alerts):
        actions.append("notify_caregiver")
    if any(alert.urgent_symptom_triage_recommended for alert in log.alerts):
        actions.append("urgent_symptom_triage_recommended")
    if any(alert.category == "emergency_symptoms" for alert in log.alerts):
        actions.append("emergency_escalation")

    if due_so_far == 0:
        summary_text = "No doses are due yet today. Adherence tracking starts when first dose becomes due."
    elif final_day and final_day_adherence_rate is not None:
        summary_text = (
            f"Final day adherence {final_day_adherence_rate}% ({completed_so_far}/{total} completed). "
            f"Overdue={overdue_so_far}. Alerts={len(log.alerts)}."
        )
    else:
        summary_text = (
            f"Progress adherence {current_progress_rate}% ({completed_so_far}/{due_so_far} due doses completed so far). "
            f"Overdue now={overdue_so_far}. Alerts={len(log.alerts)}."
        )

    return CaregiverSummary(
        patient_id=patient_id,
        date=day,
        patient_timezone=patient_timezone,
        local_now=local_now.isoformat(),
        total_doses=total,
        taken_count=taken,
        skipped_count=skipped,
        delayed_count=delayed,
        unsure_count=unsure,
        adherence_rate=adherence_rate,
        total_doses_today=total,
        doses_due_so_far=due_so_far,
        doses_completed_so_far=completed_so_far,
        overdue_so_far=overdue_so_far,
        final_day_adherence_rate=final_day_adherence_rate,
        current_progress_rate=current_progress_rate,
        active_alerts=log.alerts,
        recommended_actions=actions,
        summary_text=summary_text,
    )


def _timeline(log: DailyMedicationLog, day: str, patient_id: str) -> MedicationTimelineResponse:
    latest_confirmation_by_reminder: dict[str, DoseConfirmation] = {}
    for confirmation in log.confirmations:
        previous = latest_confirmation_by_reminder.get(confirmation.reminder_id)
        if previous is None or confirmation.confirmed_at > previous.confirmed_at:
            latest_confirmation_by_reminder[confirmation.reminder_id] = confirmation

    items: list[MedicationTimelineItem] = []
    for reminder in sorted(log.reminders, key=lambda item: item.scheduled_datetime):
        latest = latest_confirmation_by_reminder.get(reminder.reminder_id)
        items.append(
            MedicationTimelineItem(
                order_key=reminder.scheduled_datetime,
                scheduled_datetime=reminder.scheduled_datetime,
                medication_name=reminder.medication_name,
                schedule_entry_id=reminder.schedule_entry_id,
                status=reminder.status,
                meal_constraint=reminder.meal_constraint,
                priority=reminder.priority,
                confirmation_status=latest.dose_status if latest else None,
            )
        )
    return MedicationTimelineResponse(patient_id=patient_id, date=day, timeline=items)


def _window_status(reminders: list[MedicationReminder]) -> str:
    statuses = {item.status for item in reminders}
    if statuses == {"completed"}:
        return "completed"
    if "overdue" in statuses:
        return "overdue"
    if "due" in statuses:
        return "due"
    return "upcoming"


def _window_risk(reminders: list[MedicationReminder]) -> str:
    if any(item.criticality_level is MedicationCriticality.CRITICAL for item in reminders):
        return "high"
    if any(item.criticality_level is MedicationCriticality.IMPORTANT for item in reminders):
        return "medium"
    return "low"


def _meal_summary(reminders: list[MedicationReminder]) -> str:
    rules = sorted({item.meal_constraint.value for item in reminders})
    return ", ".join(rules) if rules else "none"


def _administration_windows(log: DailyMedicationLog, tz: ZoneInfo) -> list[AdministrationWindow]:
    grouped: dict[str, list[MedicationReminder]] = {}
    for reminder in log.reminders:
        localized = _localize_reminder(reminder, tz)
        if localized.local_scheduled_time is None:
            continue
        slot = localized.local_scheduled_time[11:16]
        grouped.setdefault(slot, []).append(localized)

    windows: list[AdministrationWindow] = []
    for slot in sorted(grouped.keys()):
        meds = sorted(grouped[slot], key=lambda item: item.medication_name.lower())
        windows.append(
            AdministrationWindow(
                window_id=f"window_{log.patient_id}_{log.date}_{slot.replace(':', '')}",
                slot_time=slot,
                meds=meds,
                meal_rule_summary=_meal_summary(meds),
                all_completed=all(item.status == "completed" for item in meds),
                window_risk_level=_window_risk(meds),
                window_status=_window_status(meds),
            )
        )
    return windows


def _caregiver_actions(log: DailyMedicationLog, windows: list[AdministrationWindow]) -> list[CaregiverActionRecommendation]:
    actions: list[CaregiverActionRecommendation] = []
    for window in windows:
        if window.window_status == "due":
            if window.window_risk_level == "high":
                actions.append(
                    CaregiverActionRecommendation(
                        action_id=f"act_{window.window_id}_critical_due",
                        action_type="critical_medication_window_due_now",
                        priority="high",
                        reason=f"Critical medication window due now at {window.slot_time}",
                        related_window_id=window.window_id,
                    )
                )
            actions.append(
                CaregiverActionRecommendation(
                    action_id=f"act_{window.window_id}_remind",
                    action_type="remind_patient_now",
                    priority="high" if window.window_risk_level == "high" else "medium",
                    reason=f"Doses due in {window.slot_time} administration window",
                    related_window_id=window.window_id,
                )
            )
            if "before_meal" in window.meal_rule_summary:
                actions.append(
                    CaregiverActionRecommendation(
                        action_id=f"act_{window.window_id}_before_food",
                        action_type="give_now_before_food",
                        priority="high" if window.window_risk_level == "high" else "medium",
                        reason=f"Before-food dose window at {window.slot_time}",
                        related_window_id=window.window_id,
                    )
                )
            if "with_food" in window.meal_rule_summary or "after_meal" in window.meal_rule_summary:
                meal_action_type = "confirm_after_breakfast" if _is_morning_slot(window.slot_time) else "confirm_after_food"
                actions.append(
                    CaregiverActionRecommendation(
                        action_id=f"act_{window.window_id}_food",
                        action_type=meal_action_type,
                        priority="medium",
                        reason="Meal-constrained doses are due",
                        related_window_id=window.window_id,
                    )
                )
        elif window.window_status == "overdue":
            if window.window_risk_level == "high":
                actions.append(
                    CaregiverActionRecommendation(
                        action_id=f"act_{window.window_id}_critical_overdue",
                        action_type="overdue_critical_medication_window_follow_up_now",
                        priority="critical",
                        reason=f"Overdue critical medication window at {window.slot_time}",
                        related_window_id=window.window_id,
                    )
                )
            actions.append(
                CaregiverActionRecommendation(
                    action_id=f"act_{window.window_id}_overdue",
                    action_type="contact_clinician",
                    priority="high",
                    reason=f"Overdue doses in {window.slot_time} window",
                    related_window_id=window.window_id,
                )
            )

    for alert in log.alerts:
        if alert.category in {"concerning_symptoms", "urgent_symptoms"}:
            actions.append(
                CaregiverActionRecommendation(
                    action_id=f"act_alert_{alert.alert_id}_triage",
                    action_type="run_urgent_symptom_triage",
                    priority="high",
                    reason=alert.message,
                    related_alert_id=alert.alert_id,
                )
            )
        if alert.category == "emergency_symptoms":
            actions.append(
                CaregiverActionRecommendation(
                    action_id=f"act_alert_{alert.alert_id}_emergency",
                    action_type="emergency_escalation",
                    priority="critical",
                    reason=alert.message,
                    related_alert_id=alert.alert_id,
                )
            )
        if alert.category == "missed_critical_dose":
            actions.append(
                CaregiverActionRecommendation(
                    action_id=f"act_alert_{alert.alert_id}_recheck",
                    action_type="monitor_and_recheck",
                    priority="high",
                    reason=alert.message,
                    related_alert_id=alert.alert_id,
                )
            )
        if alert.category == "repeated_missed_doses":
            actions.append(
                CaregiverActionRecommendation(
                    action_id=f"act_alert_{alert.alert_id}_contact",
                    action_type="contact_clinician",
                    priority="high",
                    reason=alert.message,
                    related_alert_id=alert.alert_id,
                )
            )
        if alert.category == "meal_rule_violation_critical_med":
            actions.append(
                CaregiverActionRecommendation(
                    action_id=f"act_alert_{alert.alert_id}_food_recheck",
                    action_type="confirm_after_food",
                    priority="high",
                    reason=alert.message,
                    related_alert_id=alert.alert_id,
                )
            )

    seen: set[str] = set()
    deduped: list[CaregiverActionRecommendation] = []
    for action in actions:
        key = f"{action.action_type}:{action.reason}:{action.related_window_id}:{action.related_alert_id}"
        if key not in seen:
            seen.add(key)
            deduped.append(action)
    return deduped


def _window_medication_names(window: AdministrationWindow) -> str:
    return ", ".join(item.medication_name for item in window.meds)


def _window_reminder_message(window: AdministrationWindow) -> str:
    names = _window_medication_names(window)
    if window.window_risk_level == "high":
        return (
            f"{window.slot_time}: Critical medicines due ({names}). Meal rule: {window.meal_rule_summary}. "
            "Reply TAKEN / DELAYED / SKIPPED / UNSURE."
        )
    if window.meal_rule_summary == "before_meal":
        return (
            f"{window.slot_time}: {names} due before food. "
            "Reply TAKEN / DELAYED / SKIPPED / UNSURE."
        )
    return (
        f"{window.slot_time}: Medicines due ({names}). Meal rule: {window.meal_rule_summary}. "
        "Reply TAKEN / DELAYED / SKIPPED / UNSURE."
    )


def _window_overdue_followup_message(window: AdministrationWindow) -> str:
    names = _window_medication_names(window)
    return (
        f"{window.slot_time}: Overdue critical medication window ({names}). "
        "Follow up now and confirm TAKEN / DELAYED / SKIPPED / UNSURE."
    )


def _find_existing_message(
    log: DailyMedicationLog,
    *,
    window_id: str,
    message_kind: MessageKind,
    recipient_role: RecipientRole,
) -> MedicationMessageRecord | None:
    for message in log.messages:
        if (
            message.window_id == window_id
            and message.message_kind == message_kind
            and message.recipient_role == recipient_role
            and message.delivery_status in {DeliveryStatus.SENT, DeliveryStatus.DELIVERED}
        ):
            return message
    return None


def _message_dedupe_key(
    *,
    patient_id: str,
    day: str,
    window_id: str,
    recipient_role: RecipientRole,
    channel_type: ChannelType,
    message_kind: MessageKind,
    escalation_stage: int | None = None,
) -> str:
    stage = str(escalation_stage) if escalation_stage is not None else "na"
    return (
        f"{day}:{patient_id}:{window_id}:{recipient_role.value}:{channel_type.value}:{message_kind.value}:{stage}"
    )


def _has_message_with_dedupe(log: DailyMedicationLog, dedupe_key: str) -> bool:
    return any(message.dedupe_key == dedupe_key for message in log.messages)


def _latest_overdue_followup_stage(log: DailyMedicationLog, window_id: str) -> tuple[int | None, datetime | None]:
    latest_stage: int | None = None
    latest_time: datetime | None = None
    for message in log.messages:
        if message.window_id != window_id or message.message_kind is not MessageKind.OVERDUE_FOLLOWUP:
            continue
        stage = message.escalation_stage
        if stage is None:
            continue
        sent_at = datetime.fromisoformat(message.created_at)
        if latest_time is None or sent_at > latest_time:
            latest_time = sent_at
            latest_stage = stage
    return latest_stage, latest_time


def _latest_customer_message_at(patient_id: str) -> str:
    latest: datetime | None = None
    for log in _all_patient_logs(patient_id):
        for message in log.messages:
            if message.message_kind is not MessageKind.CONFIRMATION_RECEIVED:
                continue
            created = datetime.fromisoformat(message.created_at)
            if latest is None or created > latest:
                latest = created
    return latest.isoformat() if latest is not None else ""


def _record_message(log: DailyMedicationLog, message: MedicationMessageRecord) -> None:
    log.messages.append(message)


def _window_by_id(windows: list[AdministrationWindow], window_id: str) -> AdministrationWindow | None:
    for window in windows:
        if window.window_id == window_id:
            return window
    return None


def _all_patient_logs(patient_id: str) -> list[DailyMedicationLog]:
    return STORE.list_logs_for_patient(patient_id)


def _find_message_by_id(patient_id: str, message_id: str) -> MedicationMessageRecord | None:
    for log in _all_patient_logs(patient_id):
        for message in log.messages:
            if message.message_id == message_id:
                return message
    return None


def _find_recent_message_for_sender(patient_id: str, sender: str) -> MedicationMessageRecord | None:
    normalized_sender = _normalize_phone(sender)
    latest: MedicationMessageRecord | None = None
    latest_ts: datetime | None = None
    for log in _all_patient_logs(patient_id):
        for message in log.messages:
            recipient = _normalize_phone(message.metadata.get("recipient_address", ""))
            if recipient and recipient != normalized_sender:
                continue
            created = datetime.fromisoformat(message.created_at)
            if latest_ts is None or created > latest_ts:
                latest_ts = created
                latest = message
    return latest


def _map_twilio_delivery_status(value: str) -> DeliveryStatus:
    normalized = value.strip().lower()
    if normalized in {"queued", "accepted", "sending"}:
        return DeliveryStatus.QUEUED
    if normalized == "sent":
        return DeliveryStatus.SENT
    if normalized == "delivered":
        return DeliveryStatus.DELIVERED
    if normalized in {"failed", "undelivered"}:
        return DeliveryStatus.FAILED
    return DeliveryStatus.QUEUED


def _resolve_patient_id_from_sender(sender: str) -> str | None:
    source = _normalize_phone(sender)
    for patient in STORE.list_patients():
        if patient.patient_contact and _normalize_phone(patient.patient_contact) == source:
            return patient.patient_id
        if _normalize_phone(patient.caregiver_contact) == source:
            return patient.patient_id
    return None


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="medication-workflow", status="ok")


@app.post("/medication/simulated-time/set", response_model=SimulatedTimeState)
def set_simulated_time(payload: SetSimulatedTimeRequest) -> SimulatedTimeState:
    target = datetime.fromisoformat(payload.simulated_now)
    result = STORE.set_simulated_now(target)
    logger.info("simulated_time_set", simulated_now=result.simulated_now, dev_only=True)
    return result


@app.post("/medication/simulated-time/advance", response_model=SimulatedTimeState)
def advance_simulated_time(payload: AdvanceSimulatedTimeRequest) -> SimulatedTimeState:
    result = STORE.advance_simulated_now(minutes=payload.minutes, hours=payload.hours)
    logger.info("simulated_time_advanced", simulated_now=result.simulated_now, dev_only=True)
    return result


@app.post("/medication/simulated-time/reset-day", response_model=SimulatedTimeState)
def reset_simulated_time_day() -> SimulatedTimeState:
    result = STORE.reset_simulated_to_day_start()
    logger.info("simulated_time_reset_day", simulated_now=result.simulated_now, dev_only=True)
    return result


@app.get("/medication/simulated-time", response_model=SimulatedTimeState)
def get_simulated_time() -> SimulatedTimeState:
    return STORE.get_simulated_state()


@app.post("/medication/patient", response_model=PatientRecord)
def create_patient(payload: PatientRecord) -> PatientRecord:
    patient = STORE.put_patient(payload)
    logger.info("medication_patient_created", patient_id=patient.patient_id)
    return patient


@app.get("/medication/patient/{patient_id}", response_model=PatientRecord)
def get_patient(patient_id: str) -> PatientRecord:
    return _get_patient_or_404(patient_id)


@app.post("/medication/patient/{patient_id}/plan", response_model=MedicationPlan)
def attach_plan_to_patient(patient_id: str, payload: MedicationPlan) -> MedicationPlan:
    _get_patient_or_404(patient_id)
    if payload.patient_id != patient_id:
        raise HTTPException(status_code=400, detail="payload patient_id mismatch")
    _validate_plan_entries(payload)
    plan = STORE.put_plan(payload)
    STORE.append_event(
        patient_id=plan.patient_id,
        date=_today_date_string(),
        event_type=ReviewActionType.SESSION_STARTED,
        message="medication plan attached to patient",
        metadata={"plan_id": plan.plan_id},
    )
    return plan


@app.post("/medication/plan", response_model=MedicationPlan)
def create_medication_plan(payload: MedicationPlan) -> MedicationPlan:
    _get_patient_or_404(payload.patient_id)
    _validate_plan_entries(payload)
    plan = STORE.put_plan(payload)
    STORE.append_event(
        patient_id=plan.patient_id,
        date=_today_date_string(),
        event_type=ReviewActionType.SESSION_STARTED,
        message="medication plan created",
        metadata={"plan_id": plan.plan_id},
    )
    logger.info("medication_plan_created", patient_id=plan.patient_id, plan_id=plan.plan_id)
    return plan


@app.put("/medication/patient/{patient_id}/plan/entry/{entry_id}", response_model=MedicationPlan)
def edit_medication_schedule_entry(
    patient_id: str,
    entry_id: str,
    payload: UpdateMedicationScheduleEntryRequest,
) -> MedicationPlan:
    _get_patient_or_404(patient_id)
    plan = _get_plan_or_404(patient_id)

    for index, entry in enumerate(plan.medications):
        if entry.entry_id == entry_id:
            plan.medications[index] = plan.medications[index].model_copy(update=payload.model_dump())
            _validate_plan_entries(plan)
            STORE.put_plan(plan)
            STORE.append_event(
                patient_id=patient_id,
                date=_today_date_string(),
                event_type=ReviewActionType.REVIEW_STATUS_UPDATED,
                message="medication schedule entry edited",
                metadata={"entry_id": entry_id},
            )
            return plan

    raise HTTPException(status_code=404, detail="schedule entry not found")


@app.post("/medication/plan/import", response_model=MedicationPlanExportResponse)
def import_medication_plan(payload: MedicationPlanImportRequest) -> MedicationPlanExportResponse:
    if payload.patient.patient_id != payload.plan.patient_id:
        raise HTTPException(status_code=400, detail="patient_id mismatch between patient and plan")
    _validate_plan_entries(payload.plan)
    STORE.put_patient(payload.patient)
    STORE.put_plan(payload.plan)
    return MedicationPlanExportResponse(patient=payload.patient, plan=payload.plan)


@app.get("/medication/plan/{patient_id}", response_model=MedicationPlan)
def get_medication_plan(patient_id: str) -> MedicationPlan:
    return _get_plan_or_404(patient_id)


@app.get("/medication/plan/{patient_id}/export", response_model=MedicationPlanExportResponse)
def export_medication_plan(patient_id: str) -> MedicationPlanExportResponse:
    patient, plan = _assert_patient_and_plan(patient_id)
    return MedicationPlanExportResponse(patient=patient, plan=plan)


@app.get("/medication/{patient_id}/schedule", response_model=DailyMedicationLog)
def get_daily_schedule(patient_id: str, date: str = Query(...)) -> DailyMedicationLog:
    _, plan = _assert_patient_and_plan(patient_id)
    log = STORE.get_log(patient_id, date)
    now = STORE.now()
    updated = _refresh_day_state(plan, log, now)
    if not any(event.event_type == ReviewActionType.MEDICATION_REMINDER_GENERATED for event in updated.audit_events):
        STORE.append_event(
            patient_id=patient_id,
            date=date,
            event_type=ReviewActionType.MEDICATION_REMINDER_GENERATED,
            message="daily reminders generated",
            metadata={"count": str(len(updated.reminders))},
        )
    return updated


@app.get("/medication/{patient_id}/due-now", response_model=DueNowResponse)
def due_now(patient_id: str, at: str | None = Query(None)) -> DueNowResponse:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)

    at_utc = _parse_query_datetime(at, timezone)
    local_now = at_utc.astimezone(timezone)
    day = _local_day_from_utc(at_utc, timezone)
    log = STORE.get_log(patient_id, day)
    updated = _refresh_day_state(plan, log, at_utc)

    due = _localize_reminders([reminder for reminder in updated.reminders if reminder.status == "due"], timezone)
    upcoming = _localize_reminders([reminder for reminder in updated.reminders if reminder.status == "upcoming"], timezone)
    next_upcoming = upcoming[0] if upcoming else None

    return DueNowResponse(
        patient_id=patient_id,
        at=at_utc.isoformat(),
        patient_timezone=timezone_name,
        local_now=local_now.isoformat(),
        due_now=due,
        next_upcoming=next_upcoming,
    )


@app.post("/medication/{patient_id}/send-due-reminders", response_model=SendDueRemindersResponse)
def send_due_reminders(patient_id: str) -> SendDueRemindersResponse:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)
    now_utc = STORE.now()
    local_now = now_utc.astimezone(timezone)
    day = local_now.date().isoformat()

    log = STORE.get_log(patient_id, day)
    updated = _refresh_day_state(plan, log, now_utc)
    windows = _administration_windows(updated, timezone)

    sent_messages: list[MedicationMessageRecord] = []
    channel_type = _transport_channel_type()
    last_customer_message_at = _latest_customer_message_at(patient_id)

    for window in windows:
        if window.window_status == "due":
            dedupe_key = _message_dedupe_key(
                patient_id=patient_id,
                day=day,
                window_id=window.window_id,
                recipient_role=RecipientRole.PATIENT,
                channel_type=channel_type,
                message_kind=MessageKind.DUE_REMINDER,
            )
            if _has_message_with_dedupe(updated, dedupe_key):
                continue
            recipient = _recipient_address(patient, RecipientRole.PATIENT)
            _enforce_pilot_send_guard(
                patient=patient,
                log=updated,
                day=day,
                recipient_address=recipient,
                channel_type=channel_type,
            )
            message = MESSAGE_TRANSPORT.send_message(
                OutboundMessageRequest(
                    patient_id=patient_id,
                    date=day,
                    window_id=window.window_id,
                    window_slot_time=window.slot_time,
                    recipient_role=RecipientRole.PATIENT,
                    recipient_address=recipient,
                    channel_type=channel_type,
                    message_kind=MessageKind.DUE_REMINDER,
                    content=_window_reminder_message(window),
                    dedupe_key=dedupe_key,
                    escalation_stage=None,
                    metadata={
                        "meal_rule_summary": window.meal_rule_summary,
                        "risk_level": window.window_risk_level,
                        "recipient_address": recipient,
                        "last_customer_message_at": last_customer_message_at,
                    },
                )
            )
            _record_message(updated, message)
            logger.info(
                "medication_outbound_sent",
                patient_id=patient_id,
                window_id=window.window_id,
                message_id=message.message_id,
                message_kind=message.message_kind.value,
                recipient_role=message.recipient_role.value,
                channel_type=message.channel_type.value,
                dedupe_key=message.dedupe_key,
            )
            sent_messages.append(message)
            STORE.append_event(
                patient_id=patient_id,
                date=day,
                event_type=ReviewActionType.MEDICATION_REMINDER_GENERATED,
                message="window reminder sent",
                metadata={"window_id": window.window_id, "message_id": message.message_id},
            )
    return SendDueRemindersResponse(
        patient_id=patient_id,
        date=day,
        patient_timezone=timezone_name,
        local_now=local_now.isoformat(),
        sent_messages=sent_messages,
    )


@app.post("/medication/{patient_id}/send-overdue-critical-followups", response_model=SendOverdueFollowupsResponse)
def send_overdue_critical_followups(
    patient_id: str,
    cooldown_minutes: int = Query(60, ge=1, le=1440),
) -> SendOverdueFollowupsResponse:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)
    now_utc = STORE.now()
    local_now = now_utc.astimezone(timezone)
    day = local_now.date().isoformat()
    log = STORE.get_log(patient_id, day)
    updated = _refresh_day_state(plan, log, now_utc)
    windows = _administration_windows(updated, timezone)

    sent_messages: list[MedicationMessageRecord] = []
    cooldown_seconds = cooldown_minutes * 60
    channel_type = _transport_channel_type()
    last_customer_message_at = _latest_customer_message_at(patient_id)

    for window in windows:
        if not (window.window_status == "overdue" and window.window_risk_level == "high"):
            continue

        latest_stage, latest_time = _latest_overdue_followup_stage(updated, window.window_id)
        next_stage: int | None = None

        if latest_stage is None:
            next_stage = 1
        elif latest_stage == 1 and latest_time is not None:
            elapsed = (now_utc - latest_time).total_seconds()
            if elapsed >= cooldown_seconds:
                next_stage = 2

        if next_stage is None:
            continue

        dedupe_key = _message_dedupe_key(
            patient_id=patient_id,
            day=day,
            window_id=window.window_id,
            recipient_role=RecipientRole.CAREGIVER,
            channel_type=channel_type,
            message_kind=MessageKind.OVERDUE_FOLLOWUP,
            escalation_stage=next_stage,
        )
        if _has_message_with_dedupe(updated, dedupe_key):
            continue
        recipient = _recipient_address(patient, RecipientRole.CAREGIVER)
        _enforce_pilot_send_guard(
            patient=patient,
            log=updated,
            day=day,
            recipient_address=recipient,
            channel_type=channel_type,
        )

        followup = MESSAGE_TRANSPORT.send_message(
            OutboundMessageRequest(
                patient_id=patient_id,
                date=day,
                window_id=window.window_id,
                window_slot_time=window.slot_time,
                recipient_role=RecipientRole.CAREGIVER,
                recipient_address=recipient,
                channel_type=channel_type,
                message_kind=MessageKind.OVERDUE_FOLLOWUP,
                content=_window_overdue_followup_message(window),
                dedupe_key=dedupe_key,
                escalation_stage=next_stage,
                metadata={
                    "risk_level": "high",
                    "window_status": "overdue",
                    "recipient_address": recipient,
                    "last_customer_message_at": last_customer_message_at,
                    "escalation_stage": str(next_stage),
                    "cooldown_minutes": str(cooldown_minutes),
                },
            )
        )
        _record_message(updated, followup)
        logger.info(
            "medication_outbound_sent",
            patient_id=patient_id,
            window_id=window.window_id,
            message_id=followup.message_id,
            message_kind=followup.message_kind.value,
            recipient_role=followup.recipient_role.value,
            channel_type=followup.channel_type.value,
            dedupe_key=followup.dedupe_key,
            escalation_stage=followup.escalation_stage,
        )
        sent_messages.append(followup)
        STORE.append_event(
            patient_id=patient_id,
            date=day,
            event_type=ReviewActionType.MEDICATION_ALERT_RAISED,
            message="overdue critical window follow-up message sent",
            metadata={"window_id": window.window_id, "message_id": followup.message_id, "stage": str(next_stage)},
        )

    return SendOverdueFollowupsResponse(
        patient_id=patient_id,
        date=day,
        patient_timezone=timezone_name,
        local_now=local_now.isoformat(),
        sent_messages=sent_messages,
    )


@app.get("/medication/{patient_id}/messages", response_model=list[MedicationMessageRecord])
def list_messages(patient_id: str, date: str = Query(...)) -> list[MedicationMessageRecord]:
    _, plan = _assert_patient_and_plan(patient_id)
    log = STORE.get_log(patient_id, date)
    _refresh_day_state(plan, log, STORE.now())
    return list(log.messages)


def _apply_window_confirmation(patient_id: str, payload: MessageConfirmationRequest) -> DailyMedicationLog:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)

    confirmed_at_utc = _parse_query_datetime(payload.confirmed_at, timezone)
    day = _local_day_from_utc(confirmed_at_utc, timezone)
    log = STORE.get_log(patient_id, day)
    updated = _refresh_day_state(plan, log, confirmed_at_utc)
    windows = _administration_windows(updated, timezone)
    window = _window_by_id(windows, payload.window_id)
    if window is None:
        raise HTTPException(status_code=404, detail="window_id not found")

    normalized = MESSAGE_TRANSPORT.receive_confirmation(payload.confirmation.value)
    confirmation_status = DoseStatus(normalized.lower())

    for reminder in window.meds:
        updated.confirmations.append(
            DoseConfirmation(
                patient_id=patient_id,
                reminder_id=reminder.reminder_id,
                schedule_entry_id=reminder.schedule_entry_id,
                dose_status=confirmation_status,
                confirmed_at=confirmed_at_utc.isoformat(),
                meal_condition_satisfied=payload.meal_condition_satisfied,
                note=payload.note,
            )
        )

    STORE.append_event(
        patient_id=patient_id,
        date=day,
        event_type=ReviewActionType.MEDICATION_DOSE_CONFIRMED,
        message="window confirmation recorded from transport",
        metadata={
            "window_id": payload.window_id,
            "confirmation": payload.confirmation.value,
            "responder_role": payload.responder_role.value,
            "message_id": payload.message_id or "",
        },
    )

    _refresh_day_state(plan, updated, confirmed_at_utc)
    _append_alert_events(patient_id, day, updated.alerts)
    return updated


@app.post("/medication/{patient_id}/message-confirmation", response_model=DailyMedicationLog)
def message_confirmation(patient_id: str, payload: MessageConfirmationRequest) -> DailyMedicationLog:
    return _apply_window_confirmation(patient_id, payload)


@app.post("/webhooks/twilio/whatsapp/inbound")
async def twilio_whatsapp_inbound(request: Request) -> Response:
    form = await request.form()
    form_data = {key: str(value) for key, value in form.items()}
    if not _validate_twilio_request_signature(request, form_data):
        raise HTTPException(status_code=403, detail="invalid twilio signature")

    from_number = form_data.get("From", "")
    body = form_data.get("Body", "")
    original_sid = form_data.get("OriginalRepliedMessageSid", "")
    inbound_sid = form_data.get("MessageSid", "")

    patient_id = _resolve_patient_id_from_sender(from_number)
    if patient_id is None:
        xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>No active medication profile found for this number.</Message></Response>"
        return Response(content=xml, media_type="text/xml")
    if _pilot_mode_enabled() and not _pilot_allowed_number(from_number):
        raise HTTPException(status_code=403, detail="pilot mode: inbound sender number not allowed")

    target_message: MedicationMessageRecord | None = None
    if original_sid:
        target_message = _find_message_by_id(patient_id, original_sid)
    if target_message is None:
        target_message = _find_recent_message_for_sender(patient_id, _normalize_phone(from_number))
    if target_message is None:
        xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>Could not map reply to a medication window. Reply TAKEN / DELAYED / SKIPPED / UNSURE to the latest reminder.</Message></Response>"
        return Response(content=xml, media_type="text/xml")

    try:
        normalized = MESSAGE_TRANSPORT.receive_confirmation(body)
    except ValueError:
        xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>Unrecognized reply. Please reply TAKEN, DELAYED, SKIPPED, or UNSURE.</Message></Response>"
        return Response(content=xml, media_type="text/xml")

    payload = MessageConfirmationRequest(
        window_id=target_message.window_id,
        confirmation=DoseStatus(normalized.lower()),
        responder_role=target_message.recipient_role,
        confirmed_at=STORE.now().isoformat(),
        message_id=target_message.message_id,
        note="twilio_whatsapp_inbound",
    )
    _apply_window_confirmation(patient_id, payload)

    confirmation_day = target_message.date
    confirmation_log = STORE.get_log(patient_id, confirmation_day)
    inbound_record = MedicationMessageRecord(
        message_id=inbound_sid or f"inbound_{datetime.now(UTC).timestamp()}",
        patient_id=patient_id,
        date=confirmation_day,
        window_id=target_message.window_id,
        window_slot_time=target_message.window_slot_time,
        recipient_role=target_message.recipient_role,
        channel_type=ChannelType.WHATSAPP,
        message_kind=MessageKind.CONFIRMATION_RECEIVED,
        content=body,
        delivery_status=DeliveryStatus.DELIVERED,
        created_at=STORE.now().isoformat(),
        dedupe_key=f"inbound:{inbound_sid or body}:{patient_id}",
        escalation_stage=None,
        metadata={
            "from": from_number,
            "normalized_confirmation": normalized,
            "linked_message_id": target_message.message_id,
        },
    )
    if not _has_message_with_dedupe(confirmation_log, inbound_record.dedupe_key):
        _record_message(confirmation_log, inbound_record)
    logger.info(
        "medication_inbound_confirmation",
        patient_id=patient_id,
        from_number=from_number,
        normalized_confirmation=normalized,
        linked_message_id=target_message.message_id,
    )

    xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><Response><Message>Received. Medication window confirmation recorded.</Message></Response>"
    return Response(content=xml, media_type="text/xml")


@app.post("/webhooks/twilio/whatsapp/status")
async def twilio_whatsapp_status(request: Request) -> dict[str, str]:
    form = await request.form()
    form_data = {key: str(value) for key, value in form.items()}
    if not _validate_twilio_request_signature(request, form_data):
        raise HTTPException(status_code=403, detail="invalid twilio signature")

    message_sid = form_data.get("MessageSid", "")
    status = form_data.get("MessageStatus", "queued")

    updated = False
    for patient in STORE.list_patients():
        message = _find_message_by_id(patient.patient_id, message_sid)
        if message is None:
            continue
        message.delivery_status = _map_twilio_delivery_status(status)
        message.metadata["twilio_status"] = status
        STORE.append_event(
            patient_id=patient.patient_id,
            date=message.date,
            event_type=ReviewActionType.MEDICATION_ALERT_RAISED,
            message="twilio delivery status updated",
            metadata={"message_id": message_sid, "delivery_status": message.delivery_status.value},
        )
        logger.info(
            "medication_delivery_status_updated",
            patient_id=patient.patient_id,
            message_id=message_sid,
            delivery_status=message.delivery_status.value,
        )
        updated = True
        break

    return {"status": "ok" if updated else "ignored", "message_sid": message_sid}


@app.post("/medication/{patient_id}/dose-confirmation", response_model=DailyMedicationLog)
def confirm_dose(patient_id: str, payload: DoseConfirmationRequest) -> DailyMedicationLog:
    _, plan = _assert_patient_and_plan(patient_id)

    confirmed_at = datetime.fromisoformat(payload.confirmed_at)
    day = confirmed_at.date().isoformat()
    log = STORE.get_log(patient_id, day)
    updated = _refresh_day_state(plan, log, confirmed_at)

    reminder = _find_reminder(updated, payload.schedule_entry_id, payload.scheduled_datetime)
    if reminder is None:
        raise HTTPException(status_code=404, detail="reminder instance not found for schedule entry/time")

    confirmation = DoseConfirmation(
        patient_id=patient_id,
        reminder_id=reminder.reminder_id,
        schedule_entry_id=payload.schedule_entry_id,
        dose_status=payload.dose_status,
        confirmed_at=payload.confirmed_at,
        meal_condition_satisfied=payload.meal_condition_satisfied,
        note=payload.note,
    )
    updated.confirmations.append(confirmation)

    STORE.append_event(
        patient_id=patient_id,
        date=day,
        event_type=ReviewActionType.MEDICATION_DOSE_CONFIRMED,
        message="dose confirmation recorded",
        metadata={"schedule_entry_id": payload.schedule_entry_id, "dose_status": payload.dose_status.value},
    )

    _refresh_day_state(plan, updated, confirmed_at)
    _append_alert_events(patient_id, day, updated.alerts)

    logger.info("dose_confirmed", patient_id=patient_id, schedule_entry_id=payload.schedule_entry_id, status=payload.dose_status)
    return updated


@app.post("/medication/{patient_id}/side-effect-checkin", response_model=DailyMedicationLog)
def side_effect_checkin(patient_id: str, payload: SideEffectCheckinRequest) -> DailyMedicationLog:
    _, plan = _assert_patient_and_plan(patient_id)

    checkin_time = datetime.fromisoformat(payload.checkin_time)
    day = checkin_time.date().isoformat()
    log = STORE.get_log(patient_id, day)
    updated = _refresh_day_state(plan, log, checkin_time)

    checkin = SideEffectCheckin(
        patient_id=patient_id,
        checkin_time=payload.checkin_time,
        feeling=payload.feeling,
        dizziness=payload.dizziness,
        breathlessness=payload.breathlessness,
        bleeding=payload.bleeding,
        nausea=payload.nausea,
        weakness=payload.weakness,
        swelling=payload.swelling,
        note=payload.note,
        chest_pain=payload.chest_pain,
        confusion=payload.confusion,
        near_fainting=payload.near_fainting,
        severe_weakness=payload.severe_weakness,
    )
    updated.side_effect_checkins.append(checkin)

    STORE.append_event(
        patient_id=patient_id,
        date=day,
        event_type=ReviewActionType.MEDICATION_CHECKIN_RECORDED,
        message="side-effect check-in recorded",
        metadata={"feeling": payload.feeling},
    )

    _refresh_day_state(plan, updated, checkin_time)
    _append_alert_events(patient_id, day, updated.alerts)
    return updated


@app.get("/medication/{patient_id}/daily-summary", response_model=CaregiverSummary)
def daily_summary(patient_id: str, date: str = Query(...)) -> CaregiverSummary:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)

    log = STORE.get_log(patient_id, date)
    updated = _refresh_day_state(plan, log, STORE.now())
    summary = _build_summary(
        patient_id,
        date,
        updated,
        local_now=STORE.now().astimezone(timezone),
        patient_timezone=timezone_name,
    )

    STORE.append_event(
        patient_id=patient_id,
        date=date,
        event_type=ReviewActionType.MEDICATION_SUMMARY_GENERATED,
        message="daily adherence summary generated",
        metadata={"adherence_rate": str(summary.adherence_rate)},
    )

    return summary


@app.get("/medication/{patient_id}/dashboard", response_model=MedicationDashboardView)
def dashboard(patient_id: str, date: str = Query(...)) -> MedicationDashboardView:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)
    log = STORE.get_log(patient_id, date)
    updated = _refresh_day_state(plan, log, STORE.now())
    summary = _build_summary(
        patient_id,
        date,
        updated,
        local_now=STORE.now().astimezone(timezone),
        patient_timezone=timezone_name,
    )

    due = [item for item in updated.reminders if item.status == "due"]
    upcoming = [item for item in updated.reminders if item.status == "upcoming"]
    overdue = [item for item in updated.reminders if item.status == "overdue"]
    completed = [item for item in updated.reminders if item.status == "completed"]
    skipped_or_delayed = [
        item for item in updated.confirmations if item.dose_status in {DoseStatus.SKIPPED, DoseStatus.DELAYED}
    ]

    return MedicationDashboardView(
        patient=patient,
        date=date,
        due_now=due,
        upcoming=upcoming,
        overdue=overdue,
        completed=completed,
        skipped_or_delayed=skipped_or_delayed,
        active_alerts=updated.alerts,
        side_effect_checkins=updated.side_effect_checkins,
        daily_adherence_score=summary.adherence_rate,
        caregiver_summary_text=summary.summary_text,
    )


@app.get("/medication/{patient_id}/today", response_model=MedicationTodayView)
def today_view(patient_id: str) -> MedicationTodayView:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)
    local_now = STORE.now().astimezone(timezone)
    day = local_now.date().isoformat()
    log = STORE.get_log(patient_id, day)
    updated = _refresh_day_state(plan, log, STORE.now())
    summary = _build_summary(
        patient_id,
        day,
        updated,
        local_now=local_now,
        patient_timezone=timezone_name,
    )

    symptom_alerts = [
        item
        for item in updated.alerts
        if item.category in {"concerning_symptoms", "urgent_symptoms", "emergency_symptoms"}
    ]
    windows = _administration_windows(updated, timezone)
    actions = _caregiver_actions(updated, windows)
    action_types = [item.action_type for item in actions]

    return MedicationTodayView(
        patient_id=patient.patient_id,
        date=day,
        patient_timezone=timezone_name,
        local_now=local_now.isoformat(),
        administration_windows=windows,
        due_now=_localize_reminders([item for item in updated.reminders if item.status == "due"], timezone),
        overdue=_localize_reminders([item for item in updated.reminders if item.status == "overdue"], timezone),
        completed=_localize_reminders([item for item in updated.reminders if item.status == "completed"], timezone),
        symptom_alerts=symptom_alerts,
        caregiver_action_needed=summary.recommended_actions + action_types,
        caregiver_actions=actions,
        end_of_day_summary=summary,
    )


@app.get("/medication/{patient_id}/alerts", response_model=list[AdherenceAlert])
def alerts(patient_id: str, date: str = Query(...)) -> list[AdherenceAlert]:
    _, plan = _assert_patient_and_plan(patient_id)
    log = STORE.get_log(patient_id, date)
    updated = _refresh_day_state(plan, log, STORE.now())
    return updated.alerts


@app.get("/medication/{patient_id}/notifications", response_model=list[CaregiverNotificationEvent])
def notifications(patient_id: str, date: str = Query(...)) -> list[CaregiverNotificationEvent]:
    _, plan = _assert_patient_and_plan(patient_id)
    log = STORE.get_log(patient_id, date)
    updated = _refresh_day_state(plan, log, STORE.now())
    return updated.notifications


@app.get("/medication/{patient_id}/timeline", response_model=MedicationTimelineResponse)
def timeline(patient_id: str, date: str = Query(...)) -> MedicationTimelineResponse:
    _, plan = _assert_patient_and_plan(patient_id)
    log = STORE.get_log(patient_id, date)
    updated = _refresh_day_state(plan, log, STORE.now())
    return _timeline(updated, date, patient_id)


@app.get("/medication/{patient_id}/log/export", response_model=DailyMedicationExportResponse)
def export_daily_log(patient_id: str, date: str = Query(...)) -> DailyMedicationExportResponse:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)
    log = STORE.get_log(patient_id, date)
    updated = _refresh_day_state(plan, log, STORE.now())
    summary = _build_summary(
        patient_id,
        date,
        updated,
        local_now=STORE.now().astimezone(timezone),
        patient_timezone=timezone_name,
    )
    return DailyMedicationExportResponse(patient=patient, plan=plan, log=updated, summary=summary)


@app.get("/medication/{patient_id}/simulate-day-report", response_model=DaySimulationReport)
def simulate_day_report(patient_id: str, date: str = Query(...)) -> DaySimulationReport:
    patient, plan = _assert_patient_and_plan(patient_id)
    timezone_name = _patient_timezone(patient, plan)
    timezone = _zoneinfo(timezone_name)
    log = STORE.get_log(patient_id, date)
    # A full-day report should be deterministic for the requested date, not dependent on current wall clock.
    day_end = datetime.fromisoformat(f"{date}T23:59:59").replace(tzinfo=timezone).astimezone(UTC)
    updated = _refresh_day_state(plan, log, day_end)
    summary = _build_summary(
        patient_id,
        date,
        updated,
        local_now=day_end.astimezone(timezone),
        patient_timezone=timezone_name,
        final_day=True,
    )
    windows = _administration_windows(updated, timezone)
    actions = _caregiver_actions(updated, windows)

    critical_missed = [item for item in updated.alerts if item.category == "missed_critical_dose"]
    symptom_alerts = [
        item for item in updated.alerts if item.category in {"concerning_symptoms", "urgent_symptoms", "emergency_symptoms"}
    ]
    follow_up = [f"{action.action_type}: {action.reason}" for action in actions[:5]]

    return DaySimulationReport(
        patient_id=patient.patient_id,
        date=date,
        administration_windows=windows,
        completed_windows=sum(1 for item in windows if item.window_status == "completed"),
        delayed_or_missed_windows=sum(1 for item in windows if item.window_status in {"overdue", "due"}),
        critical_missed_dose_events=critical_missed,
        symptom_alerts=symptom_alerts,
        caregiver_notifications=updated.notifications,
        adherence_summary=summary,
        top_caregiver_follow_up_items=follow_up,
    )
