from __future__ import annotations

from fastapi.testclient import TestClient

import careos_mcp_server.main as mcp_main


client = TestClient(mcp_main.app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "careos-mcp"


def test_tools_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("CAREOS_MCP_API_KEY", "secret")
    response = client.get("/mcp/tools")
    assert response.status_code == 401
    ok = client.get("/mcp/tools", headers={"x-mcp-api-key": "secret"})
    assert ok.status_code == 200
    assert any(tool["name"] == "careos_get_today" for tool in ok.json()["tools"])


def test_read_tool_dispatch(monkeypatch) -> None:
    monkeypatch.setenv("CAREOS_MCP_API_KEY", "secret")

    def fake_request_json(url: str, *, method: str = "GET", payload: dict | None = None):
        assert method == "GET"
        assert "careos/patient_discharge_001/today" in url
        assert payload is None
        return {"patient_id": "patient_discharge_001", "ok": True}

    monkeypatch.setattr(mcp_main, "_request_json", fake_request_json)

    response = client.post(
        "/mcp/call",
        headers={"x-mcp-api-key": "secret"},
        json={"tool": "careos_get_today", "arguments": {"patient_id": "patient_discharge_001"}},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["result"]["patient_id"] == "patient_discharge_001"


def test_write_tool_requires_actor_fields(monkeypatch) -> None:
    monkeypatch.setenv("CAREOS_MCP_API_KEY", "secret")
    response = client.post(
        "/mcp/call",
        headers={"x-mcp-api-key": "secret"},
        json={
            "tool": "careos_upsert_medication",
            "arguments": {
                "patient_id": "p1",
                "medication_name": "AZTOR 40MG TAB",
                "dose_instructions": "1 tablet after food",
                "scheduled_time": "21:00",
            },
        },
    )
    assert response.status_code == 400

