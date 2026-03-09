# careos-photo-intake

Parses medication photo text notes and applies deterministic CareOS updates via remote `careos-mcp`.

## Inputs

- `MCP_BASE_URL` (default `http://localhost:8110`)
- `MCP_API_KEY` (required)
- `PATIENT_ID` (required)
- `PHOTO_TEXT` (required for `upsert_medication` / `delete_medication`)
- `ACTION`:
  - `preview` (default)
  - `upsert_medication`
  - `delete_medication`
  - `get_today`
- `ACTOR_ID`, `ACTOR_ROLE`, `REASON` for write actions.

## Behavior

1. Deterministically parses medication name, time, dose, and meal rule from `PHOTO_TEXT`.
2. `preview` prints parsed candidate.
3. Write actions call MCP tool API on VM and return JSON result.

## Notes

- No autonomous medical advice. This only updates schedule data.
- Keep `actor_role` explicit (`doctor`, `clinician`, or `caregiver`) for auditability.

