"""Tests for on-the-spot verb generation (core/verb_autogen.py).

Covers:
- is_plausible_verb_query gate: valid and invalid inputs
- /search_verb: autogen triggered (generating=1 in redirect) for EN/ES miss
- /search_verb: autogen NOT triggered for HE/RU miss or garbage queries
- /verbs: generating notice rendered when generating=1 in URL
"""

from __future__ import annotations

from unittest.mock import patch

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

    # -- Newly-supported languages (it, fr) + accented-char bug fix (issue #30) --

    def test_valid_italian_word(self):
        assert is_plausible_verb_query("parlare", "it") is True

    def test_valid_french_word(self):
        assert is_plausible_verb_query("parler", "fr") is True

    def test_accepts_french_accented(self):
        assert is_plausible_verb_query("être", "fr") is True

    def test_accepts_french_accented_multi_diacritic(self):
        assert is_plausible_verb_query("préférer", "fr") is True

    def test_accepts_italian_accented(self):
        assert is_plausible_verb_query("però", "it") is True

    def test_accepts_italian_accented_double_letter(self):
        assert is_plausible_verb_query("città", "it") is True

    def test_accepts_spanish_accented_n_tilde(self):
        """Regression: reñir was incorrectly rejected before the accented-char fix."""
        assert is_plausible_verb_query("reñir", "es") is True

    def test_accepts_spanish_accented_n_tilde_second_word(self):
        assert is_plausible_verb_query("soñar", "es") is True

    def test_rejects_cyrillic_for_french(self):
        assert is_plausible_verb_query("бежать", "fr") is False

    def test_rejects_cyrillic_for_italian(self):
        assert is_plausible_verb_query("бежать", "it") is False

    def test_rejects_hebrew_for_french(self):
        assert is_plausible_verb_query("ללכת", "fr") is False

    def test_rejects_hebrew_for_italian(self):
        assert is_plausible_verb_query("ללכת", "it") is False

    def test_translation_targets_for_italian(self):
        from core.verb_autogen import _TRANSLATION_TARGETS

        assert _TRANSLATION_TARGETS["it"] == ["en", "ru", "es"]

    def test_translation_targets_for_french(self):
        from core.verb_autogen import _TRANSLATION_TARGETS

        assert _TRANSLATION_TARGETS["fr"] == ["en", "ru", "es"]

    def test_translation_targets_never_include_hebrew(self):
        from core.verb_autogen import _TRANSLATION_TARGETS

        for language, targets in _TRANSLATION_TARGETS.items():
            assert "he" not in targets, f"{language} target list must not include Hebrew"

    def test_translation_targets_cover_every_other_ui_language(self):
        from core.languages.config import UI_LANGUAGES
        from core.verb_autogen import _TRANSLATION_TARGETS, AUTOGEN_LANGUAGES

        gemini_ui_languages = {lang for lang in UI_LANGUAGES if lang != "he"}
        for language in AUTOGEN_LANGUAGES:
            expected = gemini_ui_languages - {language}
            assert set(_TRANSLATION_TARGETS[language]) == expected, (
                f"{language} should target {sorted(expected)}, got {sorted(_TRANSLATION_TARGETS[language])}"
            )

    # -- Script gate now sourced from core.languages.config.STUDY_LANGUAGE_SCRIPTS
    # (issue #31 prep) -- these monkeypatch AUTOGEN_LANGUAGES to include "ru" so
    # the script-gate logic itself is exercised end-to-end even before Russian
    # is actually flipped on for real.

    def test_accepts_cyrillic_for_russian_once_enabled(self, monkeypatch):
        import core.verb_autogen as va

        monkeypatch.setattr(va, "AUTOGEN_LANGUAGES", frozenset({"ru"}))
        assert va.is_plausible_verb_query("бежать", "ru") is True

    def test_accepts_uppercase_cyrillic_once_enabled(self, monkeypatch):
        import core.verb_autogen as va

        monkeypatch.setattr(va, "AUTOGEN_LANGUAGES", frozenset({"ru"}))
        assert va.is_plausible_verb_query("Бежать", "ru") is True

    def test_rejects_latin_for_russian_once_enabled(self, monkeypatch):
        import core.verb_autogen as va

        monkeypatch.setattr(va, "AUTOGEN_LANGUAGES", frozenset({"ru"}))
        assert va.is_plausible_verb_query("run", "ru") is False

    def test_rejects_mixed_script_for_russian_once_enabled(self, monkeypatch):
        import core.verb_autogen as va

        monkeypatch.setattr(va, "AUTOGEN_LANGUAGES", frozenset({"ru"}))
        assert va.is_plausible_verb_query("бежatь", "ru") is False

    def test_rejects_hebrew_for_russian_once_enabled(self, monkeypatch):
        import core.verb_autogen as va

        monkeypatch.setattr(va, "AUTOGEN_LANGUAGES", frozenset({"ru"}))
        assert va.is_plausible_verb_query("ללכת", "ru") is False

    def test_script_gate_unaffected_for_currently_enabled_languages(self):
        # Refactor safety net: the config-driven gate must not change behavior
        # for en/es/it/fr, which is exactly what the full existing test suite
        # above already exercises -- this just pins the two representative
        # accented-char cases directly against the new STUDY_LANGUAGE_SCRIPTS
        # source of truth, rather than a since-removed local dict.
        from core.languages.config import STUDY_LANGUAGE_SCRIPTS

        assert STUDY_LANGUAGE_SCRIPTS["fr"].extra_letters == "àâäéèêëïîôöùûüÿçœæ"
        assert STUDY_LANGUAGE_SCRIPTS["es"].extra_letters == "ñ"
        assert STUDY_LANGUAGE_SCRIPTS["en"].extra_letters == ""
        assert STUDY_LANGUAGE_SCRIPTS["en"].ascii_ok is True
        assert STUDY_LANGUAGE_SCRIPTS["ru"].ascii_ok is False


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


