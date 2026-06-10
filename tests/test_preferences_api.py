"""
Tests for the /api/preferences endpoint and /set_language route.

Coverage:
- GET /api/preferences requires auth (401 without token)
- POST /api/preferences requires auth (401 without token)
- GET /api/preferences returns all three fields (ui_language, learning_language,
  practice_session_size) -- even when not set (returns nulls)
- POST /api/preferences round-trip: set ui_language, read it back
- POST /api/preferences round-trip: set learning_language, read it back
- POST /api/preferences round-trip: set practice_session_size, read it back
- POST /api/preferences rejects invalid ui_language value
- POST /api/preferences rejects invalid learning_language value
- POST /api/preferences rejects invalid practice_session_size value
- POST /api/preferences accepts partial payloads (only one field)
- /set_language redirects to /?language=<lang>
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, follow_redirects=False)
AUTH = {"Authorization": "Bearer local-dev"}


# ---------------------------------------------------------------------------
# GET /api/preferences -- auth guard
# ---------------------------------------------------------------------------


def test_get_preferences_requires_auth() -> None:
    response = client.get("/api/preferences")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/preferences -- auth guard
# ---------------------------------------------------------------------------


def test_post_preferences_requires_auth() -> None:
    response = client.post(
        "/api/preferences",
        json={"ui_language": "en"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/preferences -- shape
# ---------------------------------------------------------------------------


def test_get_preferences_returns_all_fields() -> None:
    """GET must return all three preference fields even if unset."""
    response = client.get("/api/preferences", headers=AUTH)
    assert response.status_code == 200
    payload = response.json()
    assert "ui_language" in payload
    assert "learning_language" in payload
    assert "practice_session_size" in payload


# ---------------------------------------------------------------------------
# POST /api/preferences -- round-trips
# ---------------------------------------------------------------------------


def test_preferences_round_trip_ui_language() -> None:
    """Setting ui_language via POST must be reflected by the next GET."""
    client.post("/api/preferences", headers=AUTH, json={"ui_language": "ru"})
    payload = client.get("/api/preferences", headers=AUTH).json()
    assert payload["ui_language"] == "ru"


def test_preferences_round_trip_learning_language() -> None:
    """Setting learning_language via POST must be reflected by the next GET."""
    client.post("/api/preferences", headers=AUTH, json={"learning_language": "he"})
    payload = client.get("/api/preferences", headers=AUTH).json()
    assert payload["learning_language"] == "he"


def test_preferences_round_trip_practice_session_size() -> None:
    """Setting practice_session_size via POST must be reflected by the next GET."""
    client.post("/api/preferences", headers=AUTH, json={"practice_session_size": 6})
    payload = client.get("/api/preferences", headers=AUTH).json()
    assert payload["practice_session_size"] == 6


def test_preferences_partial_post_only_one_field() -> None:
    """POST with only learning_language must succeed and return ok=True."""
    response = client.post(
        "/api/preferences", headers=AUTH, json={"learning_language": "es"}
    )
    assert response.status_code == 200
    assert response.json().get("ok") is True


# ---------------------------------------------------------------------------
# POST /api/preferences -- input validation
# ---------------------------------------------------------------------------


def test_post_preferences_rejects_invalid_ui_language() -> None:
    """Unknown UI language codes must be rejected with 422."""
    response = client.post(
        "/api/preferences",
        headers=AUTH,
        json={"ui_language": "xx"},
    )
    assert response.status_code == 422


def test_post_preferences_rejects_invalid_learning_language() -> None:
    """Learning language codes that have no plugin must be rejected with 422."""
    response = client.post(
        "/api/preferences",
        headers=AUTH,
        json={"learning_language": "zz"},
    )
    assert response.status_code == 422


def test_post_preferences_rejects_invalid_practice_session_size() -> None:
    """Practice session sizes outside {3, 6, 9} must be rejected with 422."""
    response = client.post(
        "/api/preferences",
        headers=AUTH,
        json={"practice_session_size": 5},
    )
    assert response.status_code == 422


@pytest.mark.parametrize("size", [3, 6, 9])
def test_post_preferences_accepts_valid_practice_session_sizes(size: int) -> None:
    """All three valid practice session sizes must be accepted."""
    response = client.post(
        "/api/preferences",
        headers=AUTH,
        json={"practice_session_size": size},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("lang", ["en", "ru", "he", "es"])
def test_post_preferences_accepts_all_valid_ui_languages(lang: str) -> None:
    """All four supported UI languages must be accepted."""
    response = client.post(
        "/api/preferences",
        headers=AUTH,
        json={"ui_language": lang},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("lang", ["en", "ru", "he", "es"])
def test_post_preferences_accepts_all_valid_learning_languages(lang: str) -> None:
    """All four supported learning languages must be accepted."""
    response = client.post(
        "/api/preferences",
        headers=AUTH,
        json={"learning_language": lang},
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# /set_language -- redirect
# ---------------------------------------------------------------------------


def test_set_language_redirects_to_home() -> None:
    """GET /set_language?language=ru must redirect to /?language=ru."""
    response = client.get("/set_language?language=ru")
    assert response.status_code in (302, 303, 307, 308)
    location = response.headers.get("location", "")
    assert "language=ru" in location
    assert location.startswith("/") or "localhost" in location
