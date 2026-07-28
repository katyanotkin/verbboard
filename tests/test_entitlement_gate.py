"""Tests for the Plus entitlement gate wired into /learn, /verbs, /api/verbs,
/audio, /search_verb[_by_lang], and /api/preferences.

FREE_STUDY_LANGUAGES currently covers every registered language (en/ru/he/es),
so core.entitlements.requires_entitlement() is False for all of them and the
gate has zero behavioral effect in production today. These tests force the
gate open with a not-yet-registered "it" language code (Plus-only, per
core/languages/config.py's PLUS_EXTRA_STUDY_LANGUAGES) so the redirect/403
branches are exercised without waiting for the Italian plugin to ship.
"""

from __future__ import annotations

from unittest.mock import patch
from urllib.parse import unquote

from fastapi.testclient import TestClient

from core.audio_service import build_hashed_audio_key
from tests.conftest import noop_ensure_audio

# ---------------------------------------------------------------------------
# /learn
# ---------------------------------------------------------------------------


def test_learn_free_language_unaffected_by_gate(client: TestClient, monkeypatch, mock_verb) -> None:
    monkeypatch.setattr("app.routes.learn.load_entries_for_language", lambda **kw: [mock_verb])
    monkeypatch.setattr("app.routes.learn.load_entry_by_id", lambda **kw: mock_verb)
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)
    monkeypatch.setattr("app.routes.learn.render_board_html", lambda **kw: "<html>board</html>")

    resp = client.get("/learn?language=en&verb_id=en_go")
    assert resp.status_code == 200


def test_learn_gate_anonymous_redirects_to_signin_with_full_return_to(client: TestClient) -> None:
    with (
        patch("app.routes.learn.can_study", return_value=False),
        patch("app.routes.learn.get_session_uid", return_value=None),
    ):
        resp = client.get(
            "/learn?language=it&verb_id=it_andare&ui_language=es",
            follow_redirects=False,
        )

    assert resp.status_code == 303
    location = resp.headers["location"]
    assert location.startswith("/auth/signin?return_to=")
    target = unquote(location.split("return_to=", 1)[1])
    # Every in-scope param on the original request must survive the round trip
    # through sign-in and back.
    assert target == "/learn?language=it&verb_id=it_andare&ui_language=es"


def test_learn_gate_signed_in_unentitled_redirects_to_verbs_plus_required(client: TestClient) -> None:
    with (
        patch("app.routes.learn.can_study", return_value=False),
        patch("app.routes.learn.get_session_uid", return_value="user-1"),
    ):
        resp = client.get("/learn?language=it&verb_id=it_andare", follow_redirects=False)

    assert resp.status_code == 303
    assert resp.headers["location"] == "/verbs?language=it&plus_required=1"


def test_learn_gate_entitled_user_passes_through(client: TestClient, monkeypatch, mock_verb) -> None:
    monkeypatch.setattr("app.routes.learn.load_entries_for_language", lambda **kw: [mock_verb])
    monkeypatch.setattr("app.routes.learn.load_entry_by_id", lambda **kw: mock_verb)
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)
    monkeypatch.setattr("app.routes.learn.render_board_html", lambda **kw: "<html>board</html>")

    # "it" has no registered plugin/voices yet -- use "en" (a real, fully
    # wired language) with can_study forced True, to isolate "does the gate
    # let an entitled request continue" from "does Italian content exist".
    with (
        patch("app.routes.learn.can_study", return_value=True),
        patch("app.routes.learn.get_session_uid", return_value="user-1"),
    ):
        resp = client.get("/learn?language=en&verb_id=en_go")

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# /verbs -- plus_required notice
# ---------------------------------------------------------------------------


def test_verbs_plus_required_renders_notice(client: TestClient) -> None:
    resp = client.get("/verbs?language=en&plus_required=1")
    assert resp.status_code == 200
    assert "VerbBoard Plus" in resp.text


def test_verbs_without_plus_required_has_no_notice(client: TestClient) -> None:
    resp = client.get("/verbs?language=en")
    assert resp.status_code == 200
    assert "VerbBoard Plus" not in resp.text


