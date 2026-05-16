from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_progress_requires_auth() -> None:
    response = client.get("/api/progress?language=en")

    assert response.status_code == 401


def test_get_progress_local_dev() -> None:
    response = client.get(
        "/api/progress?language=en",
        headers={
            "Authorization": "Bearer local-dev",
        },
    )

    assert response.status_code == 200
    assert "verbs" in response.json()


def test_mark_seen_local_dev() -> None:
    response = client.post(
        "/api/progress/seen",
        headers={
            "Authorization": "Bearer local-dev",
        },
        json={
            "language": "en",
            "verb_id": "en_write",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_mark_known_local_dev() -> None:
    response = client.post(
        "/api/progress/known",
        headers={
            "Authorization": "Bearer local-dev",
        },
        json={
            "language": "en",
            "verb_id": "en_write",
            "known": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_progress_round_trip_local_dev() -> None:
    client.post(
        "/api/progress/seen",
        headers={
            "Authorization": "Bearer local-dev",
        },
        json={
            "language": "en",
            "verb_id": "en_like",
        },
    )

    client.post(
        "/api/progress/known",
        headers={
            "Authorization": "Bearer local-dev",
        },
        json={
            "language": "en",
            "verb_id": "en_like",
            "known": True,
        },
    )

    response = client.get(
        "/api/progress?language=en",
        headers={
            "Authorization": "Bearer local-dev",
        },
    )

    payload = response.json()

    assert payload["verbs"]["en_like"]["seen"] is True
    assert payload["verbs"]["en_like"]["known"] is True
