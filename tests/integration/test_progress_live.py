"""
Live integration tests for /api/progress endpoints.

Run against a live server -- skipped automatically unless
PROGRESS_TEST_BASE_URL is set.

Quick-start:
  make test-progress-stage        # stage, mock user (user-stage token)
  make test-progress-prod         # prod,  mock user (user-prod  token)

  # local dev-bypass:
  PROGRESS_TEST_BASE_URL=http://localhost:8001 pytest tests/integration -v

  # any env with a real Firebase token:
  PROGRESS_TEST_BASE_URL=https://stage.verbboard.com \\
    PROGRESS_TEST_TOKEN="<firebase-id-token>" pytest tests/integration -v
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = pytest.mark.skipif(
    not os.getenv("PROGRESS_TEST_BASE_URL"),
    reason="set PROGRESS_TEST_BASE_URL to run (e.g. make test-progress-stage)",
)


# ---------------------------------------------------------------------------
# Auth guards
# ---------------------------------------------------------------------------


def test_get_progress_rejects_unauthenticated(live_base_url: str) -> None:
    r = requests.get(f"{live_base_url}/api/progress?language=en")
    assert r.status_code == 401


def test_get_practice_rejects_unauthenticated(live_base_url: str) -> None:
    r = requests.get(f"{live_base_url}/api/progress/practice?language=en")
    assert r.status_code == 401


def test_post_seen_rejects_unauthenticated(live_base_url: str) -> None:
    r = requests.post(
        f"{live_base_url}/api/progress/seen",
        json={"language": "en", "verb_id": "en_go"},
    )
    assert r.status_code == 401


def test_post_known_rejects_unauthenticated(live_base_url: str) -> None:
    r = requests.post(
        f"{live_base_url}/api/progress/known",
        json={"language": "en", "verb_id": "en_go", "known": True},
    )
    assert r.status_code == 401


def test_post_practice_rejects_unauthenticated(live_base_url: str) -> None:
    r = requests.post(
        f"{live_base_url}/api/progress/practice",
        json={"language": "en", "badges": [3]},
    )
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# user_progress: seen + known round-trip
# ---------------------------------------------------------------------------


def test_mark_seen_succeeds(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    r = requests.post(
        f"{live_base_url}/api/progress/seen",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_mark_known_succeeds(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    r = requests.post(
        f"{live_base_url}/api/progress/known",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "known": True},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_seen_and_known_read_back(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    requests.post(
        f"{live_base_url}/api/progress/seen",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id},
    )
    requests.post(
        f"{live_base_url}/api/progress/known",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "known": True},
    )

    r = requests.get(
        f"{live_base_url}/api/progress?language=en",
        headers=live_auth_headers,
    )
    assert r.status_code == 200
    verbs = r.json()["verbs"]
    assert live_verb_id in verbs
    assert verbs[live_verb_id]["seen"] is True
    assert verbs[live_verb_id]["known"] is True


def test_unmark_known_read_back(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    requests.post(
        f"{live_base_url}/api/progress/seen",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id},
    )
    requests.post(
        f"{live_base_url}/api/progress/known",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "known": True},
    )
    requests.post(
        f"{live_base_url}/api/progress/known",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "known": False},
    )

    r = requests.get(
        f"{live_base_url}/api/progress?language=en",
        headers=live_auth_headers,
    )
    verbs = r.json()["verbs"]
    assert verbs[live_verb_id]["known"] is False
    assert verbs[live_verb_id]["seen"] is True


# ---------------------------------------------------------------------------
# spaced repetition: srs_box/srs_due_at/srs_reviewed_at round-trip
# ---------------------------------------------------------------------------


def test_post_review_rejects_unauthenticated(live_base_url: str) -> None:
    r = requests.post(
        f"{live_base_url}/api/progress/review",
        json={"language": "en", "verb_id": "en_go", "recalled": True},
    )
    assert r.status_code == 401


def test_marking_known_initializes_ladder(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    requests.post(
        f"{live_base_url}/api/progress/known",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "known": True},
    )

    r = requests.get(
        f"{live_base_url}/api/progress?language=en",
        headers=live_auth_headers,
    )
    verb = r.json()["verbs"][live_verb_id]
    assert verb["srs_box"] == 1
    assert verb["srs_due_at"] is not None
    assert verb["srs_reviewed_at"] is not None


def test_get_progress_omits_srs_fields_when_never_known(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    """seen-only (never marked known) must not carry srs fields at all --
    this is exactly the shape the client-side backfill logic depends on to
    tell "genuinely never in the ladder" apart from "in the ladder"."""
    requests.post(
        f"{live_base_url}/api/progress/seen",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id},
    )

    r = requests.get(
        f"{live_base_url}/api/progress?language=en",
        headers=live_auth_headers,
    )
    verb = r.json()["verbs"][live_verb_id]
    assert "srs_box" not in verb


def test_review_recalled_true_promotes_box(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    requests.post(
        f"{live_base_url}/api/progress/known",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "known": True},
    )

    r = requests.post(
        f"{live_base_url}/api/progress/review",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "recalled": True},
    )
    assert r.status_code == 200
    assert r.json()["box"] == 2

    r2 = requests.get(
        f"{live_base_url}/api/progress?language=en",
        headers=live_auth_headers,
    )
    assert r2.json()["verbs"][live_verb_id]["srs_box"] == 2


def test_review_recalled_false_resets_to_box_one(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    requests.post(
        f"{live_base_url}/api/progress/known",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "known": True},
    )
    requests.post(
        f"{live_base_url}/api/progress/review",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "recalled": True},
    )

    r = requests.post(
        f"{live_base_url}/api/progress/review",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "recalled": False},
    )
    assert r.status_code == 200
    assert r.json()["box"] == 1


def test_review_on_never_known_verb_lands_box_one_regardless_of_recall(
    live_base_url: str,
    live_auth_headers: dict[str, str],
    live_verb_id: str,
) -> None:
    """A verb reviewed before it was ever marked known (e.g. the pre-existing-
    known-verb backfill path, which surfaces a verb for review without ever
    calling POST /known) must land on box 1 whether or not recall succeeds --
    a review action is itself evidence of active study."""
    r = requests.post(
        f"{live_base_url}/api/progress/review",
        headers=live_auth_headers,
        json={"language": "en", "verb_id": live_verb_id, "recalled": False},
    )
    assert r.json()["box"] == 1


# ---------------------------------------------------------------------------
# user_practice: badges round-trip
# ---------------------------------------------------------------------------


def test_save_badges_succeeds(
    live_base_url: str,
    live_auth_headers: dict[str, str],
) -> None:
    r = requests.post(
        f"{live_base_url}/api/progress/practice",
        headers=live_auth_headers,
        json={"language": "en", "badges": [3, 6, 9]},
    )
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_badges_read_back(
    live_base_url: str,
    live_auth_headers: dict[str, str],
) -> None:
    badges = [3, 6, 9]
    requests.post(
        f"{live_base_url}/api/progress/practice",
        headers=live_auth_headers,
        json={"language": "en", "badges": badges},
    )

    r = requests.get(
        f"{live_base_url}/api/progress/practice?language=en",
        headers=live_auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["badges"] == badges


def test_badges_language_isolation(
    live_base_url: str,
    live_auth_headers: dict[str, str],
) -> None:
    """Badges written to 'he' must not appear in 'en' and vice versa."""
    # Save current state of 'he' so we can restore it after the test.
    before = (
        requests.get(
            f"{live_base_url}/api/progress/practice?language=he",
            headers=live_auth_headers,
        )
        .json()
        .get("badges", [])
    )

    sentinel = [42424242]
    requests.post(
        f"{live_base_url}/api/progress/practice",
        headers=live_auth_headers,
        json={"language": "he", "badges": sentinel},
    )

    r_en = requests.get(
        f"{live_base_url}/api/progress/practice?language=en",
        headers=live_auth_headers,
    )
    assert 42424242 not in r_en.json().get("badges", [])

    # Restore 'he' badges so the test leaves no dirty data.
    requests.post(
        f"{live_base_url}/api/progress/practice",
        headers=live_auth_headers,
        json={"language": "he", "badges": before},
    )
