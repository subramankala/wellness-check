# check-overdue-critical-doses

Checks overdue critical medication windows and dispatches staged caregiver follow-up messages.

## Inputs
- `MEDICATION_BASE_URL` (default `http://localhost:8105`)
- `PATIENT_ID` (required)
- `FOLLOWUP_COOLDOWN_MINUTES` (default `60`)

## Behavior
1. Calls `/medication/{patient_id}/today`.
2. Calls `/medication/{patient_id}/send-overdue-critical-followups` with cooldown.
3. Returns sent follow-up messages with escalation stage metadata.

Staged follow-ups are deduplicated by medication-workflow using dedupe keys.
