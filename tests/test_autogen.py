"""Tests for on-the-spot verb generation (core/verb_autogen.py).

Covers:
- is_plausible_verb_query gate: valid and invalid inputs
- /search_verb: autogen triggered (generating=1 in redirect) for EN/ES miss
- /search_verb: autogen NOT triggered for HE/RU miss or garbage queries
- /verbs: generating notice rendered when generating=1 in URL
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from core.verb_autogen import is_plausible_verb_query

# ---------------------------------------------------------------------------
# Unit tests for the garbage gate
# ---------------------------------------------------------------------------


class TestIsPlausibleVerbQuery:
    def test_valid_english_word(self):
        assert is_plausible_verb_query("run", "en") is True

    def test_valid_spanish_infinitive(self):
        assert is_plausible_verb_query("correr", "es") is True

    def test_valid_inflected_form(self):
        assert is_plausible_verb_query("running", "en") is True

    def test_valid_reflexive_two_words(self):
        assert is_plausible_verb_query("se ir", "es") is True

    def test_valid_with_apostrophe(self):
        assert is_plausible_verb_query("don't", "en") is True

    def test_rejects_hebrew_language(self):
        assert is_plausible_verb_query("run", "he") is False

    def test_rejects_russian_language(self):
        assert is_plausible_verb_query("run", "ru") is False

    def test_rejects_empty(self):
        assert is_plausible_verb_query("", "en") is False

    def test_rejects_single_char(self):
        assert is_plausible_verb_query("a", "en") is False

    def test_rejects_too_long(self):
        assert is_plausible_verb_query("x" * 31, "en") is False

    def test_rejects_digits(self):
        assert is_plausible_verb_query("run2", "en") is False

    def test_rejects_three_word_phrase(self):
        assert is_plausible_verb_query("to be done", "en") is False

    def test_rejects_cyrillic(self):
        assert is_plausible_verb_query("бежать", "en") is False

    def test_rejects_stop_word_en(self):
        assert is_plausible_verb_query("the", "en") is False

    def test_rejects_stop_word_es(self):
        assert is_plausible_verb_query("el", "es") is False

    def test_rejects_symbols(self):
        assert is_plausible_verb_query("run!", "en") is False

    def test_accepts_hyphenated(self):
        assert is_plausible_verb_query("well-known", "en") is True

    def test_length_boundary_min(self):
        assert is_plausible_verb_query("go", "en") is True

    def test_length_boundary_max(self):
        assert is_plausible_verb_query("a" * 30, "en") is True


# ---------------------------------------------------------------------------
# Integration tests for /search_verb autogen trigger
# ---------------------------------------------------------------------------

_NOOP_MISS = lambda lang, query: None  # noqa: E731


def _patch_search_miss(monkeypatch) -> None:
    """Stub out all search paths to produce a clean miss."""
    monkeypatch.setattr("app.routes.home.find_verb_by_search_extract", _NOOP_MISS)
    monkeypatch.setattr("app.routes.home.log_missing_verb_search", lambda **kw: None)
    monkeypatch.setattr("app.routes.home._load_entries", lambda language: [])


def test_autogen_fires_for_en_miss(client: TestClient, monkeypatch) -> None:
    """EN search miss with a plausible query redirects with generating=1."""
    _patch_search_miss(monkeypatch)
    autogen_calls: list[dict] = []

    async def _fake_autogen(**kwargs):
        autogen_calls.append(kwargs)

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _fake_autogen)

    response = client.get("/search_verb?language=en&q=book", follow_redirects=False)

    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "generating=1" in location
    assert "not_available=1" in location
    assert "search=book" in location


def test_autogen_fires_for_es_miss(client: TestClient, monkeypatch) -> None:
    """ES search miss with a plausible query redirects with generating=1."""
    _patch_search_miss(monkeypatch)

    async def _noop(**kw):
        pass

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _noop)

    response = client.get("/search_verb?language=es&q=correr", follow_redirects=False)

    location = response.headers["location"]
    assert "generating=1" in location


def test_autogen_skips_for_unsupported_language(client: TestClient, monkeypatch) -> None:
    """Languages outside AUTOGEN_LANGUAGES never trigger autogen.

    HE and RU with ASCII queries are auto-redirected to /search_verb_by_lang
    (see _NON_LATIN_LANGUAGES in home.py), so we test the is_plausible_verb_query
    gate directly: is_plausible_verb_query returns False for "he" and "ru".
    The integration coverage is in test_autogen_skips_for_garbage_query which
    exercises the miss-without-generation path on the EN endpoint.
    """
    from core.verb_autogen import AUTOGEN_LANGUAGES

    assert "he" not in AUTOGEN_LANGUAGES
    assert "ru" not in AUTOGEN_LANGUAGES


def test_autogen_skips_for_garbage_query(client: TestClient, monkeypatch) -> None:
    """Queries with digits or non-Latin chars do not trigger autogen."""
    _patch_search_miss(monkeypatch)

    response = client.get("/search_verb?language=en&q=r2d2", follow_redirects=False)

    location = response.headers["location"]
    assert "generating=1" not in location
    assert "not_available=1" in location


def test_autogen_skips_for_three_word_phrase(client: TestClient, monkeypatch) -> None:
    """Multi-word non-verb phrases do not trigger autogen."""
    _patch_search_miss(monkeypatch)

    response = client.get("/search_verb?language=en&q=the+quick+fox", follow_redirects=False)

    location = response.headers["location"]
    assert "generating=1" not in location


def test_autogen_does_not_fire_on_hit(client: TestClient, monkeypatch) -> None:
    """A verb that IS found must not trigger autogen."""
    monkeypatch.setattr(
        "app.routes.home.find_verb_by_search_extract",
        lambda lang, query: {"verb_id": "en_go"},
    )
    fired: list[bool] = []

    async def _should_not_be_called(**kw):
        fired.append(True)

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _should_not_be_called)

    response = client.get("/search_verb?language=en&q=go", follow_redirects=False)

    location = response.headers["location"]
    assert "/learn" in location
    assert "generating" not in location
    assert not fired


# ---------------------------------------------------------------------------
# Verbs page: generating notice rendered
# ---------------------------------------------------------------------------


def _patch_verbs_page(monkeypatch) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda language: [])
    monkeypatch.setattr("app.routes.verbs.list_verbs_recent", lambda language, limit=8: [])


def test_verbs_page_shows_generating_notice(client: TestClient, monkeypatch) -> None:
    """When generating=1 is in the URL the verbs page shows the countdown notice."""
    _patch_verbs_page(monkeypatch)

    response = client.get(
        "/verbs?language=en&not_available=1&search=book&generating=1",
        follow_redirects=False,
    )

    assert response.status_code == 200
    html = response.text
    assert "vb-notice-countdown" in html
    assert "book" in html


def test_verbs_page_plain_notice_without_generating(client: TestClient, monkeypatch) -> None:
    """Without generating=1, verbs page shows the standard not-found notice."""
    _patch_verbs_page(monkeypatch)

    response = client.get(
        "/verbs?language=en&not_available=1&search=xyzzy",
        follow_redirects=False,
    )

    assert response.status_code == 200
    html = response.text
    assert "vb-notice-countdown" not in html
    assert "xyzzy" in html


def test_verbs_page_no_notice_without_not_available(client: TestClient, monkeypatch) -> None:
    """Without not_available=1 no notice is shown at all."""
    _patch_verbs_page(monkeypatch)

    response = client.get("/verbs?language=en", follow_redirects=False)

    assert response.status_code == 200
    html = response.text
    assert "vb-notice" not in html
