from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

AUTH = {"Authorization": "Bearer local-dev"}

# ---------------------------------------------------------------------------
# GET /api/progress
# ---------------------------------------------------------------------------


def test_get_progress_requires_auth() -> None:
    response = client.get("/api/progress?language=en")

    assert response.status_code == 401


def test_get_progress_local_dev() -> None:
    response = client.get(
        "/api/progress?language=en",
        headers=AUTH,
    )

    assert response.status_code == 200
    assert "verbs" in response.json()


# ---------------------------------------------------------------------------
# POST /api/progress/seen
# ---------------------------------------------------------------------------


def test_mark_seen_requires_auth() -> None:
    response = client.post(
        "/api/progress/seen",
        json={"language": "en", "verb_id": "en_go"},
    )

    assert response.status_code == 401


def test_mark_seen_local_dev() -> None:
    response = client.post(
        "/api/progress/seen",
        headers=AUTH,
        json={
            "language": "en",
            "verb_id": "en_write",
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# POST /api/progress/known
# ---------------------------------------------------------------------------


def test_mark_known_requires_auth() -> None:
    response = client.post(
        "/api/progress/known",
        json={"language": "en", "verb_id": "en_go", "known": True},
    )

    assert response.status_code == 401


def test_mark_known_local_dev() -> None:
    response = client.post(
        "/api/progress/known",
        headers=AUTH,
        json={
            "language": "en",
            "verb_id": "en_write",
            "known": True,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_unmark_known_local_dev() -> None:
    """Setting known=False should also succeed."""
    response = client.post(
        "/api/progress/known",
        headers=AUTH,
        json={
            "language": "en",
            "verb_id": "en_write",
            "known": False,
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# GET /api/progress/practice
# ---------------------------------------------------------------------------


def test_get_practice_progress_requires_auth() -> None:
    response = client.get("/api/progress/practice?language=en")

    assert response.status_code == 401


def test_get_practice_progress_local_dev() -> None:
    response = client.get(
        "/api/progress/practice?language=en",
        headers=AUTH,
    )

    assert response.status_code == 200
    payload = response.json()
    assert "badges" in payload
    assert isinstance(payload["badges"], list)


# ---------------------------------------------------------------------------
# POST /api/progress/practice
# ---------------------------------------------------------------------------


def test_save_practice_requires_auth() -> None:
    response = client.post(
        "/api/progress/practice",
        json={"language": "en", "badges": [3]},
    )

    assert response.status_code == 401


def test_save_practice_local_dev() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3, 6],
        },
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}


# ---------------------------------------------------------------------------
# Round-trip: seen + known persisted, then read back
# ---------------------------------------------------------------------------


def test_progress_round_trip_local_dev() -> None:
    client.post(
        "/api/progress/seen",
        headers=AUTH,
        json={
            "language": "en",
            "verb_id": "en_like",
        },
    )

    client.post(
        "/api/progress/known",
        headers=AUTH,
        json={
            "language": "en",
            "verb_id": "en_like",
            "known": True,
        },
    )

    response = client.get(
        "/api/progress?language=en",
        headers=AUTH,
    )

    payload = response.json()

    assert payload["verbs"]["en_like"]["seen"] is True
    assert payload["verbs"]["en_like"]["known"] is True


# ---------------------------------------------------------------------------
# Cross-device sync: known=true is visible in GET after POST
# (fixes "selected as known on desktop, not reflected on phone")
# ---------------------------------------------------------------------------


def test_known_true_reflected_in_get_progress() -> None:
    """
    Marking a verb known=true via POST must be returned by GET /api/progress.
    hydrateProgress() on another device depends on this to add verbs to the
    local known set.
    """
    verb_id = "en_sync_known_true"

    client.post(
        "/api/progress/known",
        headers=AUTH,
        json={"language": "en", "verb_id": verb_id, "known": True},
    )

    payload = client.get("/api/progress?language=en", headers=AUTH).json()

    assert verb_id in payload["verbs"], "verb not returned by GET after marking known"
    assert payload["verbs"][verb_id]["known"] is True


# ---------------------------------------------------------------------------
# Cross-device sync: known=false is visible in GET after unmark POST
# (fixes "unselected on desktop, not reflected on phone")
# ---------------------------------------------------------------------------


def test_known_false_reflected_in_get_progress() -> None:
    """
    After marking a verb known=true and then known=false, GET /api/progress
    must return known=false for that verb.
    hydrateProgress() on another device depends on this to remove verbs from
    the local known set (the known.delete() branch added to auth.js).
    """
    verb_id = "en_sync_known_false"

    # First mark it known
    client.post(
        "/api/progress/known",
        headers=AUTH,
        json={"language": "en", "verb_id": verb_id, "known": True},
    )

    # Then unmark it
    client.post(
        "/api/progress/known",
        headers=AUTH,
        json={"language": "en", "verb_id": verb_id, "known": False},
    )

    payload = client.get("/api/progress?language=en", headers=AUTH).json()

    assert verb_id in payload["verbs"], "verb not returned by GET after unmarking known"
    assert payload["verbs"][verb_id]["known"] is False


# ---------------------------------------------------------------------------
# Cross-device sync: badges saved on one device are returned on another
# (fixes "earned badge on desktop, not visible on phone after login")
# ---------------------------------------------------------------------------


def test_badges_reflected_in_get_after_post() -> None:
    """
    Badges POSTed to /api/progress/practice must be returned by
    GET /api/progress/practice so that syncPracticeBadgesFromServer() on
    another device can restore them into localStorage.
    """
    badges_to_save = [3, 6, 3, 9]

    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={"language": "ru", "badges": badges_to_save},
    )

    payload = client.get(
        "/api/progress/practice?language=ru",
        headers=AUTH,
    ).json()

    assert (
        payload["badges"] == badges_to_save
    ), "saved badges not returned by GET; cross-device badge sync would fail"


# ---------------------------------------------------------------------------
# Multi-language isolation: badges for "he" don't bleed into "en"
# ---------------------------------------------------------------------------


def test_practice_badges_language_isolation() -> None:
    """Writing badges to 'he' must not change the 'en' badge state."""
    before_en = client.get(
        "/api/progress/practice?language=en",
        headers=AUTH,
    ).json()["badges"]

    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={"language": "he", "badges": [6]},
    )

    after_en = client.get(
        "/api/progress/practice?language=en",
        headers=AUTH,
    ).json()["badges"]

    assert after_en == before_en, "he badges bled into en"


# ---------------------------------------------------------------------------
# Input validation (SECURITY: field length and badge-value constraints)
# ---------------------------------------------------------------------------


def test_seen_rejects_language_too_long() -> None:
    response = client.post(
        "/api/progress/seen",
        headers=AUTH,
        json={"language": "toolong", "verb_id": "en_go"},
    )
    assert response.status_code == 422


def test_seen_rejects_verb_id_too_long() -> None:
    response = client.post(
        "/api/progress/seen",
        headers=AUTH,
        json={"language": "en", "verb_id": "x" * 121},
    )
    assert response.status_code == 422


def test_known_rejects_language_too_long() -> None:
    response = client.post(
        "/api/progress/known",
        headers=AUTH,
        json={"language": "toolong", "verb_id": "en_go", "known": True},
    )
    assert response.status_code == 422


def test_practice_rejects_invalid_badge_size() -> None:
    """Badge values must be in {3, 6, 9}; arbitrary numbers are rejected."""
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={"language": "en", "badges": [5]},
    )
    assert response.status_code == 422


def test_practice_rejects_empty_language() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={"language": "", "badges": [3]},
    )
    assert response.status_code == 422


def test_get_progress_rejects_language_too_long() -> None:
    response = client.get(
        "/api/progress?language=toolong",
        headers=AUTH,
    )
    assert response.status_code == 422


def test_get_practice_rejects_language_too_long() -> None:
    response = client.get(
        "/api/progress/practice?language=toolong",
        headers=AUTH,
    )
    assert response.status_code == 422
