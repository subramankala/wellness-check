Run from repo root:

```bash
PATIENT_ID=patient_discharge_001 \
MCP_BASE_URL=http://<vm-ip>:8110 \
MCP_API_KEY=<secret> \
PHOTO_TEXT="Aztor 40mg 1 tab after food at 9 PM" \
ACTION=preview \
python3 openclaw/skills/careos-photo-intake/scripts/run.py
```

Apply update:

```bash
PATIENT_ID=patient_discharge_001 \
MCP_BASE_URL=http://<vm-ip>:8110 \
MCP_API_KEY=<secret> \
PHOTO_TEXT="Aztor 40mg 1 tab after food at 9 PM" \
ACTION=upsert_medication \
ACTOR_ID=doctor_001 \
ACTOR_ROLE=doctor \
REASON="discharge reconciliation" \
python3 openclaw/skills/careos-photo-intake/scripts/run.py
```

