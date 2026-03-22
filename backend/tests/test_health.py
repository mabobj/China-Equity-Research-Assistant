"""Health check tests."""

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_check() -> None:
    """The health endpoint should return an OK payload."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
