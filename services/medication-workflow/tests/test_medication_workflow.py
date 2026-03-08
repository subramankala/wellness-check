from fastapi.testclient import TestClient

from medication_workflow.main import app


client = TestClient(app)


def _patient_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "display_name": "Rajesh Kumar",
        "timezone": "UTC",
        "caregiver_name": "Anita Kumar",
        "caregiver_contact": "+15550009999",
        "created_at": "2026-03-07T08:00:00+00:00",
        "notes": "Post-cardiac discharge pilot",
    }


def _plan_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "plan_id": f"plan_{patient_id}",
        "workflow_status": "active",
        "timezone": "UTC",
        "created_at": "2026-03-07T08:00:00+00:00",
        "medications": [
            {
                "entry_id": "m1",
                "display_name": "Morning Beta Blocker",
                "generic_name": "metoprolol",
                "medication_name": "CardioMed-A",
                "dose_instructions": "25 mg tablet after meal",
                "scheduled_time": "08:00",
                "meal_constraint": "after_meal",
                "priority": "critical",
                "criticality_level": "critical",
                "monitoring_notes": "Check pulse before dose",
                "missed_dose_policy": "Call caregiver and log missed dose; clinician call if 2 misses",
                "side_effect_watch_items": ["dizziness", "weakness"],
            },
            {
                "entry_id": "m2",
                "display_name": "Noon Diuretic",
                "generic_name": "furosemide",
                "medication_name": "CardioMed-B",
                "dose_instructions": "40 mg tablet with food",
                "scheduled_time": "12:00",
                "meal_constraint": "with_food",
                "priority": "important",
                "criticality_level": "important",
                "monitoring_notes": "Monitor urine output",
                "missed_dose_policy": "Take within 2 hours else skip",
                "side_effect_watch_items": ["dizziness"],
            },
            {
                "entry_id": "m3",
                "display_name": "Night Antiplatelet",
                "generic_name": "clopidogrel",
                "medication_name": "CardioMed-C",
                "dose_instructions": "75 mg tablet",
                "scheduled_time": "22:00",
                "meal_constraint": "none",
                "priority": "critical",
                "criticality_level": "critical",
                "monitoring_notes": "Watch for bleeding",
                "missed_dose_policy": "Call caregiver immediately if missed",
                "side_effect_watch_items": ["bleeding"],
            },
        ],
    }


def _cluster_plan_payload(patient_id: str) -> dict:
    plan = _plan_payload(patient_id)
    plan["medications"].append(
        {
            "entry_id": "m4",
            "display_name": "Morning Statin",
            "generic_name": "atorvastatin",
            "medication_name": "CardioMed-D",
            "dose_instructions": "10 mg after meal",
            "scheduled_time": "08:00",
            "meal_constraint": "after_meal",
            "priority": "important",
            "criticality_level": "important",
            "monitoring_notes": "cluster dose",
            "missed_dose_policy": "caregiver reminder",
            "side_effect_watch_items": ["weakness"],
        }
    )
    return plan


def _setup_patient_plan(patient_id: str, clustered: bool = False) -> None:
    client.post("/medication/patient", json=_patient_payload(patient_id))
    payload = _cluster_plan_payload(patient_id) if clustered else _plan_payload(patient_id)
    response = client.post(f"/medication/patient/{patient_id}/plan", json=payload)
    assert response.status_code == 200


def _kolkata_patient_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "display_name": "Kolkata Patient",
        "timezone": "Asia/Kolkata",
        "caregiver_name": "Caregiver",
        "caregiver_contact": "+911234567890",
        "created_at": "2026-03-07T06:30:00+05:30",
        "notes": "Timezone test patient",
    }


