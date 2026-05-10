from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "audio_backend" in data


def test_health_reflects_local_environment(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["environment"] == "local"
    assert data["audio_backend"] == "gcs"
