from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import os
import re
from typing import Protocol
from uuid import uuid4

from shared_types import (
    ChannelType,
    DeliveryStatus,
    MedicationMessageRecord,
    MessageKind,
    RecipientRole,
)

try:
    from twilio.rest import Client as TwilioClient
except Exception:  # pragma: no cover - optional import path
    TwilioClient = None  # type: ignore[assignment]


@dataclass(frozen=True)
class OutboundMessageRequest:
    patient_id: str
    date: str
    window_id: str
    window_slot_time: str
    recipient_role: RecipientRole
    recipient_address: str
    channel_type: ChannelType
    message_kind: MessageKind
    content: str
    dedupe_key: str
    escalation_stage: int | None
    metadata: dict[str, str]


class MessageTransport(Protocol):
    def send_message(self, request: OutboundMessageRequest) -> MedicationMessageRecord:
        ...

    def receive_confirmation(self, incoming_text: str) -> str:
        ...


def normalize_confirmation_text(incoming_text: str) -> str:
    raw = incoming_text.strip().lower()
    condensed = re.sub(r"[^a-z0-9 ]+", " ", raw)
    condensed = re.sub(r"\s+", " ", condensed).strip()

    if condensed in {"taken", "yes", "done", "taken done", "done taken", "yes done", "done yes"}:
        return "TAKEN"
    if condensed.startswith("delayed") or condensed.startswith("later"):
        return "DELAYED"
    if condensed in {"skipped", "skip", "skipped today", "not taken", "cannot take today"}:
        return "SKIPPED"
    if condensed in {"unsure", "not sure", "dont know", "don't know", "maybe"}:
        return "UNSURE"
    if "not taken" in condensed:
        return "SKIPPED"
    return ""


class MockMessageTransport:
    def send_message(self, request: OutboundMessageRequest) -> MedicationMessageRecord:
        return MedicationMessageRecord(
            message_id=f"msg_{uuid4().hex}",
            patient_id=request.patient_id,
            date=request.date,
            window_id=request.window_id,
            window_slot_time=request.window_slot_time,
            recipient_role=request.recipient_role,
            channel_type=request.channel_type,
            message_kind=request.message_kind,
            content=request.content,
            delivery_status=DeliveryStatus.DELIVERED,
            created_at=datetime.now(UTC).isoformat(),
            dedupe_key=request.dedupe_key,
            escalation_stage=request.escalation_stage,
            metadata=request.metadata,
        )

    def receive_confirmation(self, incoming_text: str) -> str:
        normalized = normalize_confirmation_text(incoming_text)
        if normalized:
            return normalized
        raise ValueError("invalid confirmation text")


