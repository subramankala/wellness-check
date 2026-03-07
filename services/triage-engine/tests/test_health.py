from fastapi.testclient import TestClient

from triage_engine.main import app


def test_triage_engine_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
