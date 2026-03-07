from fastapi.testclient import TestClient

from voice_runtime_app.main import app


def _base_request() -> dict:
    return {
        "session": {
            "request_id": "req_1",
            "session_id": "sess_1",
            "channel": "twilio_voice",
            "protocol_id": "post_op_fever_v1",
            "caller_language": "en",
            "caller_id": "+15550001111",
            "metadata": {"call_sid": "CA123"},
        },
        "symptom_input": {
            "patient_id": "p-100",
            "protocol_id": "post_op_fever_v1",
            "chief_complaint": "post op fever",
            "symptom_summary": "mild fever",
            "observed_signals": [],
            "answers": {
                "fever_temp_f": "100.4",
                "postop_day": "3",
                "wound_appearance": "clean and dry",
            },
        },
        "turns": [],
    }


def test_mild_stable_post_op_fever() -> None:
    client = TestClient(app)
    payload = _base_request()
    payload["symptom_input"]["symptom_summary"] = "mild fever improving"
    payload["symptom_input"]["observed_signals"] = ["low grade fever"]

    response = client.post("/runtime/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["safety_result"]["severity_level"] == "normal"
    assert body["final_disposition"] in {"self_care", "callback"}


def test_fever_wound_redness_urgent() -> None:
    client = TestClient(app)
    payload = _base_request()
    payload["symptom_input"]["symptom_summary"] = "persistent fever with wound redness"
    payload["symptom_input"]["observed_signals"] = ["wound redness", "persistent fever"]
    payload["symptom_input"]["answers"]["wound_appearance"] = "redness around incision"

    response = client.post("/runtime/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["safety_result"]["severity_level"] == "urgent"
    assert body["final_disposition"] == "urgent_nurse_handoff"


def test_severe_shortness_of_breath_emergency() -> None:
    client = TestClient(app)
    payload = _base_request()
    payload["symptom_input"]["symptom_summary"] = "severe shortness of breath after surgery"

    response = client.post("/runtime/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["safety_result"]["severity_level"] == "emergency"
    assert body["final_disposition"] == "emergency_instruction"


def test_incomplete_intake_returns_next_required_question() -> None:
    client = TestClient(app)
    payload = _base_request()
    payload["symptom_input"]["answers"] = {"fever_temp_f": "100.1"}

    response = client.post("/runtime/evaluate", json=payload)
    assert response.status_code == 200
    body = response.json()

    assert body["triage_result"]["ready_for_disposition"] is False
    assert body["final_disposition"] is None
    assert body["next_required_question"]["key"] == "postop_day"


def test_handoff_payload_shape_for_urgent_case() -> None:
    client = TestClient(app)
    payload = _base_request()
    payload["symptom_input"]["symptom_summary"] = "worsening pain and wound redness"
    payload["symptom_input"]["observed_signals"] = ["wound redness", "worsening pain"]

    response = client.post("/runtime/evaluate", json=payload)
    assert response.status_code == 200
    handoff = response.json()["handoff_payload"]

    assert handoff is not None
    assert handoff["handoff_required"] is True
    assert handoff["destination"] == "urgent_nurse_queue"
    assert handoff["priority"] == "urgent"


def test_documentation_payload_shape_for_emergency_case() -> None:
    client = TestClient(app)
    payload = _base_request()
    payload["symptom_input"]["symptom_summary"] = "patient is confused and has chest pain"

    response = client.post("/runtime/evaluate", json=payload)
    assert response.status_code == 200
    docs = response.json()["documentation_payload"]

    assert "clinician_summary" in docs
    assert "patient_summary" in docs
    assert docs["structured_note"]["final_disposition"] == "emergency_instruction"
