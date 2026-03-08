from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
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


def _plan_payload_with_care(patient_id: str) -> dict:
    plan = _plan_payload(patient_id)
    plan["care_activities"] = [
        {
            "activity_id": "breakfast_0800",
            "title": "Breakfast",
            "category": "meal",
            "schedule": "08:00",
            "duration_minutes": 20,
            "instruction": "Have breakfast before meds",
            "frequency": "daily",
            "priority": "important",
            "confirmation_required": True,
            "escalation_policy": "follow up if skipped",
        },
        {
            "activity_id": "walk_1000",
            "title": "Walk",
            "category": "activity",
            "schedule": "10:00",
            "duration_minutes": 20,
            "instruction": "Light walk for 20 minutes",
            "frequency": "daily",
            "priority": "routine",
            "confirmation_required": True,
            "escalation_policy": "reschedule if delayed",
        },
    ]
    return plan


def _setup(patient_id: str) -> None:
    client.post("/medication/patient", json=_patient_payload(patient_id))
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_plan_payload(patient_id))
    assert response.status_code == 200


def _setup_with_contact(patient_id: str, patient_contact: str) -> None:
    payload = _patient_payload(patient_id)
    payload["patient_contact"] = patient_contact
    client.post("/medication/patient", json=payload)
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_plan_payload(patient_id))
    assert response.status_code == 200


def _setup_with_care(patient_id: str) -> None:
    client.post("/medication/patient", json=_patient_payload(patient_id))
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_plan_payload_with_care(patient_id))
    assert response.status_code == 200


def _setup_with_care_contact(patient_id: str, patient_contact: str) -> None:
    payload = _patient_payload(patient_id)
    payload["patient_contact"] = patient_contact
    client.post("/medication/patient", json=payload)
    response = client.post(f"/medication/patient/{patient_id}/plan", json=_plan_payload_with_care(patient_id))
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
        metadata={"last_customer_message_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
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
    from_number = "+919999020001"
    _setup_with_contact(patient_id, from_number)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})

    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")
    client.post(f"/medication/{patient_id}/send-due-reminders")

    inbound = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "TAKEN"},
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


def test_inbound_schedule_command_returns_formatted_schedule(monkeypatch) -> None:
    patient_id = "twilio_cmd_schedule"
    from_number = "+919999010001"
    _setup_with_care_contact(patient_id, from_number)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "SCHEDULE"},
    )
    assert response.status_code == 200
    assert "Schedule" in response.text
    assert "Breakfast" in response.text


def test_inbound_today_command_returns_status_summary(monkeypatch) -> None:
    patient_id = "twilio_cmd_today"
    from_number = "+919999010002"
    _setup_with_care_contact(patient_id, from_number)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "TODAY"},
    )
    assert response.status_code == 200
    assert "TODAY" in response.text
    assert "Completed" in response.text


def test_inbound_status_command_returns_careos_summary(monkeypatch) -> None:
    patient_id = "twilio_cmd_status"
    from_number = "+919999010009"
    _setup_with_care_contact(patient_id, from_number)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "STATUS"},
    )
    assert response.status_code == 200
    assert "TODAY" in response.text
    assert "Completed" in response.text


def test_inbound_next_command_returns_next_item(monkeypatch) -> None:
    patient_id = "twilio_cmd_next"
    from_number = "+919999010003"
    _setup_with_care_contact(patient_id, from_number)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "NEXT"},
    )
    assert response.status_code == 200
    assert "Next:" in response.text


def test_inbound_skip_activity_command_marks_care_activity_skipped(monkeypatch) -> None:
    patient_id = "twilio_cmd_skip"
    from_number = "+919999010004"
    _setup_with_care_contact(patient_id, from_number)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "SKIP breakfast"},
    )
    assert response.status_code == 200
    assert "as skipped" in response.text

    today = client.get(f"/medication/{patient_id}/today").json()
    breakfast = next(
        item
        for item in today["unified_daily_plan"]["items"]
        if item["item_type"] == "care_activity" and "Breakfast" in item["title"]
    )
    assert breakfast["status"] == "skipped"


def test_inbound_delay_activity_command_records_delayed(monkeypatch) -> None:
    patient_id = "twilio_cmd_delay"
    from_number = "+919999010005"
    _setup_with_care_contact(patient_id, from_number)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:10:00+05:30"})
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "DELAY breakfast 15"},
    )
    assert response.status_code == 200
    assert "Marked DELAYED" in response.text

    timeline = client.get(f"/careos/{patient_id}/timeline", params={"date": "2026-03-07"}).json()
    breakfast = next(item for item in timeline["items"] if item["item_type"] == "care_activity" and "Breakfast" in item["title"])
    assert breakfast["slot_time"] == "08:15"


def test_inbound_done_command_marks_item_complete(monkeypatch) -> None:
    patient_id = "twilio_cmd_done"
    from_number = "+919999010006"
    _setup_with_care_contact(patient_id, from_number)
    client.post("/medication/simulated-time/set", json={"simulated_now": "2026-03-07T08:05:00+05:30"})
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "DONE breakfast"},
    )
    assert response.status_code == 200
    assert "Marked Breakfast as done" in response.text

    today = client.get(f"/careos/{patient_id}/today").json()
    breakfast = next(item for item in today["timeline"]["items"] if item["item_type"] == "care_activity" and "Breakfast" in item["title"])
    assert breakfast["status"] == "completed"


def test_inbound_move_command_retimes_activity(monkeypatch) -> None:
    patient_id = "twilio_cmd_move"
    from_number = "+919999010007"
    _setup_with_care_contact(patient_id, from_number)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "MOVE walk 11:15"},
    )
    assert response.status_code == 200
    assert "Moved Walk to 11:15" in response.text

    timeline = client.get(f"/careos/{patient_id}/timeline", params={"date": "2026-03-07"}).json()
    moved = next(item for item in timeline["items"] if item["item_type"] == "care_activity" and "Walk" in item["title"])
    assert moved["slot_time"] == "11:15"


def test_inbound_unknown_command_returns_help(monkeypatch) -> None:
    patient_id = "twilio_cmd_help"
    from_number = "+919999010008"
    _setup_with_care_contact(patient_id, from_number)
    monkeypatch.setenv("TWILIO_VALIDATE_SIGNATURES", "false")

    response = client.post(
        "/webhooks/twilio/whatsapp/inbound",
        data={"From": f"whatsapp:{from_number}", "Body": "FOOBAR"},
    )
    assert response.status_code == 200
    assert "Commands:" in response.text


def test_delivery_status_callback_updates_message_state(monkeypatch) -> None:
    patient_id = "twilio_status"
    _setup_with_contact(patient_id, "+919999020002")
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
