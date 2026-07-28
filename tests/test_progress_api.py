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
    assert response.json() == {"ok": True, "streak": None}


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

    assert payload["badges"] == badges_to_save, "saved badges not returned by GET; cross-device badge sync would fail"


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


# ---------------------------------------------------------------------------
# Practice streak
#
# These tests hit a real Firestore doc (user_practice/local-dev-user/languages/*)
# that persists across test runs, and streak merges are monotonic (never
# shrink). To stay deterministic regardless of leftover state from previous
# runs, tests that need a *known* stored value first seed it with a
# far-future `last_day` -- guaranteed to be more recent than anything a prior
# run could have written, so merge_streak always lets it win outright.
# Each test also uses its own language code to avoid cross-test interference.
# ---------------------------------------------------------------------------

_FAR_FUTURE_DAY = "2099-01-01"
_FAR_FUTURE_DAY_PLUS_ONE = "2099-01-02"


def test_post_streak_persists_and_is_returned_by_get() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "s1",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 5,
        },
    )

    assert response.status_code == 200
    assert response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY, "len": 5, "grace_used": False}

    payload = client.get("/api/progress/practice?language=s1", headers=AUTH).json()
    assert payload["streak"] == {"last_day": _FAR_FUTURE_DAY, "len": 5, "grace_used": False}


def test_post_streak_response_contains_server_merged_streak() -> None:
    """The POST response streak must reflect the server-side merge, not the
    raw value the client sent (e.g. an adjacent-day bump extends length)."""
    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "s2",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 5,
        },
    )

    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "s2",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY_PLUS_ONE,
            "streak_len": 1,
        },
    )

    # Adjacent day: merged length is max(later.len, earlier.len + 1) = max(1, 6) = 6.
    assert response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY_PLUS_ONE, "len": 6, "grace_used": False}


def test_post_without_streak_leaves_existing_streak_untouched() -> None:
    """A POST that omits both streak fields must not disturb a previously
    stored streak, and must echo it back unchanged."""
    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "s3",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 7,
        },
    )

    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={"language": "s3", "badges": [3, 6]},
    )

    assert response.status_code == 200
    assert response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY, "len": 7, "grace_used": False}

    payload = client.get("/api/progress/practice?language=s3", headers=AUTH).json()
    assert payload["streak"] == {"last_day": _FAR_FUTURE_DAY, "len": 7, "grace_used": False}


def test_stale_post_does_not_shrink_stored_streak() -> None:
    """An older/shorter incoming streak (e.g. a stale offline device syncing
    late) must never shrink what's already stored."""
    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "s4",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 50,
        },
    )

    # Same day, much shorter length.
    same_day_response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "s4",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 1,
        },
    )
    assert same_day_response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY, "len": 50, "grace_used": False}

    # Much older day with a short length (stale sync, big gap -> broken streak
    # on the stale device, but must not overwrite the newer stored streak).
    stale_response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "s4",
            "badges": [3],
            "streak_last_day": "2026-01-01",
            "streak_len": 1,
        },
    )
    assert stale_response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY, "len": 50, "grace_used": False}

    payload = client.get("/api/progress/practice?language=s4", headers=AUTH).json()
    assert payload["streak"] == {"last_day": _FAR_FUTURE_DAY, "len": 50, "grace_used": False}


# ---------------------------------------------------------------------------
# Streak grace/freeze (N2) -- gated by Settings.streak_grace_enabled
# (STREAK_GRACE_ENABLED env / EDITION=plus default). load_settings() is not
# cached, so monkeypatching the env var before the request is enough.
# ---------------------------------------------------------------------------

_FAR_FUTURE_DAY_PLUS_TWO = "2099-01-03"
_FAR_FUTURE_DAY_PLUS_THREE = "2099-01-04"


def test_gap_of_two_breaks_streak_when_grace_disabled() -> None:
    """Zero env -> free edition -> grace disabled -> a gap of 2 days breaks
    the streak exactly like the pre-grace implementation."""
    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={"language": "g4", "badges": [3], "streak_last_day": _FAR_FUTURE_DAY, "streak_len": 5},
    )

    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={"language": "g4", "badges": [3], "streak_last_day": _FAR_FUTURE_DAY_PLUS_TWO, "streak_len": 1},
    )

    assert response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY_PLUS_TWO, "len": 1, "grace_used": False}


def test_gap_of_two_preserves_streak_when_grace_available(monkeypatch) -> None:
    """One free miss per streak: a gap of exactly 2 days extends the streak
    (like a consecutive day) instead of breaking it, and consumes the grace."""
    monkeypatch.setenv("STREAK_GRACE_ENABLED", "true")

    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "g1",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 5,
            "streak_grace_used": False,
        },
    )

    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "g1",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY_PLUS_TWO,
            "streak_len": 1,
            "streak_grace_used": False,
        },
    )

    # gap of 2, grace available -> extended like an adjacent day: max(1, 5+1) = 6.
    assert response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY_PLUS_TWO, "len": 6, "grace_used": True}


def test_gap_of_two_breaks_streak_when_grace_already_used(monkeypatch) -> None:
    """A second missed day before the grace resets breaks the streak normally."""
    monkeypatch.setenv("STREAK_GRACE_ENABLED", "true")

    # Seed a streak that has already consumed its one free miss.
    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "g2",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 5,
            "streak_grace_used": True,
        },
    )

    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "g2",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY_PLUS_TWO,
            "streak_len": 1,
            "streak_grace_used": False,
        },
    )

    # Grace already used -> gap of 2 breaks the streak; the fresh streak's
    # grace_used resets to False (grace becomes available again).
    assert response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY_PLUS_TWO, "len": 1, "grace_used": False}


def test_gap_of_three_breaks_streak_regardless_of_grace(monkeypatch) -> None:
    """Only a single missed day is forgiven -- a gap of 3+ always breaks the
    streak, even with grace available."""
    monkeypatch.setenv("STREAK_GRACE_ENABLED", "true")

    client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "g3",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY,
            "streak_len": 5,
            "streak_grace_used": False,
        },
    )

    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "g3",
            "badges": [3],
            "streak_last_day": _FAR_FUTURE_DAY_PLUS_THREE,
            "streak_len": 1,
            "streak_grace_used": False,
        },
    )

    assert response.json()["streak"] == {"last_day": _FAR_FUTURE_DAY_PLUS_THREE, "len": 1, "grace_used": False}


def test_post_streak_rejects_malformed_calendar_date() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3],
            "streak_last_day": "2026-13-40",
            "streak_len": 1,
        },
    )
    assert response.status_code == 422


def test_post_streak_rejects_wrong_date_format() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3],
            "streak_last_day": "07/08/2026",
            "streak_len": 1,
        },
    )
    assert response.status_code == 422


def test_post_streak_rejects_zero_len() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3],
            "streak_last_day": "2026-07-08",
            "streak_len": 0,
        },
    )
    assert response.status_code == 422


def test_post_streak_rejects_negative_len() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3],
            "streak_last_day": "2026-07-08",
            "streak_len": -1,
        },
    )
    assert response.status_code == 422


def test_post_streak_rejects_len_over_max() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3],
            "streak_last_day": "2026-07-08",
            "streak_len": 36601,
        },
    )
    assert response.status_code == 422


def test_post_streak_rejects_len_without_day() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3],
            "streak_len": 5,
        },
    )
    assert response.status_code == 422


def test_post_streak_rejects_day_without_len() -> None:
    response = client.post(
        "/api/progress/practice",
        headers=AUTH,
        json={
            "language": "en",
            "badges": [3],
            "streak_last_day": "2026-07-08",
        },
    )
    assert response.status_code == 422