def test_verbs_picker_not_entitlement_filtered(client: TestClient) -> None:
    """The language picker filters through active_study_plugins() (edition-
    level), not entitlement. An unentitled user must still see today's four
    languages -- this only pins that /verbs itself never 404s/redirects based
    on entitlement, since the picker filter is untouched by this task."""
    resp = client.get("/verbs?language=en")
    assert resp.status_code == 200


def test_verbs_direct_select_of_gated_language_blocks_content_not_page(client: TestClient, monkeypatch) -> None:
    """Hand-navigating (or picking from the still-visible picker) to a
    Plus-only language directly must not load/render its real verb list --
    same fate as bouncing back from /learn, just without the redirect hop."""
    called: list = []

    def _fake_load_entries(**kw):
        called.append(kw)
        return []

    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", _fake_load_entries)

    with (
        patch("app.routes.verbs.can_study", return_value=False),
        patch("app.routes.verbs.get_session_uid", return_value=None),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    assert "VerbBoard Plus" in resp.text
    assert called == []  # no Firestore verb-list load for a gated language


def test_verbs_entitled_selection_still_loads_real_content(client: TestClient, monkeypatch, mock_verb) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [mock_verb])

    with (
        patch("app.routes.verbs.can_study", return_value=True),
        patch("app.routes.verbs.get_session_uid", return_value="user-1"),
    ):
        resp = client.get("/verbs?language=en")

    assert resp.status_code == 200
    assert "VerbBoard Plus" not in resp.text


def test_verbs_entitled_selection_of_language_without_ui_locale_does_not_500(
    client: TestClient, monkeypatch, mock_verb
) -> None:
    """Regression: an entitled request for a study language that has no
    UI locale file (Italian is a real registered plugin but not a UI
    language -- app/i18n/it.json does not exist) must not crash trying to
    build the alphabet-specific sort_az_label via get_strings(language)."""
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [mock_verb])

    with (
        patch("app.routes.verbs.can_study", return_value=True),
        patch("app.routes.verbs.get_session_uid", return_value="user-1"),
    ):
        resp = client.get("/verbs?language=it&ui_language=ru")

    assert resp.status_code == 200
    assert "VerbBoard Plus" not in resp.text


# ---------------------------------------------------------------------------
# /api/verbs -- JSON pager endpoint verbs.html calls directly
# ---------------------------------------------------------------------------


def test_api_verbs_free_language_not_gated(client: TestClient) -> None:
    resp = client.get("/api/verbs?language=en&offset=0&limit=20")
    assert resp.status_code == 200


def test_api_verbs_gated_language_returns_403(client: TestClient) -> None:
    with patch("app.routes.verbs.can_study", return_value=False):
        resp = client.get("/api/verbs?language=it&offset=0&limit=20")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /search_verb_by_lang and /search_verb -- must not spend LLM calls on a
# gated language before the (already-gated) /learn redirect would apply.
# ---------------------------------------------------------------------------


def test_search_verb_by_lang_gate_anonymous_redirects_to_signin(client: TestClient) -> None:
    with patch("app.routes.home.can_study", return_value=False):
        resp = client.get(
            "/search_verb_by_lang?language=it&q=run&source_lang=en",
            follow_redirects=False,
        )
    assert resp.status_code in (302, 303, 307, 308)
    assert resp.headers["location"].startswith("/auth/signin?return_to=")


def test_search_verb_by_lang_gate_signed_in_redirects_with_plus_required(client: TestClient) -> None:
    with (
        patch("app.routes.home.can_study", return_value=False),
        patch("app.routes.home.get_session_uid", return_value="user-1"),
    ):
        resp = client.get(
            "/search_verb_by_lang?language=it&q=run&source_lang=en&return_to=%2Fverbs%3Flanguage%3Dit",
            follow_redirects=False,
        )
    assert resp.status_code in (302, 303, 307, 308)
    location = resp.headers["location"]
    assert location.startswith("/verbs?language=it")
    assert "plus_required=1" in location