def _kolkata_plan_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "plan_id": f"plan_{patient_id}",
        "workflow_status": "active",
        "timezone": "Asia/Kolkata",
        "created_at": "2026-03-07T06:30:00+05:30",
        "medications": [
            {
                "entry_id": "before_food_0700",
                "display_name": "Before Food Med",
                "generic_name": "testmed-a",
                "medication_name": "TestMed-A",
                "dose_instructions": "1 tablet before food",
                "scheduled_time": "07:00",
                "meal_constraint": "before_meal",
                "priority": "important",
                "criticality_level": "important",
                "monitoring_notes": "before-food test",
                "missed_dose_policy": "log and follow up",
                "side_effect_watch_items": [],
            },
            {
                "entry_id": "critical_after_food_0800",
                "display_name": "Critical After Food Med",
                "generic_name": "testmed-b",
                "medication_name": "TestMed-B",
                "dose_instructions": "1 tablet after food",
                "scheduled_time": "08:00",
                "meal_constraint": "after_meal",
                "priority": "critical",
                "criticality_level": "critical",
                "monitoring_notes": "critical after-food test",
                "missed_dose_policy": "notify caregiver immediately",
                "side_effect_watch_items": [],
            },
        ],
    }


def _setup_kolkata_patient_plan(patient_id: str) -> None:
    client.post("/medication/patient", json=_kolkata_patient_payload(patient_id))
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_kolkata_plan_payload(patient_id))
    assert response.status_code == 200


def _kolkata_1230_plan_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "plan_id": f"plan_{patient_id}",
        "workflow_status": "active",
        "timezone": "Asia/Kolkata",
        "created_at": "2026-03-07T06:30:00+05:30",
        "medications": [
            {
                "entry_id": "med_1230",
                "display_name": "Noon Med",
                "generic_name": "testmed-noon",
                "medication_name": "NoonMed",
                "dose_instructions": "1 tablet after food",
                "scheduled_time": "12:30",
                "meal_constraint": "after_meal",
                "priority": "important",
                "criticality_level": "important",
                "monitoring_notes": "timezone check",
                "missed_dose_policy": "log and follow up",
                "side_effect_watch_items": [],
            }
        ],
    }


def _setup_kolkata_1230_patient_plan(patient_id: str) -> None:
    client.post("/medication/patient", json=_kolkata_patient_payload(patient_id))
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_kolkata_1230_plan_payload(patient_id))
    assert response.status_code == 200


def _care_activity_plan_payload(patient_id: str) -> dict:
    plan = _plan_payload(patient_id)
    plan["timezone"] = "Asia/Kolkata"
    plan["care_activities"] = [
        {
            "activity_id": "breakfast_0800",
            "title": "Breakfast",
            "category": "meal",
            "schedule": "08:00",
            "duration_minutes": 20,
            "instruction": "Have breakfast with low salt meal",
            "frequency": "daily",
            "priority": "important",
            "confirmation_required": True,
            "escalation_policy": "caregiver follow-up if skipped",
        },
        {
            "activity_id": "walk_1000",
            "title": "Morning Walk",
            "category": "activity",
            "schedule": "10:00",
            "duration_minutes": 25,
            "instruction": "Walk slowly for 20-25 minutes",
            "frequency": "daily",
            "priority": "routine",
            "confirmation_required": True,
            "escalation_policy": "reschedule once if delayed",
        },
        {
            "activity_id": "dressing_2000",
            "title": "Wound Dressing",
            "category": "wound_care",
            "schedule": "20:00",
            "duration_minutes": 15,
            "instruction": "Daily dressing with clean supplies",
            "frequency": "daily",
            "priority": "critical",
            "confirmation_required": True,
            "escalation_policy": "caregiver immediate follow-up if missed",
        },
    ]
    return plan


def _setup_patient_plan_with_care(patient_id: str) -> None:
    payload = _patient_payload(patient_id)
    payload["timezone"] = "Asia/Kolkata"
    payload["created_at"] = "2026-03-07T08:00:00+05:30"
    client.post("/medication/patient", json=payload)
    response = client.post(
        f"/medication/patient/{patient_id}/plan",
        json=_care_activity_plan_payload(patient_id),
    )
    assert response.status_code == 200


