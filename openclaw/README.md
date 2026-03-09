# openclaw

Workspace for medication workflow operational automations.

## Skills

- `skills/dispatch-due-medication-windows`
- `skills/check-overdue-critical-doses`
- `skills/send-caregiver-daily-summary`
- `skills/careos-photo-intake`

## Cron Specs

- `cron/due-reminders.yaml`
- `cron/overdue-critical.yaml`
- `cron/daily-summary.yaml`

## Local Simulation Runbook

1. Set simulated time to `06:55 IST`:
   `curl -X POST http://localhost:8105/medication/simulated-time/set -H 'Content-Type: application/json' -d '{\"simulated_now\":\"2026-03-07T06:55:00+05:30\"}'`
2. Run due reminder skill (07:00 window path):
   `PATIENT_ID=patient_discharge_001 python3 openclaw/skills/dispatch-due-medication-windows/scripts/run.py`
3. Advance to `08:05 IST` and run due reminder skill again:
   `curl -X POST http://localhost:8105/medication/simulated-time/advance -H 'Content-Type: application/json' -d '{\"hours\":1,\"minutes\":10}'`
4. Send 08:00 critical reminder:
   `PATIENT_ID=patient_discharge_001 python3 openclaw/skills/dispatch-due-medication-windows/scripts/run.py`
5. Advance to overdue window and run overdue check:
   `curl -X POST http://localhost:8105/medication/simulated-time/advance -H 'Content-Type: application/json' -d '{\"hours\":1,\"minutes\":0}'`
   `PATIENT_ID=patient_discharge_001 python3 openclaw/skills/check-overdue-critical-doses/scripts/run.py`
6. Inspect message records:
   `curl 'http://localhost:8105/medication/patient_discharge_001/messages?date=2026-03-07'`