def test_autogen_fires_for_it_miss(client: TestClient, monkeypatch) -> None:
    """IT search miss with a plausible query redirects with generating=1."""
    _patch_search_miss(monkeypatch)

    async def _noop(**kw):
        pass

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _noop)

    response = client.get("/search_verb?language=it&q=parlare", follow_redirects=False)

    location = response.headers["location"]
    assert "generating=1" in location


def test_autogen_fires_for_fr_miss(client: TestClient, monkeypatch) -> None:
    """FR search miss with a plausible query redirects with generating=1.

    French is the sole Plus-only study language (core/entitlements.py); the
    entitlement gate is forced open here (mirroring test_entitlement_gate.py's
    pattern) so this test isolates the autogen trigger from Plus-gating.
    """
    _patch_search_miss(monkeypatch)

    async def _noop(**kw):
        pass

    monkeypatch.setattr("app.routes.home.autogenerate_missing_verb", _noop)

    with (
        patch("app.routes.home.can_study", return_value=True),
        patch("app.routes.home.get_session_uid", return_value="user-1"),
    ):
        response = client.get("/search_verb?language=fr&q=parler", follow_redirects=False)

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


# ---------------------------------------------------------------------------
# autogen_rate_limited (core/verb_autogen.py) -- caps paid-LLM-call exposure
# per client IP, independent of the exact-string _GENERATING dedup.
# ---------------------------------------------------------------------------


class TestAutogenRateLimited:
    def test_default_limiter_matches_documented_budget(self) -> None:
        """5 calls / 600s per key, per the module docstring/comment."""
        import core.verb_autogen as va

        assert va._AUTOGEN_RATE_LIMITER._max_calls == 5
        assert va._AUTOGEN_RATE_LIMITER._window_seconds == 600

    def test_allows_up_to_max_calls_then_blocks_same_ip(self, monkeypatch) -> None:
        import core.verb_autogen as va
        from core.rate_limit import SlidingWindowRateLimiter

        # Fresh limiter instance so this test can't be polluted by (or pollute)
        # the real module-level singleton shared with live request handling.
        monkeypatch.setattr(va, "_AUTOGEN_RATE_LIMITER", SlidingWindowRateLimiter(max_calls=5, window_seconds=600))

        ip = "203.0.113.10"
        for _ in range(5):
            assert va.autogen_rate_limited(ip) is False

        assert va.autogen_rate_limited(ip) is True

    def test_different_ip_has_its_own_quota(self, monkeypatch) -> None:
        import core.verb_autogen as va
        from core.rate_limit import SlidingWindowRateLimiter

        monkeypatch.setattr(va, "_AUTOGEN_RATE_LIMITER", SlidingWindowRateLimiter(max_calls=1, window_seconds=600))

        assert va.autogen_rate_limited("198.51.100.1") is False
        assert va.autogen_rate_limited("198.51.100.1") is True
        # A different client IP must not be affected by the first IP's quota.
        assert va.autogen_rate_limited("198.51.100.2") is False

    def test_autogen_rate_limited_inverts_limiter_allow(self, monkeypatch) -> None:
        """autogen_rate_limited() returns True exactly when the underlying
        limiter's allow() would return False."""
        import core.verb_autogen as va
        from core.rate_limit import SlidingWindowRateLimiter

        monkeypatch.setattr(va, "_AUTOGEN_RATE_LIMITER", SlidingWindowRateLimiter(max_calls=1, window_seconds=600))

        assert va.autogen_rate_limited("192.0.2.1") is False
        assert va.autogen_rate_limited("192.0.2.1") is True