def test_search_verb_by_lang_gate_checked_before_translation_call(client: TestClient) -> None:
    called: list = []

    def _fake_translate(*a, **kw):
        called.append((a, kw))
        return "correr"

    with (
        patch("app.routes.home.can_study", return_value=False),
        patch("app.routes.home.translate_search_query", _fake_translate),
    ):
        client.get("/search_verb_by_lang?language=it&q=run&source_lang=en")
    assert called == []


def test_search_verb_gate_anonymous_redirects_to_signin(client: TestClient) -> None:
    with patch("app.routes.home.can_study", return_value=False):
        resp = client.get("/search_verb?language=it&q=andare", follow_redirects=False)
    assert resp.status_code in (302, 303, 307, 308)
    assert resp.headers["location"].startswith("/auth/signin?return_to=")


def test_search_verb_gate_checked_before_firestore_lookup(client: TestClient) -> None:
    called: list = []

    def _fake_find(*a, **kw):
        called.append((a, kw))
        return None

    with (
        patch("app.routes.home.can_study", return_value=False),
        patch("app.routes.home.find_verb_by_search_extract", _fake_find),
    ):
        client.get("/search_verb?language=it&q=andare")
    assert called == []


def test_search_verb_free_language_unaffected_by_gate(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", lambda lang, query: None)
    monkeypatch.setattr("app.routes.home.log_missing_verb_search", lambda **kwargs: None)
    resp = client.get("/search_verb?language=en&q=xyzzyverb", follow_redirects=False)
    assert resp.status_code in (302, 303, 307, 308)
    assert "/auth/signin" not in resp.headers.get("location", "")


# ---------------------------------------------------------------------------
# /api/preferences -- learning_language must not persist a Plus-only value
# for an unentitled user
# ---------------------------------------------------------------------------


def test_preferences_rejects_gated_learning_language_even_if_edition_allows_it(client: TestClient) -> None:
    # is_study_language forced True so this test isolates the entitlement
    # check specifically, not the pre-existing edition-level check.
    with (
        patch("app.routes.api_preferences.is_study_language", return_value=True),
        patch("app.routes.api_preferences.can_study", return_value=False),
    ):
        resp = client.post(
            "/api/preferences",
            json={"learning_language": "it"},
            headers={"Authorization": "Bearer local-dev"},
        )
    assert resp.status_code == 422


def test_preferences_accepts_entitled_learning_language(client: TestClient) -> None:
    with (
        patch("app.routes.api_preferences.is_study_language", return_value=True),
        patch("app.routes.api_preferences.can_study", return_value=True),
        patch("app.routes.api_preferences.set_preferences") as mock_set,
    ):
        resp = client.post(
            "/api/preferences",
            json={"learning_language": "it"},
            headers={"Authorization": "Bearer local-dev"},
        )
    assert resp.status_code == 200
    mock_set.assert_called_once()


# ---------------------------------------------------------------------------
# /audio
# ---------------------------------------------------------------------------


def test_audio_free_language_unaffected_by_gate(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.audio.read_audio_bytes", lambda **kw: b"cached-mp3")
    form_key = build_hashed_audio_key("base", "go")
    resp = client.get(f"/audio/en/en_go/female/{form_key}.mp3")
    assert resp.status_code == 200


def test_audio_gated_language_returns_403_not_redirect(client: TestClient) -> None:
    with patch("app.routes.audio.can_study", return_value=False):
        resp = client.get("/audio/it/it_andare/female/base_deadbeef00.mp3", follow_redirects=False)
    assert resp.status_code == 403


def test_audio_gate_checked_before_backend_read(client: TestClient, monkeypatch) -> None:
    """The gate must short-circuit before any Firestore/TTS work."""
    called: list = []

    def _fake_read_audio(**kw):
        called.append(kw)
        return None

    monkeypatch.setattr("app.routes.audio.read_audio_bytes", _fake_read_audio)

    with patch("app.routes.audio.can_study", return_value=False):
        resp = client.get("/audio/it/it_andare/female/base_deadbeef00.mp3")

    assert resp.status_code == 403
    assert called == []
