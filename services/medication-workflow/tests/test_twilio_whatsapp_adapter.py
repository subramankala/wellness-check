from __future__ import annotations

import os
from types import SimpleNamespace

from fastapi.testclient import TestClient

import medication_workflow.main as main_module
from medication_workflow.transport import (
    OutboundMessageRequest,
    WhatsAppMessageTransport,
    normalize_confirmation_text,
)
from shared_types import ChannelType, MessageKind, RecipientRole


client = TestClient(main_module.app)


def _patient_payload(patient_id: str) -> dict:
    return {
        "patient_id": patient_id,
        "display_name": "Twilio Patient",
        "timezone": "Asia/Kolkata",
        "patient_contact": "+919999000001",
        "caregiver_name": "Twilio Caregiver",
        "caregiver_contact": "+919999000002",
        "created_at": "2026-03-07T06:00:00+05:30",
        "notes": "twilio webhook test",
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
    }


def _setup(patient_id: str) -> None:
    client.post("/medication/patient", json=_patient_payload(patient_id))
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_plan_payload(patient_id))
    assert response.status_code == 200


class _FakeTwilioMessages:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(sid=f"SM{len(self.calls):03d}", status="queued")


class _FakeTwilioClient:
    def __init__(self) -> None:
        self.messages = _FakeTwilioMessages()


