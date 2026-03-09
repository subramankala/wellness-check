# careos-mcp

MCP-style tool server for remote CareOS control.

This service exposes authenticated tool calls over HTTP and forwards them to
the medication/CareOS backend (`services/medication-workflow`).

## Why this exists

- OpenClaw can run on a different machine and still perform full CRUD via one endpoint.
- Doctors/caregivers can access state and submit controlled updates with actor metadata.
- Future EHR connectors can integrate through a stable tool contract.

## Run

```bash
export CAREOS_BASE_URL=http://localhost:8105
export CAREOS_MCP_API_KEY=change_me
uvicorn careos_mcp_server.main:app --host 0.0.0.0 --port 8110
```

## Auth

Pass header:

- `x-mcp-api-key: <CAREOS_MCP_API_KEY>`

## Endpoints

- `GET /health`
- `GET /mcp/tools`
- `POST /mcp/call`

## Tool examples

```bash
curl -X POST http://localhost:8110/mcp/call \
  -H "Content-Type: application/json" \
  -H "x-mcp-api-key: change_me" \
  -d '{"tool":"careos_get_today","arguments":{"patient_id":"patient_discharge_001"}}'
```

```bash
curl -X POST http://localhost:8110/mcp/call \
  -H "Content-Type: application/json" \
  -H "x-mcp-api-key: change_me" \
  -d '{
    "tool":"careos_upsert_medication",
    "arguments":{
      "patient_id":"patient_discharge_001",
      "actor_id":"doctor_001",
      "actor_role":"doctor",
      "reason":"new discharge order",
      "medication_name":"AZTOR 40MG TAB",
      "dose_instructions":"1 tablet after food",
      "scheduled_time":"21:00",
      "meal_constraint":"after_meal",
      "priority":"important"
    }
  }'
```
