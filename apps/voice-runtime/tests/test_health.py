from fastapi.testclient import TestClient

from voice_runtime_app.main import app


def test_voice_runtime_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
