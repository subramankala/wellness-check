from fastapi.testclient import TestClient

from voice_runtime_app.main import app


client = TestClient(app)


def _start_payload(session_id: str, request_id: str = "req_1") -> dict:
    return {
        "session": {
            "request_id": request_id,
            "session_id": session_id,
            "channel": "twilio_voice",
            "protocol_id": "post_op_fever_v1",
            "caller_language": "en",
            "caller_id": "+15550001111",
            "metadata": {"call_sid": f"CA_{session_id}"},
        }
    }


def _turn_payload(session_id: str, text: str, symptom_update: dict | None = None) -> dict:
    payload: dict = {
        "session_id": session_id,
        "turn": {
            "speaker": "patient",
            "text": text,
        },
    }
    if symptom_update is not None:
        payload["symptom_update"] = symptom_update
    return payload


def test_session_start_returns_first_required_question() -> None:
    session_id = "sess_sm_1"
    response = client.post("/runtime/session/start", json=_start_payload(session_id))

    assert response.status_code == 200
    body = response.json()
    assert body["session_state"]["status"] == "active"
    assert body["next_required_question"]["key"] == "fever_temp_f"


def test_multi_turn_mild_case_reaches_final_only_after_answers() -> None:
    session_id = "sess_sm_2"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    first_turn = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "I have mild fever",
            {
                "symptom_summary": "mild fever improving",
                "observed_signals": ["low grade fever"],
                "answers": {"fever_temp_f": "100.2"},
            },
        ),
    )
    assert first_turn.status_code == 200
    assert first_turn.json()["final_disposition"] is None

    second_turn = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "It is day 3 after surgery",
            {"answers": {"postop_day": "3"}},
        ),
    )
    assert second_turn.status_code == 200
    assert second_turn.json()["final_disposition"] is None

    third_turn = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "Wound looks clean",
            {"answers": {"wound_appearance": "clean and dry"}},
        ),
    )
    body = third_turn.json()
    assert third_turn.status_code == 200
    assert body["session_state"]["status"] == "completed"
    assert body["final_disposition"] in {"self_care", "callback"}


def test_urgent_case_escalates_when_wound_redness_appears() -> None:
    session_id = "sess_sm_3"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "Fever started",
            {"answers": {"fever_temp_f": "101.8", "postop_day": "5"}},
        ),
    )

    response = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "Now there is wound redness",
            {
                "symptom_summary": "persistent fever with wound redness",
                "observed_signals": ["wound redness", "persistent fever"],
                "answers": {"wound_appearance": "redness around incision"},
            },
        ),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_state"]["latest_safety_result"]["severity_level"] == "urgent"
    assert body["final_disposition"] == "urgent_nurse_handoff"


def test_emergency_case_interrupts_flow_immediately() -> None:
    session_id = "sess_sm_4"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    response = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "I have severe shortness of breath",
            {"symptom_summary": "severe shortness of breath"},
        ),
    )
    body = response.json()

    assert response.status_code == 200
    assert body["session_state"]["status"] == "completed"
    assert body["session_state"]["latest_safety_result"]["severity_level"] == "emergency"
    assert body["final_disposition"] == "emergency_instruction"


def test_completed_session_does_not_change_disposition_on_extra_turns() -> None:
    session_id = "sess_sm_5"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    first = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "I feel confused",
            {"symptom_summary": "confusion and chest pain"},
        ),
    ).json()
    locked = first["final_disposition"]

    second = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "Actually maybe mild",
            {"symptom_summary": "mild fever only", "answers": {"fever_temp_f": "99.8"}},
        ),
    ).json()

    assert locked == "emergency_instruction"
    assert second["final_disposition"] == locked
    assert second["disposition_locked_this_turn"] is False


def test_reset_clears_progress_and_allows_re_evaluation() -> None:
    session_id = "sess_sm_6"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "I have severe shortness of breath",
            {"symptom_summary": "severe shortness of breath"},
        ),
    )

    reset = client.post(f"/runtime/session/{session_id}/reset")
    body = reset.json()

    assert reset.status_code == 200
    assert body["session_state"]["status"] == "active"
    assert body["session_state"]["disposition_lock"] is None
    assert body["session_state"]["question_progress"]["answered_questions"] == []
    assert body["next_required_question"]["key"] == "fever_temp_f"


def test_handoff_and_documentation_created_exactly_once() -> None:
    session_id = "sess_sm_7"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    first = client.post(
        "/runtime/session/turn",
        json=_turn_payload(
            session_id,
            "Severe breathing problem",
            {"symptom_summary": "severe shortness of breath"},
        ),
    ).json()

    second = client.post(
        "/runtime/session/turn",
        json=_turn_payload(session_id, "extra turn after completion"),
    ).json()

    assert first["session_state"]["handoff_payload"] is not None
    assert first["session_state"]["documentation_payload"] is not None
    assert second["session_state"]["handoff_payload"] == first["session_state"]["handoff_payload"]
    assert second["session_state"]["documentation_payload"] == first["session_state"]["documentation_payload"]
