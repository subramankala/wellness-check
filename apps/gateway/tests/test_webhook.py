from fastapi.testclient import TestClient

from gateway_app.main import app


def test_twilio_voice_webhook_valid_request() -> None:
    client = TestClient(app)
    response = client.post(
        "/webhooks/twilio/voice",
        json={
            "call_sid": "CA123456",
            "from_number": "+15550001111",
            "to_number": "+15550002222",
            "caller_language": "en",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["protocol_id"] == "post_op_fever_v1"
    assert body["channel"] == "twilio_voice"
    assert body["session_id"] == "sess_CA123456"
    assert body["request_id"].startswith("req_")


def test_twilio_voice_webhook_invalid_request() -> None:
    client = TestClient(app)
    response = client.post(
        "/webhooks/twilio/voice",
        json={
            "from_number": "+15550001111",
            "to_number": "+15550002222",
        },
    )

    assert response.status_code == 422