def test_outbound_whatsapp_payload_generation(monkeypatch) -> None:
    patient_id = "twilio_outbound"
    _setup(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    fake_client = _FakeTwilioClient()
    transport = WhatsAppMessageTransport(
        account_sid="AC123",
        auth_token="token",
        whatsapp_sender="+14155238886",
        callback_base_url="https://example.ngrok-free.app",
        sandbox_mode=True,
        client=fake_client,
    )
    monkeypatch.setattr(main_module, "MESSAGE_TRANSPORT", transport)

    sent = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert sent.status_code == 200
    sent_body = sent.json()
    assert len(sent_body["sent_messages"]) == 1
    msg = sent_body["sent_messages"][0]
    assert msg["channel_type"] == "whatsapp"
    assert msg["message_id"].startswith("SM")
    assert fake_client.messages.calls[0]["from_"] == "whatsapp:+14155238886"
    assert fake_client.messages.calls[0]["to"] == "whatsapp:+919999000001"


def test_session_window_routing_uses_free_form_body(monkeypatch) -> None:
    fake_client = _FakeTwilioClient()
    monkeypatch.setenv("TWILIO_WHATSAPP_ROUTING_MODE", "auto")
    transport = WhatsAppMessageTransport(
        account_sid="AC123",
        auth_token="token",
        whatsapp_sender="+14155238886",
        callback_base_url="https://example.ngrok-free.app",
        sandbox_mode=True,
        client=fake_client,
    )
    request = OutboundMessageRequest(
        patient_id="p1",
        date="2026-03-07",
        window_id="w1",
        window_slot_time="08:00",
        recipient_role=RecipientRole.PATIENT,
        recipient_address="+919999000001",
        channel_type=ChannelType.WHATSAPP,
        message_kind=MessageKind.DUE_REMINDER,
        content="08:00 reminder",
        dedupe_key="k1",
        escalation_stage=None,
        metadata={"last_customer_message_at": "2026-03-07T07:30:00+00:00"},
    )
    msg = transport.send_message(request)
    assert "body" in fake_client.messages.calls[0]
    assert "content_sid" not in fake_client.messages.calls[0]
    assert msg.metadata["message_route"] == "session"


def test_template_routing_fallback_in_sandbox_when_template_missing(monkeypatch) -> None:
    fake_client = _FakeTwilioClient()
    monkeypatch.setenv("TWILIO_WHATSAPP_ROUTING_MODE", "template_only")
    monkeypatch.delenv("TWILIO_WHATSAPP_TEMPLATE_DUE_REMINDER_SID", raising=False)
    transport = WhatsAppMessageTransport(
        account_sid="AC123",
        auth_token="token",
        whatsapp_sender="+14155238886",
        callback_base_url="https://example.ngrok-free.app",
        sandbox_mode=True,
        client=fake_client,
    )
    request = OutboundMessageRequest(
        patient_id="p1",
        date="2026-03-07",
        window_id="w1",
        window_slot_time="08:00",
        recipient_role=RecipientRole.PATIENT,
        recipient_address="+919999000001",
        channel_type=ChannelType.WHATSAPP,
        message_kind=MessageKind.DUE_REMINDER,
        content="08:00 reminder",
        dedupe_key="k1",
        escalation_stage=None,
        metadata={},
    )
    msg = transport.send_message(request)
    assert msg.metadata["message_route"] == "session_fallback_sandbox"
    assert "body" in fake_client.messages.calls[0]


def test_template_routing_uses_content_sid_when_configured(monkeypatch) -> None:
    fake_client = _FakeTwilioClient()
    monkeypatch.setenv("TWILIO_WHATSAPP_ROUTING_MODE", "template_only")
    monkeypatch.setenv("TWILIO_WHATSAPP_TEMPLATE_DUE_REMINDER_SID", "HX_TEMPLATE_DUE")
    transport = WhatsAppMessageTransport(
        account_sid="AC123",
        auth_token="token",
        whatsapp_sender="+14155238886",
        callback_base_url="https://example.ngrok-free.app",
        sandbox_mode=False,
        client=fake_client,
    )
    request = OutboundMessageRequest(
        patient_id="p1",
        date="2026-03-07",
        window_id="w1",
        window_slot_time="08:00",
        recipient_role=RecipientRole.PATIENT,
        recipient_address="+919999000001",
        channel_type=ChannelType.WHATSAPP,
        message_kind=MessageKind.DUE_REMINDER,
        content="08:00 reminder",
        dedupe_key="k1",
        escalation_stage=None,
        metadata={},
    )
    msg = transport.send_message(request)
    assert "content_sid" in fake_client.messages.calls[0]
    assert fake_client.messages.calls[0]["content_sid"] == "HX_TEMPLATE_DUE"
    assert msg.metadata["message_route"] == "template"


def test_reply_normalization_variants() -> None:
    assert normalize_confirmation_text("yes") == "TAKEN"
    assert normalize_confirmation_text("done") == "TAKEN"
    assert normalize_confirmation_text("taken done") == "TAKEN"
    assert normalize_confirmation_text("delayed 10 min") == "DELAYED"
    assert normalize_confirmation_text("skipped today") == "SKIPPED"
    assert normalize_confirmation_text("not taken") == "SKIPPED"
    assert normalize_confirmation_text("unknown words") == ""


def test_inbound_taken_reply_maps_to_confirmation(monkeypatch) -> None:
    patient_id = "twilio_inbound_taken"
    _setup(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")
    client.post(f"/medication/{patient_id}/send-due-reminders")

    inbound = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": "whatsapp:+919999000001", "Body": "TAKEN"},
    )
    assert inbound.status_code == 200
    assert "confirmation recorded" in inbound.text

    today = client.get(f"/medication/{patient_id}/today").json()
    window = next(item for item in today["administration_windows"] if item["slot_time"] == "08:00")
    assert window["window_status"] == "completed"


def test_inbound_unknown_reply_gets_safe_fallback(monkeypatch) -> None:
    patient_id = "twilio_inbound_unknown"
    _setup(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")
    client.post(f"/medication/{patient_id}/send-due-reminders")

    inbound = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": "whatsapp:+919999000001", "Body": "WHAT"},
    )
    assert inbound.status_code == 200
    assert "Unrecognized reply" in inbound.text


def test_delivery_status_callback_updates_message_state(monkeypatch) -> None:
    patient_id = "twilio_status"
    _setup(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    fake_client = _FakeTwilioClient()
    transport = WhatsAppMessageTransport(
        account_sid="AC123",
        auth_token="token",
        whatsapp_sender="+14155238886",
        callback_base_url="https://example.ngrok-free.app",
        sandbox_mode=True,
        client=fake_client,
    )
    monkeypatch.setattr(main_module, "MESSAGE_TRANSPORT", transport)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    sent = client.post(f"/medication/{patient_id}/send-due-reminders").json()
    sid = sent["sent_messages"][0]["message_id"]

    status = client.post(
        "/webhooks/twilio/whatsapp/status",
        data={"MessageSid": sid, "MessageStatus": "delivered"},
    )
    assert status.status_code == 200

    messages = client.get(f"/medication/{patient_id}/messages", params={"date": "2026-03-07"}).json()
    matched = [item for item in messages if item["message_id"] == sid][0]
    assert matched["delivery_status"] == "delivered"


def test_invalid_webhook_signature_rejected(monkeypatch) -> None:
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "true")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": "whatsapp:+919999000001", "Body": "TAKEN"},
    )
    assert response.status_code == 403