def test_strict_real_patient_plan_validation() -> None:
    patient_id = "pilot_validation"
    client.post("/medication/patient", json=_patient_payload(patient_id))

    invalid = _plan_payload(patient_id)
    invalid["medications"][0]["dose_instructions"] = ""
    assert client.post(f"/medication/patient/{patient_id}/plan", json=invalid).status_code == 400

    invalid2 = _plan_payload(patient_id)
    invalid2["medications"][1]["priority"] = "unknown"
    assert client.post(f"/medication/patient/{patient_id}/plan", json=invalid2).status_code == 400

    invalid3 = _plan_payload(patient_id)
    invalid3["medications"][0]["missed_dose_policy"] = ""
    assert client.post(f"/medication/patient/{patient_id}/plan", json=invalid3).status_code == 400


def test_missed_critical_dose_notification_event() -> None:
    patient_id = "pilot_missed_critical"
    _setup_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T23:10:00+00:00"})

    events = client.get(f"/medication/{patient_id}/notifications", params={"date": "2026-03-07"}).json()
    assert "missed_critical_dose" in [item["event_type"] for item in events]


def test_repeated_missed_doses_notification_escalation() -> None:
    patient_id = "pilot_repeated_miss"
    _setup_patient_plan(patient_id)
    schedule = client.get(f"/medication/{patient_id}/schedule", params={"date": "2026-03-07"}).json()

    for item in schedule["reminders"][:2]:
        client.post(
            f"/medication/{patient_id}/dose-confirmation",
            json={
                "schedule_entry_id": item["schedule_entry_id"],
                "scheduled_datetime": item["scheduled_datetime"],
                "dose_status": "skipped",
                "confirmed_at": "2026-03-07T12:30:00+00:00",
                "meal_condition_satisfied": False,
                "note": "missed",
            },
        )

    notifications = client.get(f"/medication/{patient_id}/notifications", params={"date": "2026-03-07"}).json()
    assert any(item["event_type"] == "repeated_missed_doses" for item in notifications)


def test_meal_rule_violation_on_critical_med() -> None:
    patient_id = "pilot_meal_violation"
    _setup_patient_plan(patient_id)
    schedule = client.get(f"/medication/{patient_id}/schedule", params={"date": "2026-03-07"}).json()
    first = schedule["reminders"][0]

    client.post(
        f"/medication/{patient_id}/dose-confirmation",
        json={
            "schedule_entry_id": first["schedule_entry_id"],
            "scheduled_datetime": first["scheduled_datetime"],
            "dose_status": "taken",
            "confirmed_at": "2026-03-07T08:05:00+00:00",
            "meal_condition_satisfied": False,
            "note": "taken without breakfast",
        },
    )

    notifications = client.get(f"/medication/{patient_id}/notifications", params={"date": "2026-03-07"}).json()
    assert any(item["event_type"] == "meal_rule_violation_critical_med" for item in notifications)


def test_concerning_symptom_checkin_triggers_clinician_review_recommendation() -> None:
    patient_id = "pilot_concerning_symptom"
    _setup_patient_plan(patient_id)

    client.post(
        f"/medication/{patient_id}/side-effect-checkin",
        json={
            "checkin_time": "2026-03-07T14:00:00+00:00",
            "feeling": "unwell",
            "dizziness": True,
            "breathlessness": False,
            "bleeding": False,
            "nausea": False,
            "weakness": False,
            "swelling": False,
            "chest_pain": False,
            "confusion": False,
            "near_fainting": False,
            "severe_weakness": False,
            "note": "lightheaded",
        },
    )

    alerts = client.get(f"/medication/{patient_id}/alerts", params={"date": "2026-03-07"}).json()
    assert any(item["category"] == "concerning_symptoms" for item in alerts)


