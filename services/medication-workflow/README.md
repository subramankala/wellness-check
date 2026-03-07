# medication-workflow

Deterministic medication adherence and daily monitoring lane.

## Responsibilities

- Store medication plans and daily schedule instances
- Generate due/upcoming/overdue reminders
- Record dose confirmations and side-effect check-ins
- Raise deterministic adherence and symptom escalation alerts
- Produce caregiver-facing daily summaries

This lane is intentionally separate from triage protocols.

## Twilio WhatsApp Sandbox Pilot

### Required Configuration

Set these environment variables:

- `MEDICATION_TRANSPORT_PROVIDER=twilio`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_WHATSAPP_SENDER` (sandbox sender: `whatsapp:+14155238886`)
- `TWILIO_CALLBACK_BASE_URL` (used for status callback URL in outbound send)
- `TWILIO_PUBLIC_WEBHOOK_BASE_URL` (externally visible URL used for signature validation)
- `TWILIO_VALIDATE_SIGNATURES=true`
- `TWILIO_WHATSAPP_ROUTING_MODE=auto` (`auto`, `session_only`, `template_only`)
- `TWILIO_WHATSAPP_TEMPLATE_DUE_REMINDER_SID` (for outside 24h window)
- `TWILIO_WHATSAPP_TEMPLATE_OVERDUE_FOLLOWUP_SID` (for outside 24h window)
- `TWILIO_WHATSAPP_SANDBOX_MODE=true`

Pilot safeguards:

- `MEDICATION_PILOT_MODE=true`
- `MEDICATION_PILOT_ALLOWED_PATIENT_IDS=patient_discharge_001`
- `MEDICATION_PILOT_ALLOWED_NUMBERS=+91xxxxxxxxxx,+91yyyyyyyyyy`
- `MEDICATION_PILOT_ALLOWED_CHANNELS=whatsapp`
- `MEDICATION_PILOT_MAX_SENDS_PER_DAY=30`

### Twilio Console Setup (Sandbox)

1. Open Twilio Console -> Messaging -> Try it out -> Send a WhatsApp message.
2. Join sandbox from patient/caregiver WhatsApp numbers using the provided join code.
3. Configure inbound webhook URL:
   - `https://<public-host>/webhooks/twilio/whatsapp/inbound`
4. Configure status callback (service uses this on outbound API calls):
   - `https://<public-host>/webhooks/twilio/whatsapp/status`
5. Ensure `<public-host>` matches `TWILIO_PUBLIC_WEBHOOK_BASE_URL` exactly for signature checks.

### Sandbox Pilot Checklist

1. Start service with Twilio transport and pilot-mode allowlists.
2. Set simulated time to a due window.
3. Trigger due reminders:
   - `POST /medication/{patient_id}/send-due-reminders`
4. Verify outbound message record:
   - `GET /medication/{patient_id}/messages?date=YYYY-MM-DD`
5. Reply from WhatsApp with `TAKEN` (or `yes`, `done`, `delayed 10 min`, etc.).
6. Confirm inbound mapping updated medication window:
   - `GET /medication/{patient_id}/today`
7. Confirm delivery updates via status callback:
   - message `delivery_status` transitions in `/messages`.
8. Advance simulated time beyond 24h and verify template path (or sandbox fallback) for outbound sends.