class WhatsAppMessageTransport:
    def __init__(
        self,
        *,
        account_sid: str,
        auth_token: str,
        whatsapp_sender: str,
        callback_base_url: str,
        sandbox_mode: bool = True,
        client: object | None = None,
    ) -> None:
        if TwilioClient is None and client is None:
            raise RuntimeError("twilio package is required for WhatsApp transport")
        self._account_sid = account_sid
        self._auth_token = auth_token
        self._sender = whatsapp_sender
        self._callback_base_url = callback_base_url.rstrip("/")
        self._sandbox_mode = sandbox_mode
        self._client = client if client is not None else TwilioClient(account_sid, auth_token)
        self._routing_mode = os.getenv("TWILIO_WHATSAPP_ROUTING_MODE", "auto").lower()
        self._template_due_sid = os.getenv("TWILIO_WHATSAPP_TEMPLATE_DUE_REMINDER_SID", "")
        self._template_followup_sid = os.getenv("TWILIO_WHATSAPP_TEMPLATE_OVERDUE_FOLLOWUP_SID", "")

    @classmethod
    def from_env(cls) -> "WhatsAppMessageTransport":
        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        whatsapp_sender = os.getenv("TWILIO_WHATSAPP_SENDER", "")
        callback_base_url = os.getenv("TWILIO_CALLBACK_BASE_URL", "")
        sandbox_mode = os.getenv("TWILIO_WHATSAPP_SANDBOX_MODE", "true").lower() == "true"
        if not (account_sid and auth_token and whatsapp_sender and callback_base_url):
            raise RuntimeError("Missing required Twilio WhatsApp env configuration")
        return cls(
            account_sid=account_sid,
            auth_token=auth_token,
            whatsapp_sender=whatsapp_sender,
            callback_base_url=callback_base_url,
            sandbox_mode=sandbox_mode,
        )

    def _to_whatsapp_address(self, value: str) -> str:
        normalized = value.strip()
        return normalized if normalized.startswith("whatsapp:") else f"whatsapp:{normalized}"

    def _template_sid_for_kind(self, kind: MessageKind) -> str:
        if kind in {MessageKind.DUE_REMINDER, MessageKind.CARE_ACTIVITY_REMINDER}:
            return self._template_due_sid
        if kind is MessageKind.OVERDUE_FOLLOWUP:
            return self._template_followup_sid
        return ""

    def _in_customer_service_window(self, request: OutboundMessageRequest, now_utc: datetime) -> bool:
        last_customer_message_at = request.metadata.get("last_customer_message_at", "")
        if not last_customer_message_at:
            return False
        try:
            last_dt = datetime.fromisoformat(last_customer_message_at)
        except ValueError:
            return False
        return (now_utc - last_dt).total_seconds() <= 24 * 60 * 60

    def _message_route(self, request: OutboundMessageRequest, now_utc: datetime) -> str:
        if self._routing_mode == "session_only":
            return "session"
        if self._routing_mode == "template_only":
            return "template"
        return "session" if self._in_customer_service_window(request, now_utc) else "template"

    def send_message(self, request: OutboundMessageRequest) -> MedicationMessageRecord:
        if not request.recipient_address.strip():
            raise ValueError("recipient_address is required")

        now_utc = datetime.now(UTC)
        route = self._message_route(request, now_utc)
        template_sid = self._template_sid_for_kind(request.message_kind)
        status_callback = f"{self._callback_base_url}/webhooks/twilio/whatsapp/status"
        create_payload: dict[str, str] = {
            "from_": self._to_whatsapp_address(self._sender),
            "to": self._to_whatsapp_address(request.recipient_address),
            "status_callback": status_callback,
        }
        if route == "template":
            if template_sid:
                create_payload["content_sid"] = template_sid
                create_payload["content_variables"] = json.dumps(
                    {"1": request.window_slot_time, "2": request.content}
                )
            elif self._sandbox_mode:
                route = "session_fallback_sandbox"
                create_payload["body"] = request.content
            else:
                raise ValueError("template routing required but template SID is missing")
        else:
            create_payload["body"] = request.content

        response = self._client.messages.create(**create_payload)  # type: ignore[attr-defined]
        sid = str(getattr(response, "sid", f"msg_{uuid4().hex}"))
        raw_status = str(getattr(response, "status", "queued")).lower()
        mapped_status = DeliveryStatus.QUEUED
        if raw_status in {"sent"}:
            mapped_status = DeliveryStatus.SENT
        if raw_status in {"delivered"}:
            mapped_status = DeliveryStatus.DELIVERED
        if raw_status in {"failed", "undelivered"}:
            mapped_status = DeliveryStatus.FAILED

        return MedicationMessageRecord(
            message_id=sid,
            patient_id=request.patient_id,
            date=request.date,
            window_id=request.window_id,
            window_slot_time=request.window_slot_time,
            recipient_role=request.recipient_role,
            channel_type=ChannelType.WHATSAPP,
            message_kind=request.message_kind,
            content=request.content,
            delivery_status=mapped_status,
            created_at=now_utc.isoformat(),
            dedupe_key=request.dedupe_key,
            escalation_stage=request.escalation_stage,
            metadata={
                **request.metadata,
                "twilio_sid": sid,
                "twilio_status": raw_status,
                "recipient_address": request.recipient_address,
                "sandbox_mode": str(self._sandbox_mode).lower(),
                "message_route": route,
                "template_sid": template_sid,
            },
        )

    def receive_confirmation(self, incoming_text: str) -> str:
        normalized = normalize_confirmation_text(incoming_text)
        if normalized:
            return normalized
        raise ValueError("invalid confirmation text")
