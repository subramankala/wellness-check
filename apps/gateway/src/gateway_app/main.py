from __future__ import annotations

import os
from uuid import uuid4

from fastapi import FastAPI
from pydantic import BaseModel

from shared_types import HealthResponse, SessionBootstrap, configure_logging, get_logger

configure_logging(os.getenv("LOG_LEVEL", "INFO"))
logger = get_logger("gateway", layer="realtime-conversation")

app = FastAPI(title="gateway")

SUPPORTED_PROTOCOL_ID = "post_op_fever_v1"


class TwilioVoiceWebhookRequest(BaseModel):
    call_sid: str
    from_number: str
    to_number: str
    caller_language: str | None = None


@app.on_event("startup")
def on_startup() -> None:
    logger.info("gateway_started")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(service="gateway", status="ok")


@app.post("/webhooks/twilio/voice", response_model=SessionBootstrap)
def twilio_voice_webhook(payload: TwilioVoiceWebhookRequest) -> SessionBootstrap:
    # TODO(security): enforce Twilio signature verification when real webhook ingress is enabled.
    request_id = f"req_{uuid4().hex}"
    session_id = f"sess_{payload.call_sid}"
    bootstrap = SessionBootstrap(
        request_id=request_id,
        session_id=session_id,
        channel="twilio_voice",
        protocol_id=SUPPORTED_PROTOCOL_ID,
        caller_language=payload.caller_language,
        caller_id=payload.from_number,
        metadata={
            "call_sid": payload.call_sid,
            "to_number": payload.to_number,
        },
    )
    logger.info(
        "voice_webhook_bootstrapped",
        request_id=request_id,
        session_id=session_id,
        protocol_id=SUPPORTED_PROTOCOL_ID,
    )
    return bootstrap