def test_severe_symptom_triggers_emergency_escalation() -> None:
    patient_id = "pilot_emergency_symptom"
    _setup_patient_plan(patient_id)

    client.post(
        f"/medication/{patient_id}/side-effect-checkin",
        json={
            "checkin_time": "2026-03-07T15:00:00+00:00",
            "feeling": "very bad",
            "dizziness": False,
            "breathlessness": True,
            "bleeding": False,
            "nausea": False,
            "weakness": False,
            "swelling": False,
            "chest_pain": True,
            "confusion": False,
            "near_fainting": False,
            "severe_weakness": False,
            "note": "chest pain and sob",
        },
    )

    today = client.get(f"/medication/{patient_id}/today").json()
    assert "emergency_escalation" in today["caregiver_action_needed"]
    assert any(item["category"] == "emergency_symptoms" for item in today["symptom_alerts"])


def test_window_grouping_for_same_time_meds() -> None:
    patient_id = "pilot_windows"
    _setup_patient_plan(patient_id, clustered=True)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:10:00+00:00"})

    today = client.get(f"/medication/{patient_id}/today").json()
    windows = today["administration_windows"]
    window_0800 = next(item for item in windows if item["slot_time"] == "08:00")
    assert len(window_0800["meds"]) == 2


def test_critical_window_risk_classification() -> None:
    patient_id = "pilot_window_risk"
    _setup_patient_plan(patient_id, clustered=True)
    today = client.get(f"/medication/{patient_id}/today").json()
    window_0800 = next(item for item in today["administration_windows"] if item["slot_time"] == "08:00")
    assert window_0800["window_risk_level"] == "high"


def test_caregiver_action_recommendation_generation() -> None:
    patient_id = "pilot_actions"
    _setup_patient_plan(patient_id, clustered=True)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:10:00+00:00"})

    today = client.get(f"/medication/{patient_id}/today").json()
    action_types = [item["action_type"] for item in today["caregiver_actions"]]
    assert "remind_patient_now" in action_types
    assert "confirm_after_food" in action_types


def test_full_day_simulation_report_shape_and_ordering() -> None:
    patient_id = "pilot_report"
    _setup_patient_plan(patient_id, clustered=True)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T23:30:00+00:00"})

    report = client.get(
        f"/medication/{patient_id}/simulate-day-report",
        params={"date": "2026-03-07"},
    )
    assert report.status_code == 200
    body = report.json()
    assert "administration_windows" in body
    assert "caregiver_notifications" in body
    assert "top_caregiver_follow_up_items" in body
    slots = [item["slot_time"] for item in body["administration_windows"]]
    assert slots == sorted(slots)


def test_completed_vs_missed_window_status() -> None:
    patient_id = "pilot_window_status"
    _setup_patient_plan(patient_id, clustered=True)
    schedule = client.get(f"/medication/{patient_id}/schedule", params={"date": "2026-03-07"}).json()

    first_window_meds = [item for item in schedule["reminders"] if item["scheduled_datetime"].endswith("08:00:00+00:00")]
    for reminder in first_window_meds:
        client.post(
            f"/medication/{patient_id}/dose-confirmation",
            json={
                "schedule_entry_id": reminder["schedule_entry_id"],
                "scheduled_datetime": reminder["scheduled_datetime"],
                "dose_status": "taken",
                "confirmed_at": "2026-03-07T08:15:00+00:00",
                "meal_condition_satisfied": True,
                "note": "taken",
            },
        )

    report = client.get(
        f"/medication/{patient_id}/simulate-day-report",
        params={"date": "2026-03-07"},
    ).json()

    statuses = {item["slot_time"]: item["window_status"] for item in report["administration_windows"]}
    assert statuses["08:00"] == "completed"
    assert any(status == "overdue" for time, status in statuses.items() if time != "08:00")


