from fastapi.testclient import TestClient

from handoff_router.main import app


def test_handoff_router_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
