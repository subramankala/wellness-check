from shared_types.models import HealthResponse


def test_health_response_model() -> None:
    response = HealthResponse(service="test", status="ok")
    assert response.status == "ok"
