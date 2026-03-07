# send-caregiver-daily-summary

Generates a deterministic caregiver digest from medication-workflow daily summary data.

## Inputs
- `MEDICATION_BASE_URL` (default `http://localhost:8105`)
- `PATIENT_ID` (required)
- `SUMMARY_DATE` (default: local today)
- `OUTPUT_PATH` (default `openclaw/output/caregiver-summary-<patient>-<date>.json`)

## Behavior
1. Fetches `/medication/{patient_id}/daily-summary?date=YYYY-MM-DD`.
2. Builds concise digest payload.
3. Writes JSON output locally for review/export.
