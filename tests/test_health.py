from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_response_shape(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "verb_data_source" in data
    assert "audio_backend" in data
    assert "loaded_languages" in data


def test_health_reflects_local_environment(client: TestClient) -> None:
    data = client.get("/health").json()
    assert data["environment"] == "local"
    assert data["verb_data_source"] == "local"
    assert data["audio_backend"] == "local"
