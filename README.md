# AI Patient Triage Monorepo

Production-shaped scaffold for a multi-service AI patient triage platform.

## Layers

- Realtime conversation layer: `apps/gateway`, `apps/voice-runtime`
- Deterministic safety/policy layer: `services/triage-engine`, `services/safety-engine`
- Operational handoff layer: `services/handoff-router`, `services/documentation`, `apps/ops-console`
- Medication adherence lane: `services/medication-workflow`

## Quick Start

1. Copy env defaults if needed: `.env.example`
2. Install dependencies: `make bootstrap`
3. Start stack: `make dev`
4. Run tests: `make test`

## Notes

- Twilio/OpenAI wiring is intentionally deferred with TODO markers.
- Protocol definitions live in `packages/protocols/schemas`.
