from fastapi.testclient import TestClient

from medication_workflow.main import app


client = TestClient(app)


def _patient_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "display_name": "CareOS Patient",
        "timezone": "Asia/Kolkata",
        "patient_contact": "+919999030001",
        "caregiver_name": "Caregiver",
        "caregiver_contact": "+919999030002",
        "created_at": "2026-03-07T06:00:00+05:30",
        "notes": "care os tests",
    }


def _plan_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "plan_id": f"plan_{patient_id}",
        "workflow_status": "active",
        "timezone": "Asia/Kolkata",
        "created_at": "2026-03-07T06:00:00+05:30",
        "medications": [
            {
                "entry_id": "critical_0800",
                "display_name": "Critical Med",
                "generic_name": "test",
                "medication_name": "CriticalMed",
                "dose_instructions": "1 tablet after food",
                "scheduled_time": "08:00",
                "meal_constraint": "after_meal",
                "priority": "critical",
                "criticality_level": "critical",
                "monitoring_notes": "",
                "missed_dose_policy": "notify caregiver",
                "side_effect_watch_items": [],
            }
        ],
        "care_activities": [
            {
                "activity_id": "breakfast_0800",
                "title": "Breakfast",
                "category": "meal",
                "schedule": "08:00",
                "duration_minutes": 20,
                "instruction": "Have breakfast",
                "frequency": "daily",
                "priority": "important",
                "confirmation_required": True,
                "escalation_policy": "follow up",
            },
            {
                "activity_id": "bp_0900",
                "title": "BP Check",
                "category": "vitals_check",
                "schedule": "09:00",
                "duration_minutes": 10,
                "instruction": "Check blood pressure",
                "frequency": "daily",
                "priority": "important",
                "confirmation_required": True,
                "escalation_policy": "follow up",
            },
        ],
    }


def _setup(patient_id: str) -> None:
    client.post("/medication/patient", json=_patient_payload(patient_id))
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_plan_payload(patient_id))
    assert response.status_code == 200


def test_careos_today_timeline_aggregation() -> None:
    patient_id = "careos_today_agg"
    _setup(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    response = client.get(f"/careos/{patient_id}/today")
    assert response.status_code == 200
    body = response.json()
    assert body["timeline"]["items"]
    item_types = {item["item_type"] for item in body["timeline"]["items"]}
    assert "medication_window" in item_types
    assert "care_activity" in item_types


def test_restricted_med_edit_protection() -> None:
    patient_id = "careos_med_guard"
    _setup(patient_id)

    today = client.get(f"/careos/{patient_id}/today").json()
    med_item = next(item for item in today["timeline"]["items"] if item["item_type"] == "medication_window")

    blocked = client.post(
        f"/careos/{patient_id}/timeline/{med_item['item_id']}/skip",
        json={"reason": "test", "allow_high_risk_medication_edit": False},
    )
    assert blocked.status_code == 403



def test_symptom_escalation_routing() -> None:
    patient_id = "careos_symptom"
    _setup(patient_id)

    response = client.post(
        f"/careos/{patient_id}/symptom-checkin",
        json={
            "checkin_time": "2026-03-07T10:00:00+05:30",
            "feeling": "bad",
            "chest_pain": True,
            "breathlessness": True,
            "dizziness": False,
            "swelling": False,
            "confusion": False,
            "severe_weakness": False,
            "bleeding": False,
            "note": "urgent symptoms",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["escalation_level"] in {
        "urgent_symptom_triage_recommended",
        "emergency_escalation",
    }



def test_caregiver_summary_rendering() -> None:
    patient_id = "careos_summary"
    _setup(patient_id)

    response = client.get(f"/careos/{patient_id}/summary", params={"date": "2026-03-07"})
    assert response.status_code == 200
    body = response.json()
    assert "caregiver_summary_text" in body
    assert "medication_adherence_summary" in body
    assert isinstance(body["symptom_escalation_flags"], list)
