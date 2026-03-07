from fastapi.testclient import TestClient

from documentation_service.main import app


def test_documentation_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
