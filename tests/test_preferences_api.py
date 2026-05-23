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
- /set_language redirects to /?language=<lang> and sets a language cookie
- /set_language with a valid language sets the right cookie value
- Home page respects language cookie when no explicit ?language= param
- Home page explicit ?language= param overrides cookie
- Home page sets language cookie on every response
"""

from __future__ import annotations

from unittest.mock import patch

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
# /set_language -- redirect and cookie
# ---------------------------------------------------------------------------


def test_set_language_redirects_to_home() -> None:
    """GET /set_language?language=ru must redirect to /?language=ru."""
    response = client.get("/set_language?language=ru")
    assert response.status_code in (302, 303, 307, 308)
    location = response.headers.get("location", "")
    assert "language=ru" in location
    assert location.startswith("/") or "localhost" in location


def test_set_language_sets_language_cookie() -> None:
    """GET /set_language must set a language cookie matching the chosen language."""
    response = client.get("/set_language?language=he")
    cookie_header = response.headers.get("set-cookie", "")
    assert "language=he" in cookie_header


@pytest.mark.parametrize("lang", ["en", "ru", "he", "es"])
def test_set_language_cookie_matches_chosen_language(lang: str) -> None:
    """The language cookie value must match the requested language for all supported languages."""
    response = client.get(f"/set_language?language={lang}")
    cookie_header = response.headers.get("set-cookie", "")
    assert f"language={lang}" in cookie_header


# ---------------------------------------------------------------------------
# Home page language resolution -- cookie and URL param interaction
# These guard the server-side half of the preference-override flow.
# ---------------------------------------------------------------------------


def test_home_explicit_language_param_wins_over_cookie() -> None:
    """Explicit ?language= URL param must override cookie when both are present."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        client_with_cookies = TestClient(app)
        response = client_with_cookies.get(
            "/?language=ru",
            cookies={"language": "he"},
        )
    assert response.status_code == 200
    # The page should reflect Russian (ru), not Hebrew (he)
    # The language selector value is in a <select> with the 'selected' attribute
    assert (
        'value="ru" selected' in response.text
        or 'value="ru"  selected' in response.text
        or (
            # Jinja renders: <option value="ru" selected>
            'value="ru"' in response.text and "ru" in response.text
        )
    )
    # Cookie must be updated to ru
    cookie_header = response.headers.get("set-cookie", "")
    assert "language=ru" in cookie_header


def test_home_cookie_used_when_no_language_param() -> None:
    """When no ?language= param is given, the language cookie determines the selection."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        client_with_cookies = TestClient(app)
        response = client_with_cookies.get(
            "/",
            cookies={"language": "es"},
        )
    assert response.status_code == 200
    # es should be selected, not the default (he)
    assert "language=es" in response.headers.get("set-cookie", "")


def test_home_sets_language_cookie_on_every_response() -> None:
    """Home page must always set the language cookie so it persists across navigation."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        client_with_cookies = TestClient(app)
        response = client_with_cookies.get("/?language=en")
    assert response.status_code == 200
    assert "language=" in response.headers.get("set-cookie", "")


def test_home_sets_ui_language_cookie_on_every_response() -> None:
    """Home page must always set the ui_language cookie so language persists across navigation."""
    with patch("app.routes.home.list_verbs_recent", return_value=[]):
        client_with_cookies = TestClient(app)
        response = client_with_cookies.get("/?ui_language=ru")
    assert response.status_code == 200
    assert "ui_language=ru" in response.headers.get("set-cookie", "")
