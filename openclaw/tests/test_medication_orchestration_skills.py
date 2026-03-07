from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from medication_workflow.main import app

ROOT = Path(__file__).resolve().parents[2]
DISPATCH_PATH = ROOT / "openclaw/skills/dispatch-due-medication-windows/scripts/run.py"
OVERDUE_PATH = ROOT / "openclaw/skills/check-overdue-critical-doses/scripts/run.py"
SUMMARY_PATH = ROOT / "openclaw/skills/send-caregiver-daily-summary/scripts/run.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _patient_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "display_name": "Kolkata Patient",
        "timezone": "Asia/Kolkata",
        "caregiver_name": "Caregiver",
        "caregiver_contact": "+911234567890",
        "created_at": "2026-03-07T06:30:00+05:30",
        "notes": "Timezone test patient",
    }


def _plan_payload(patient_id: str) -> dict:
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


def _setup(client: TestClient, patient_id: str) -> None:
    client.post("/medication/patient", json=_patient_payload(patient_id))
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_plan_payload(patient_id))
    assert response.status_code == 200


def _patch_request_json(module, client: TestClient):
    def _call(url: str, *, method: str = "GET", payload=None):
        path = url.split("http://local")[-1].split("http://localhost:8105")[-1]
        if method == "POST":
            response = client.post(path, json=payload)
        else:
            response = client.get(path)
        assert response.status_code == 200, response.text
        return response.json()

    module._request_json = _call


def test_dispatch_due_skill_sends_reminder_and_is_idempotent() -> None:
    client = TestClient(app)
    patient_id = "oc_dispatch"
    _setup(client, patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T07:05:00+05:30"})

    dispatch = _load_module(DISPATCH_PATH, "dispatch_skill")
    _patch_request_json(dispatch, client)

    first = dispatch.run("http://localhost:8105", patient_id)
    second = dispatch.run("http://localhost:8105", patient_id)

    assert first["sent_count"] >= 1
    assert second["sent_count"] == 0


def test_overdue_skill_sends_followup_once_per_stage() -> None:
    client = TestClient(app)
    patient_id = "oc_overdue"
    _setup(client, patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:45:00+05:30"})

    overdue = _load_module(OVERDUE_PATH, "overdue_skill")
    _patch_request_json(overdue, client)

    first = overdue.run("http://localhost:8105", patient_id, 60)
    assert first["sent_count"] == 1
    assert first["sent_messages"][0]["escalation_stage"] == 1

    second = overdue.run("http://localhost:8105", patient_id, 60)
    assert second["sent_count"] == 0

    client.post("/medication/simulated-time/advance", json={"hours": 1, "minutes": 1})
    third = overdue.run("http://localhost:8105", patient_id, 60)
    assert third["sent_count"] == 1
    assert third["sent_messages"][0]["escalation_stage"] == 2


def test_daily_summary_skill_generates_digest_structure(tmp_path: Path) -> None:
    client = TestClient(app)
    patient_id = "oc_summary"
    _setup(client, patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T06:45:00+05:30"})

    summary = _load_module(SUMMARY_PATH, "summary_skill")

    def _call(url: str):
        path = url.split("http://localhost:8105")[-1]
        response = client.get(path)
        assert response.status_code == 200
        return response.json()

    summary._request_json = _call

    output = summary.run(
        "http://localhost:8105",
        patient_id,
        "2026-03-07",
        str(tmp_path / "digest.json"),
    )
    digest = output["digest"]
    assert "progress" in digest
    assert "summary_text" in digest
    assert "recommended_actions" in digest
