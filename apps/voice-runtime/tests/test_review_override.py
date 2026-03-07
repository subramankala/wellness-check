from fastapi.testclient import TestClient

from voice_runtime_app.main import app


client = TestClient(app)


def _start_payload(session_id: str) -> dict:
    return {
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


def _emergency_turn(session_id: str) -> None:
    client.post(
        "/runtime/session/turn",
        json={
            "session_id": session_id,
            "turn": {"speaker": "patient", "text": "cannot breathe"},
            "utterance_input": {
                "utterance_text": "I can't breathe properly",
                "session_id": session_id,
                "protocol_id": "post_op_fever_v1",
            },
        },
    )


def test_session_list_returns_active_and_completed_sessions() -> None:
    active_id = "sess_review_active"
    complete_id = "sess_review_complete"

    client.post("/runtime/session/start", json=_start_payload(active_id))
    client.post("/runtime/session/start", json=_start_payload(complete_id))
    _emergency_turn(complete_id)

    response = client.get("/runtime/sessions")
    assert response.status_code == 200
    rows = response.json()
    ids = {row["session_id"] for row in rows}
    assert active_id in ids
    assert complete_id in ids


def test_session_detail_returns_audit_history() -> None:
    session_id = "sess_review_detail"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    response = client.get(f"/runtime/session/{session_id}/detail")
    assert response.status_code == 200
    detail = response.json()
    events = detail["session_state"]["audit_events"]
    assert len(events) >= 3
    event_types = [event["event_type"] for event in events]
    assert "session_started" in event_types


def test_override_requires_rationale_and_reviewer_id() -> None:
    session_id = "sess_review_validate"
    client.post("/runtime/session/start", json=_start_payload(session_id))
    _emergency_turn(session_id)

    response = client.post(
        f"/runtime/session/{session_id}/override",
        json={
            "reviewer_id": "",
            "reviewer_name": "Dr A",
            "new_disposition": "urgent_nurse_handoff",
            "rationale": "",
            "human_takeover": True,
        },
    )
    assert response.status_code == 400


def test_override_preserves_machine_recommendation_and_sets_effective() -> None:
    session_id = "sess_review_override"
    client.post("/runtime/session/start", json=_start_payload(session_id))
    _emergency_turn(session_id)

    response = client.post(
        f"/runtime/session/{session_id}/override",
        json={
            "reviewer_id": "u123",
            "reviewer_name": "Dr Smith",
            "new_disposition": "urgent_nurse_handoff",
            "rationale": "Patient stabilized after immediate intervention",
            "human_takeover": True,
        },
    )
    assert response.status_code == 200
    state = response.json()["session_state"]
    assert state["machine_recommended_disposition"] == "emergency_instruction"
    assert state["final_effective_disposition"] == "urgent_nurse_handoff"


def test_override_creates_updated_handoff_and_documentation_versions() -> None:
    session_id = "sess_review_versions"
    client.post("/runtime/session/start", json=_start_payload(session_id))
    _emergency_turn(session_id)

    before = client.get(f"/runtime/session/{session_id}/detail").json()["session_state"]
    assert len(before["handoff_versions"]) == 1
    assert len(before["documentation_versions"]) == 1

    after = client.post(
        f"/runtime/session/{session_id}/override",
        json={
            "reviewer_id": "u124",
            "reviewer_name": "Dr Lee",
            "new_disposition": "urgent_nurse_handoff",
            "rationale": "Down-triage based on bedside reassessment",
            "human_takeover": True,
        },
    ).json()["session_state"]

    assert len(after["handoff_versions"]) == 2
    assert len(after["documentation_versions"]) == 2
    assert after["handoff_versions"][1]["supersedes_version"] == 1
    assert after["documentation_versions"][1]["supersedes_version"] == 1


def test_downward_override_recorded_with_audit_event() -> None:
    session_id = "sess_review_down"
    client.post("/runtime/session/start", json=_start_payload(session_id))
    _emergency_turn(session_id)

    detail = client.post(
        f"/runtime/session/{session_id}/override",
        json={
            "reviewer_id": "u125",
            "reviewer_name": "Dr Ray",
            "new_disposition": "callback",
            "rationale": "Symptoms resolved after direct exam and vitals normal",
            "human_takeover": True,
        },
    ).json()["session_state"]

    assert detail["override_record"]["acuity_change"] == "down"
    events = detail["audit_events"]
    override_events = [event for event in events if event["event_type"] == "human_override_applied"]
    assert len(override_events) >= 1


def test_review_status_transitions_reflected_in_session_detail() -> None:
    session_id = "sess_review_status"
    client.post("/runtime/session/start", json=_start_payload(session_id))

    client.post(
        f"/runtime/session/{session_id}/review-status",
        json={
            "reviewer_id": "u200",
            "reviewer_name": "RN One",
            "review_status": "in_review",
            "note": "Opened chart",
        },
    )
    client.post(
        f"/runtime/session/{session_id}/review-status",
        json={
            "reviewer_id": "u200",
            "reviewer_name": "RN One",
            "review_status": "resolved",
            "note": "Closed",
        },
    )

    detail = client.get(f"/runtime/session/{session_id}/detail").json()
    assert detail["summary"]["review_status"] == "resolved"
