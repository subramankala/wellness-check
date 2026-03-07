# dispatch-due-medication-windows

Dispatches due medication-window reminders via medication-workflow transport endpoints.

## Inputs
- `MEDICATION_BASE_URL` (default `http://localhost:8105`)
- `PATIENT_ID` (required)

## Behavior
1. Calls `/medication/{patient_id}/due-now` for current state visibility.
2. Calls `/medication/{patient_id}/send-due-reminders`.
3. Prints JSON result with sent messages and counts.

Idempotency is enforced by medication-workflow dedupe keys.
