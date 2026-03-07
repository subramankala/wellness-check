# Architecture Overview

## Layer Boundaries

1. Realtime conversation layer
- `apps/gateway`
- `apps/voice-runtime`

2. Deterministic safety/policy layer
- `services/triage-engine`
- `services/safety-engine`

3. Operational handoff layer
- `services/handoff-router`
- `services/documentation`
- `apps/ops-console`

4. Medication adherence lane
- `services/medication-workflow`

## Storage

- PostgreSQL is the initial persistence backend.
- Service ownership of tables and migrations will be defined in a later phase.

## Protocol-Driven Development

- Versioned YAML protocol contracts live in `packages/protocols/schemas`.
- Services should consume parsed protocol docs rather than hardcoded flow assumptions.
