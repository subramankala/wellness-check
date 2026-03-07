# services

Backend domain services separated by deterministic decisioning and operational workflows.

- `triage-engine`: deterministic triage scoring
- `safety-engine`: hard policy/safety gate
- `handoff-router`: queue/destination routing
- `documentation`: note generation + persistence adapter
- `medication-workflow`: medication adherence, reminders, check-ins, escalation alerts