def test_pilot_mode_recipient_restrictions(monkeypatch) -> None:
    patient_id = "twilio_pilot_restrict"
    _setup(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    fake_client = _FakeTwilioClient()
    transport = WhatsAppMessageTransport(
        account_sid="AC123",
        auth_token="token",
        whatsapp_sender="+14155238886",
        callback_base_url="https://example.ngrok-free.app",
        sandbox_mode=True,
        client=fake_client,
    )
    monkeypatch.setattr(main_module, "MESSAGE_TRANSPORT", transport)
    monkeypatch.setenv("MEDICATION_PILOT_MODE", "true")
    monkeypatch.setenv("MEDICATION_PILOT_ALLOWED_PATIENT_IDS", patient_id)
    monkeypatch.setenv("MEDICATION_PILOT_ALLOWED_CHANNELS", "whatsapp")
    monkeypatch.setenv("MEDICATION_PILOT_ALLOWED_NUMBERS", "+919999000099")

    blocked = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert blocked.status_code == 403


def test_dedupe_prevents_duplicate_sends_with_twilio_adapter(monkeypatch) -> None:
    patient_id = "twilio_dedupe"
    _setup(patient_id)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    fake_client = _FakeTwilioClient()
    transport = WhatsAppMessageTransport(
        account_sid="AC123",
        auth_token="token",
        whatsapp_sender="+14155238886",
        callback_base_url="https://example.ngrok-free.app",
        sandbox_mode=True,
        client=fake_client,
    )
    monkeypatch.setattr(main_module, "MESSAGE_TRANSPORT", transport)

    first = client.post(f"/medication/{patient_id}/send-due-reminders")
    second = client.post(f"/medication/{patient_id}/send-due-reminders")
    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["sent_messages"]) == 1
    assert len(second.json()["sent_messages"]) == 0
    assert len(fake_client.messages.calls) == 1


def test_signature_validation_uses_public_callback_url(monkeypatch) -> None:
    class _FakeValidator:
        last_url = ""

        def __init__(self, token: str) -> None:
            self.token = token

        def validate(self, url: str, form_data: dict[str, str], signature: str) -> bool:
            _FakeValidator.last_url = url
            return signature == "ok"

    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "true")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "token")
    monkeypatch.setenv("TWILIO_PUBLIC_WEBHOOK_BASE_URL", "https://public.example.com")
    monkeypatch.setattr(main_module, "RequestValidator", _FakeValidator)

    response = client.post(
        "/webhooks/twilio/whatsapp/status?v=1",
        data={"MessageSid": "SM000", "MessageStatus": "sent"},
        headers={"X-Twilio-Signature": "ok"},
    )
    assert response.status_code == 200
    assert _FakeValidator.last_url == "https://public.example.com/webhooks/twilio/whatsapp/status?v=1"
