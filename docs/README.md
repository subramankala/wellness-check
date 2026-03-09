# Documentation

This repository has two documentation tracks:

- Developer track: implementation, architecture, APIs, and local operations.
- Product-builder track: workflow configuration, pilot rollout, and caregiver-facing behavior.

## Read This First

1. [System Architecture](/Users/kumarmankala/code/Codex/Wellness-check/docs/architecture.md)
2. [Developer Guide](/Users/kumarmankala/code/Codex/Wellness-check/docs/developer-guide.md)
3. [Control Flows](/Users/kumarmankala/code/Codex/Wellness-check/docs/control-flows.md)
4. [Medication/CareOS API Guide](/Users/kumarmankala/code/Codex/Wellness-check/docs/medication-careos-api.md)
5. [Product Builder Guide](/Users/kumarmankala/code/Codex/Wellness-check/docs/product-builder-guide.md)
6. [CareOS MCP Integration](/Users/kumarmankala/code/Codex/Wellness-check/docs/careos-mcp-integration.md)

## Who Should Use What

- Backend/frontend engineers: developer guide + control flows + API guide.
- Automation/orchestration engineers: control flows + `openclaw/README.md`.
- Product builders and pilot operators: product builder guide + API guide.

## Scope Notes

- Deterministic safety and triage logic is intentionally separated from medication/CareOS workflow logic.
- WhatsApp transport is provider-agnostic at the interface level and currently supports mock plus Twilio adapter paths.
- Voice/realtime audio and LLM-based extraction are intentionally out of scope for this lane.