def test_kolkata_local_time_serialization_in_today_and_due_now() -> None:
    patient_id = "tz_localization_case"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T06:45:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today")
    assert today.status_code == 200
    today_body = today.json()
    assert today_body["patient_timezone"] == "Asia/Kolkata"
    assert today_body["local_now"].endswith("+05:30")

    due_now = client.get(f"/medication/{patient_id}/due-now")
    assert due_now.status_code == 200
    due_now_body = due_now.json()
    assert due_now_body["patient_timezone"] == "Asia/Kolkata"
    assert due_now_body["local_now"].endswith("+05:30")
    if due_now_body["next_upcoming"] is not None:
        assert due_now_body["next_upcoming"]["local_scheduled_time"].endswith("+05:30")


def test_kolkata_scheduled_time_interpreted_as_local_wall_clock() -> None:
    patient_id = "tz_1230_local_wall_clock"
    _setup_kolkata_1230_patient_plan(patient_id)
    schedule = client.get(f"/medication/{patient_id}/schedule", params={"date": "2026-03-07"}).json()

    reminder = schedule["reminders"][0]
    assert reminder["local_scheduled_time"] == "2026-03-07T12:30:00+05:30"
    assert reminder["scheduled_datetime"] == "2026-03-07T07:00:00+00:00"


def test_kolkata_due_now_works_with_corrected_1230_time() -> None:
    patient_id = "tz_1230_due_now"
    _setup_kolkata_1230_patient_plan(patient_id)

    due_now = client.get(
        f"/medication/{patient_id}/due-now",
        params={"at": "2026-03-07T12:35:00+05:30"},
    )
    assert due_now.status_code == 200
    body = due_now.json()
    assert len(body["due_now"]) == 1
    assert body["due_now"][0]["local_scheduled_time"] == "2026-03-07T12:30:00+05:30"


def test_kolkata_send_due_reminders_uses_corrected_1230_window_time() -> None:
    patient_id = "tz_1230_send_due"
    _setup_kolkata_1230_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T12:35:00+05:30"})

    send = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert send.status_code == 200
    body = send.json()
    assert any(msg["window_slot_time"] == "12:30" for msg in body["sent_messages"])


def test_pre_first_dose_summary_does_not_show_misleading_zero_percent() -> None:
    patient_id = "tz_pre_dose_summary"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T06:45:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today").json()
    summary_text = today["end_of_day_summary"]["summary_text"]
    assert "No doses are due yet today" in summary_text
    assert "0%" not in summary_text


def test_0700_before_food_window_generates_correct_caregiver_action() -> None:
    patient_id = "tz_action_0700_before_food"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T07:05:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today").json()
    action_types = [item["action_type"] for item in today["caregiver_actions"]]
    assert "give_now_before_food" in action_types


def test_0800_critical_after_food_window_generates_correct_caregiver_action() -> None:
    patient_id = "tz_action_0800_critical_after_food"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today").json()
    action_types = [item["action_type"] for item in today["caregiver_actions"]]
    assert "critical_medication_window_due_now" in action_types
    assert "confirm_after_breakfast" in action_types


def test_overdue_critical_window_generates_urgent_caregiver_action() -> None:
    patient_id = "tz_action_overdue_critical"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:45:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today").json()
    action_types = [item["action_type"] for item in today["caregiver_actions"]]
    assert "overdue_critical_medication_window_follow_up_now" in action_types


def test_due_window_generates_outbound_reminder_message() -> None:
    patient_id = "msg_due_window"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T07:05:00+05:30"})

    response = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert response.status_code == 200
    body = response.json()
    assert len(body["sent_messages"]) >= 1
    assert any(msg["message_kind"] == "due_reminder" for msg in body["sent_messages"])


def test_repeated_due_reminder_run_does_not_duplicate_reminder() -> None:
    patient_id = "msg_due_idempotent"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T07:05:00+05:30"})

    first = client.post(f"/medication/{patient_id}/send-due-reminders")
    second = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["sent_messages"]) >= 1
    assert len(second.json()["sent_messages"]) == 0


