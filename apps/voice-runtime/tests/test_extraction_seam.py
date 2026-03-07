from fastapi.testclient import TestClient

from voice_runtime_app.main import app


client = TestClient(app)


def _start_payload(session_id: str, initial_symptom_input: dict | None = None) -> dict:
    payload = {
        "session": {
            "request_id": f"req_{session_id}",
            "session_id": session_id,
            "channel": "twilio_voice",
            "protocol_id": "post_op_fever_v1",
            "caller_language": "en",
            "caller_id": "+15550001111",
            "metadata": {"call_sid": f"CA_{session_id}"},
        }
    }
    if initial_symptom_input is not None:
        payload["initial_symptom_input"] = initial_symptom_input
    return payload


def _utterance_turn(session_id: str, text: str) -> dict:
    return {
        "session_id": session_id,
        "turn": {"speaker": "patient", "text": text},
        "utterance_input": {"utterance_text": text, "session_id": session_id, "protocol_id": "post_op_fever_v1"},
    }


def test_utterance_fever_since_yesterday_extracts_fields() -> None:
    session_id = "sess_ext_1"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    response = client.post(
        "/runtime/session/turn",
        json=_utterance_turn(session_id, "I have fever since yesterday"),
    )
    assert response.status_code == 200
    body = response.json()

    extracted = body["session_state"]["latest_extraction_result"]
    assert extracted is not None
    assert any(field["field_path"] == "observed_signals" and field["value"] == "fever" for field in extracted["extracted_fields"])
    assert body["session_state"]["symptom_input"]["answers"]["onset_hint"] == "since yesterday"


def test_utterance_wound_red_triggers_urgent_path() -> None:
    session_id = "sess_ext_2"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    response = client.post(
        "/runtime/session/turn",
        json=_utterance_turn(session_id, "my wound is red"),
    )
    assert response.status_code == 200
    body = response.json()

    assert body["session_state"]["latest_safety_result"]["severity_level"] == "urgent"


def test_utterance_cant_breathe_triggers_emergency_path() -> None:
    session_id = "sess_ext_3"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    response = client.post(
        "/runtime/session/turn",
        json=_utterance_turn(session_id, "I can't breathe properly"),
    )
    assert response.status_code == 200
    body = response.json()

    assert body["session_state"]["latest_safety_result"]["severity_level"] == "emergency"
    assert body["final_disposition"] == "emergency_instruction"


def test_mixed_turn_merges_structured_and_utterance() -> None:
    session_id = "sess_ext_4"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    payload = _utterance_turn(session_id, "fever 101 since yesterday")
    payload["symptom_update"] = {
        "answers": {"fever_temp_f": "99.9", "postop_day": "4"},
        "observed_signals": ["low grade fever"],
    }

    response = client.post("/runtime/session/turn", json=payload)
    assert response.status_code == 200
    body = response.json()

    answers = body["session_state"]["symptom_input"]["answers"]
    assert answers["fever_temp_f"] == "99.9"
    assert answers["postop_day"] == "4"
    assert "fever" in body["session_state"]["symptom_input"]["observed_signals"]


def test_low_information_utterance_does_not_overwrite_known_fields() -> None:
    session_id = "sess_ext_5"
    start = _start_payload(
        session_id,
        {
            "patient_id": "p-5",
            "protocol_id": "post_op_fever_v1",
            "chief_complaint": "post op fever",
            "symptom_summary": "known summary",
            "observed_signals": [],
            "answers": {"fever_temp_f": "101.2"},
        },
    )
    client.post("/runtime/session/start", json=start)

    response = client.post(
        "/runtime/session/turn",
        json=_utterance_turn(session_id, "okay"),
    )
    assert response.status_code == 200
    body = response.json()

    symptom_input = body["session_state"]["symptom_input"]
    assert symptom_input["symptom_summary"] == "known summary"
    assert symptom_input["answers"]["fever_temp_f"] == "101.2"


def test_extraction_results_stored_in_state_history() -> None:
    session_id = "sess_ext_6"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    client.post("/runtime/session/turn", json=_utterance_turn(session_id, "I have fever"))
    response = client.post("/runtime/session/turn", json=_utterance_turn(session_id, "my wound is red"))

    assert response.status_code == 200
    body = response.json()
    history = body["session_state"]["extraction_history"]
    assert len(history) >= 2
    assert history[-1]["utterance_text"] == "my wound is red"


def test_runtime_extract_endpoint_returns_deterministic_output() -> None:
    response = client.post(
        "/runtime/extract",
        json={
            "utterance_text": "fever 102 and wound is red",
            "protocol_id": "post_op_fever_v1",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "utterance_text"
    field_paths = [item["field_path"] for item in body["extracted_fields"]]
    assert "answers.fever_temp_f" in field_paths
    assert "answers.wound_appearance" in field_paths
