from fastapi.testclient import TestClient

from gateway_app.main import app


def test_gateway_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