def test_message_content_uses_local_time_and_grouped_meds() -> None:
    patient_id = "msg_group_content"
    _setup_patient_plan(patient_id, clustered=True)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+00:00"})

    response = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert response.status_code == 200
    messages = response.json()["sent_messages"]
    due_messages = [msg for msg in messages if msg["message_kind"] == "due_reminder" and msg["window_slot_time"] == "08:00"]
    assert len(due_messages) == 1
    content = due_messages[0]["content"]
    assert "08:00" in content
    assert "CardioMed-A" in content
    assert "CardioMed-D" in content


def test_taken_confirmation_marks_window_complete() -> None:
    patient_id = "msg_taken_complete"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T07:05:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today").json()
    window = next(item for item in today["administration_windows"] if item["slot_time"] == "07:00")
    confirm = client.post(
        f"/medication/{patient_id}/message-confirmation",
        json={"window_id": window["window_id"], "confirmation": "taken", "note": "done"},
    )
    assert confirm.status_code == 200

    today_after = client.get(f"/medication/{patient_id}/today").json()
    updated_window = next(item for item in today_after["administration_windows"] if item["slot_time"] == "07:00")
    assert updated_window["all_completed"] is True
    assert updated_window["window_status"] == "completed"


def test_delayed_and_skipped_update_workflow_correctly() -> None:
    patient_id = "msg_delayed_skipped"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:10:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today").json()
    window_0700 = next(item for item in today["administration_windows"] if item["slot_time"] == "07:00")
    window_0800 = next(item for item in today["administration_windows"] if item["slot_time"] == "08:00")

    delayed_response = client.post(
        f"/medication/{patient_id}/message-confirmation",
        json={"window_id": window_0700["window_id"], "confirmation": "delayed"},
    )
    assert delayed_response.status_code == 200

    skipped_response = client.post(
        f"/medication/{patient_id}/message-confirmation",
        json={"window_id": window_0800["window_id"], "confirmation": "skipped"},
    )
    assert skipped_response.status_code == 200

    today_after = client.get(f"/medication/{patient_id}/today").json()
    updated_0700 = next(item for item in today_after["administration_windows"] if item["slot_time"] == "07:00")
    updated_0800 = next(item for item in today_after["administration_windows"] if item["slot_time"] == "08:00")
    assert updated_0700["window_status"] == "completed"
    assert updated_0800["window_status"] in {"due", "overdue"}


def test_overdue_critical_window_creates_followup_event_message() -> None:
    patient_id = "msg_overdue_followup"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:45:00+05:30"})

    first_stage = client.post(f"/medication/{patient_id}/send-overdue-critical-followups")
    assert first_stage.status_code == 200
    first_messages = first_stage.json()["sent_messages"]
    assert len(first_messages) == 1
    assert first_messages[0]["message_kind"] == "overdue_followup"
    assert first_messages[0]["recipient_role"] == "caregiver"
    assert first_messages[0]["escalation_stage"] == 1

    # Immediate repeat should not duplicate stage-1.
    repeat = client.post(f"/medication/{patient_id}/send-overdue-critical-followups")
    assert repeat.status_code == 200
    assert repeat.json()["sent_messages"] == []

    # Advance beyond cooldown for stage-2 escalation.
    client.post("/medication/simulated-time/advance", json={"hours": 1, "minutes": 1})
    second_stage = client.post(f"/medication/{patient_id}/send-overdue-critical-followups")
    assert second_stage.status_code == 200
    second_messages = second_stage.json()["sent_messages"]
    assert len(second_messages) == 1
    assert second_messages[0]["escalation_stage"] == 2

    # No more stages beyond 2.
    client.post("/medication/simulated-time/advance", json={"hours": 2, "minutes": 0})
    third = client.post(f"/medication/{patient_id}/send-overdue-critical-followups")
    assert third.status_code == 200
    assert third.json()["sent_messages"] == []


