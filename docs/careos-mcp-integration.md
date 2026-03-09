# CareOS MCP Integration

This guide connects:

- VM: `careos-mcp` server (talks to CareOS backend)
- Mac: OpenClaw skill (`careos-photo-intake`) that sends MCP tool calls

## 1. VM setup (`careos-mcp`)

Run on VM:

```bash
cd ~/Wellness-check
export CAREOS_BASE_URL=http://localhost:8105
export CAREOS_MCP_API_KEY=change_me
export CAREOS_MCP_ALLOWED_WRITE_ROLES=doctor,clinician,caregiver
../venv/bin/python -m uvicorn careos_mcp_server.main:app --host 0.0.0.0 --port 8110
```

Health check:

```bash
curl http://localhost:8110/health
```

## 2. VM MCP quick checks

List tools:

```bash
curl http://localhost:8110/mcp/tools -H "x-mcp-api-key: change_me" | jq
```

Read today status:

```bash
curl -X POST http://localhost:8110/mcp/call \
  -H "Content-Type: application/json" \
  -H "x-mcp-api-key: change_me" \
  -d '{"tool":"careos_get_today","arguments":{"patient_id":"patient_discharge_001"}}' | jq
```

## 3. Mac OpenClaw skill usage

Preview parse from photo text:

```bash
cd /Users/kumarmankala/code/Codex/Wellness-check
PATIENT_ID=patient_discharge_001 \
MCP_BASE_URL=http://<VM_PUBLIC_IP>:8110 \
MCP_API_KEY=change_me \
PHOTO_TEXT="Aztor 40mg 1 tab after food at 9 PM" \
ACTION=preview \
python3 openclaw/skills/careos-photo-intake/scripts/run.py
```

Apply medication upsert:

```bash
PATIENT_ID=patient_discharge_001 \
MCP_BASE_URL=http://<VM_PUBLIC_IP>:8110 \
MCP_API_KEY=change_me \
PHOTO_TEXT="Aztor 40mg 1 tab after food at 9 PM" \
ACTION=upsert_medication \
ACTOR_ID=doctor_001 \
ACTOR_ROLE=doctor \
REASON="discharge reconciliation update" \
python3 openclaw/skills/careos-photo-intake/scripts/run.py
```

Delete medication entry by parsed name+time:

```bash
PATIENT_ID=patient_discharge_001 \
MCP_BASE_URL=http://<VM_PUBLIC_IP>:8110 \
MCP_API_KEY=change_me \
PHOTO_TEXT="Aztor at 9 PM" \
ACTION=delete_medication \
ACTOR_ID=doctor_001 \
ACTOR_ROLE=doctor \
REASON="duplicate entry cleanup" \
python3 openclaw/skills/careos-photo-intake/scripts/run.py
```

## 4. Security baseline

- Keep `CAREOS_MCP_API_KEY` secret.
- Restrict port `8110` to trusted IPs only (Mac/OpenClaw runner).
- Use TLS/HTTPS via reverse proxy before production exposure.
- Keep actor fields (`ACTOR_ID`, `ACTOR_ROLE`, `REASON`) on write calls for audit trail.

## 5. Full CRUD coverage

Exposed tools include:

- Read: today/timeline/notifications/messages/plan export
- Write: import plan, upsert/delete medication, upsert/delete activity, timeline action