def test_critical_window_escalation_respects_configured_threshold(monkeypatch) -> None:
    patient_id = "msg_overdue_threshold"
    _setup_kolkata_patient_plan(patient_id)
    monkeypatch.setenv("MEDICATION_CRITICAL_WINDOW_ESCALATION_MINUTES", "90")

    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:45:00+05:30"})
    before_threshold = client.post(f"/medication/{patient_id}/send-overdue-critical-followups")
    assert before_threshold.status_code == 200
    assert before_threshold.json()["sent_messages"] == []

    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T09:35:00+05:30"})
    after_threshold = client.post(f"/medication/{patient_id}/send-overdue-critical-followups")
    assert after_threshold.status_code == 200
    assert len(after_threshold.json()["sent_messages"]) == 1
    assert after_threshold.json()["sent_messages"][0]["message_kind"] == "overdue_followup"


def test_important_care_activity_escalates_after_configured_threshold(monkeypatch) -> None:
    patient_id = "care_important_threshold"
    _setup_patient_plan_with_care(patient_id)
    monkeypatch.setenv("MEDICATION_IMPORTANT_ACTIVITY_ESCALATION_MINUTES", "30")

    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:20:00+05:30"})
    before_threshold = client.get(f"/medication/{patient_id}/today").json()
    before_actions = [item["action_type"] for item in before_threshold["caregiver_actions"]]
    assert "important_care_activity_missed_follow_up" not in before_actions

    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:40:00+05:30"})
    after_threshold = client.get(f"/medication/{patient_id}/today").json()
    after_actions = [item["action_type"] for item in after_threshold["caregiver_actions"]]
    assert "important_care_activity_missed_follow_up" in after_actions


def test_mock_transport_stores_delivery_records_correctly() -> None:
    patient_id = "msg_delivery_records"
    _setup_kolkata_patient_plan(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T07:10:00+05:30"})

    client.post(f"/medication/{patient_id}/send-due-reminders")
    messages = client.get(
        f"/medication/{patient_id}/messages",
        params={"date": "2026-03-07"},
    )
    assert messages.status_code == 200
    body = messages.json()
    assert len(body) >= 1
    assert all(item["delivery_status"] == "delivered" for item in body)
    assert all(item["dedupe_key"] for item in body)
    assert len({item["dedupe_key"] for item in body}) == len(body)


def test_unified_daily_timeline_combines_medication_windows_and_care_activities() -> None:
    patient_id = "care_timeline_unified"
    _setup_patient_plan_with_care(patient_id)

    response = client.get(
        f"/medication/{patient_id}/daily-care-timeline",
        params={"date": "2026-03-07"},
    )
    assert response.status_code == 200
    body = response.json()
    item_types = {item["item_type"] for item in body["items"]}
    assert "medication_window" in item_types
    assert "care_activity" in item_types
    slots = [item["slot_time"] for item in body["items"]]
    assert slots == sorted(slots)


def test_send_due_reminders_includes_due_care_activity_messages() -> None:
    patient_id = "care_due_reminders"
    _setup_patient_plan_with_care(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    response = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert response.status_code == 200
    messages = response.json()["sent_messages"]
    assert any(item["message_kind"] == "care_activity_reminder" for item in messages)


def test_care_activity_confirmation_done_marks_activity_completed() -> None:
    patient_id = "care_confirm_done"
    _setup_patient_plan_with_care(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:10:00+05:30"})

    today = client.get(f"/medication/{patient_id}/today").json()
    instance = next(item for item in today["care_activities_due_now"] if item["activity_id"] == "breakfast_0800")
    confirm = client.post(
        f"/medication/{patient_id}/care-activity-confirmation",
        json={"instance_id": instance["instance_id"], "confirmation": "done"},
    )
    assert confirm.status_code == 200

    after = client.get(f"/medication/{patient_id}/today").json()
    updated = next(
        item
        for item in after["unified_daily_plan"]["items"]
        if item["item_type"] == "care_activity" and item["item_id"] == instance["instance_id"]
    )
    assert updated["status"] == "completed"
