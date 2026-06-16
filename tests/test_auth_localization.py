"""
Tests for localized auth button labels and the translation toggle.

Coverage:
- board page window.UI carries auth.login / auth.logout for every UI language
- verbs page window.UI carries auth.login / auth.logout for every UI language
- home page window.UI carries auth.login / auth.logout for every UI language
- auth labels match the i18n JSON values (not hardcoded English)
- all three pages expose window.UI as a single JSON object assignment
- translation toggle appears whenever ui_lang != verb_lang and a translation exists
- translation toggle is absent when ui_lang == verb_lang
- translation toggle is absent when the translation key is missing for the ui_lang
- full matrix: all (verb_lang, ui_lang) combos with translations present
- window.UI and window.FIREBASE_WEB_CONFIG are in SEPARATE <script> blocks on every page
- empty firebase_web_config_json renders as null (not empty string) so JS is valid
- all three pages expose an auth mount point (#auth-slot or .topbar-actions)
"""

from __future__ import annotations

import dataclasses
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.i18n import SUPPORTED_UI_LANGS, get_strings
from core.models import Board, Example, VerbEntry
from core.render import render_board_html
from core.settings import load_settings as _real_load_settings

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

SUPPORTED_VERB_LANGS = ["en", "ru", "he", "es"]


def _minimal_verb(lang: str, examples: list[Example] | None = None) -> VerbEntry:
    return VerbEntry(
        id=f"{lang}_test",
        rank=1,
        lemma="test",
        forms={},
        examples=examples or [],
    )


def _board(verb: VerbEntry, lang: str = "en") -> Board:
    return Board(
        language=lang,
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[],
    )


def _extract_window_ui(html: str) -> dict:
    """Parse the window.UI = {...}; assignment from rendered HTML.

    All three pages (home, verbs, board) use a single complete JSON object
    assignment: ``window.UI = { ... };``.  This helper finds the first such
    assignment and parses it.
    """
    marker = "window.UI = "
    start = html.index(marker) + len(marker)
    # Locate the matching closing brace by tracking brace depth so that nested
    # objects don't confuse the search.
    depth = 0
    i = start
    while i < len(html):
        ch = html[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
        i += 1
    else:
        raise ValueError("Could not find closing brace for window.UI")
    return json.loads(html[start:end])


def _ui_and_firebase_in_separate_blocks(html: str) -> bool:
    """Return True when window.UI and window.FIREBASE_WEB_CONFIG are in
    different <script> elements.  At least one </script> closing tag must
    appear between the end of the window.UI assignment and the start of the
    window.FIREBASE_WEB_CONFIG assignment."""
    ui_pos = html.find("window.UI = ")
    fb_pos = html.find("window.FIREBASE_WEB_CONFIG = ")
    if ui_pos == -1 or fb_pos == -1:
        return False
    between = html[ui_pos:fb_pos]
    return "</script>" in between


def _settings_no_firebase():
    """Return real settings with firebase_web_config_json cleared to empty string."""
    return dataclasses.replace(_real_load_settings(), firebase_web_config_json="")


# ---------------------------------------------------------------------------
# board page -- auth strings in window.UI
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ui_lang", sorted(SUPPORTED_UI_LANGS))
@pytest.mark.parametrize("auth_key", ["auth.login", "auth.logout"])
def test_board_window_ui_has_auth_key(ui_lang: str, auth_key: str) -> None:
    ui_strings = get_strings(ui_lang)
    verb = _minimal_verb("ru")
    html = render_board_html(_board(verb, "ru"), ui_strings=ui_strings, ui_lang=ui_lang)
    ui = _extract_window_ui(html)
    assert auth_key in ui, f"{auth_key} missing from board window.UI for ui_lang={ui_lang}"
    assert ui[auth_key] == ui_strings[auth_key]


def test_board_auth_labels_are_not_hardcoded_english() -> None:
    """Hebrew board must expose Hebrew auth labels, not 'Login'/'Logout'."""
    he = get_strings("he")
    verb = _minimal_verb("ru")
    html = render_board_html(_board(verb, "ru"), ui_strings=he, ui_lang="he")
    ui = _extract_window_ui(html)
    assert ui["auth.login"] == he["auth.login"]
    assert ui["auth.logout"] == he["auth.logout"]
    assert ui["auth.login"] != "Login"
    assert ui["auth.logout"] != "Logout"


# ---------------------------------------------------------------------------
# verbs page -- auth strings in window.UI
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ui_lang", sorted(SUPPORTED_UI_LANGS))
@pytest.mark.parametrize("auth_key", ["auth.login", "auth.logout"])
def test_verbs_window_ui_has_auth_key(client: TestClient, ui_lang: str, auth_key: str) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get(f"/verbs?language=en&ui_language={ui_lang}")
    assert resp.status_code == 200
    ui = _extract_window_ui(resp.text)
    expected = get_strings(ui_lang)[auth_key]
    assert auth_key in ui, f"{auth_key} missing from verbs window.UI for ui_lang={ui_lang}"
    assert ui[auth_key] == expected


def test_verbs_auth_labels_are_not_hardcoded_english(client: TestClient) -> None:
    """Russian verbs page must expose Russian auth labels."""
    ru = get_strings("ru")
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=ru&ui_language=ru")
    assert resp.status_code == 200
    ui = _extract_window_ui(resp.text)
    assert ui["auth.login"] == ru["auth.login"]
    assert ui["auth.logout"] == ru["auth.logout"]
    assert ui["auth.login"] != "Login"
    assert ui["auth.logout"] != "Logout"


# ---------------------------------------------------------------------------
# home page -- auth strings in window.UI
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ui_lang", sorted(SUPPORTED_UI_LANGS))
@pytest.mark.parametrize("auth_key", ["auth.login", "auth.logout"])
def test_home_window_ui_has_auth_key(client: TestClient, ui_lang: str, auth_key: str) -> None:
    with (
        patch("app.routes.home.list_verbs_recent", return_value=[]),
        patch("app.routes.home.list_verbs_recent", return_value=[]),
    ):
        resp = client.get(f"/?ui_language={ui_lang}")
    assert resp.status_code == 200
    ui = _extract_window_ui(resp.text)
    expected = get_strings(ui_lang)[auth_key]
    assert auth_key in ui, f"{auth_key} missing from home window.UI for ui_lang={ui_lang}"
    assert ui[auth_key] == expected


def test_home_auth_labels_are_not_hardcoded_english(client: TestClient) -> None:
    """Spanish home page must expose Spanish auth labels."""
    es = get_strings("es")
    with (
        patch("app.routes.home.list_verbs_recent", return_value=[]),
        patch("app.routes.home.list_verbs_recent", return_value=[]),
    ):
        resp = client.get("/?ui_language=es")
    assert resp.status_code == 200
    ui = _extract_window_ui(resp.text)
    assert ui["auth.login"] == es["auth.login"]
    assert ui["auth.logout"] == es["auth.logout"]
    assert ui["auth.login"] != "Login"
    assert ui["auth.logout"] != "Logout"


# ---------------------------------------------------------------------------
# all three pages use the shared _firebase_auth.html include
# ---------------------------------------------------------------------------


def test_verbs_uses_shared_firebase_include(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en")
    assert resp.status_code == 200
    assert resp.text.count("firebase-app-compat.js") == 1
    assert resp.text.count("/static/auth.js") == 1


def test_home_uses_shared_firebase_include(client: TestClient) -> None:
    with (
        patch("app.routes.home.list_verbs_recent", return_value=[]),
        patch("app.routes.home.list_verbs_recent", return_value=[]),
    ):
        resp = client.get("/")
    assert resp.status_code == 200
    assert resp.text.count("firebase-app-compat.js") == 1
    assert resp.text.count("/static/auth.js") == 1


# ---------------------------------------------------------------------------
# window.UI and window.FIREBASE_WEB_CONFIG must be in separate <script> blocks
# so that an empty/invalid Firebase config never prevents window.UI from loading
# ---------------------------------------------------------------------------


def test_board_ui_and_firebase_config_in_separate_script_blocks() -> None:
    """window.UI and window.FIREBASE_WEB_CONFIG must not share a <script> tag."""
    verb = _minimal_verb("en")
    html = render_board_html(_board(verb, "en"), ui_strings=get_strings("en"))
    assert _ui_and_firebase_in_separate_blocks(html), (
        "board: window.UI and window.FIREBASE_WEB_CONFIG are in the same <script> block"
    )


def test_verbs_ui_and_firebase_config_in_separate_script_blocks(
    client: TestClient,
) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en")
    assert resp.status_code == 200
    assert _ui_and_firebase_in_separate_blocks(resp.text), (
        "verbs: window.UI and window.FIREBASE_WEB_CONFIG are in the same <script> block"
    )


def test_home_ui_and_firebase_config_in_separate_script_blocks(
    client: TestClient,
) -> None:
    with (
        patch("app.routes.home.list_verbs_recent", return_value=[]),
        patch("app.routes.home.list_verbs_recent", return_value=[]),
    ):
        resp = client.get("/")
    assert resp.status_code == 200
    assert _ui_and_firebase_in_separate_blocks(resp.text), (
        "home: window.UI and window.FIREBASE_WEB_CONFIG are in the same <script> block"
    )


# ---------------------------------------------------------------------------
# empty firebase_web_config_json must render as null, not bare empty string
# (bare empty string produces a JS syntax error that kills the whole block)
# ---------------------------------------------------------------------------


def test_board_empty_firebase_config_renders_null() -> None:
    """render_board_html with no firebase config must emit null, not ''."""
    verb = _minimal_verb("en")
    # default firebase_web_config_json="" (not passed)
    html = render_board_html(_board(verb, "en"), ui_strings=get_strings("en"))
    assert "window.FIREBASE_WEB_CONFIG = null;" in html, "board: empty firebase config must render as null"
    assert "window.FIREBASE_WEB_CONFIG = ;" not in html


def test_verbs_empty_firebase_config_renders_null(client: TestClient) -> None:
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=[]),
        patch("app.routes.verbs.load_settings", side_effect=_settings_no_firebase),
    ):
        resp = client.get("/verbs?language=en")
    assert resp.status_code == 200
    assert "window.FIREBASE_WEB_CONFIG = null;" in resp.text, "verbs: empty firebase config must render as null"
    assert "window.FIREBASE_WEB_CONFIG = ;" not in resp.text


def test_home_empty_firebase_config_renders_null(client: TestClient) -> None:
    with (
        patch("app.routes.home.list_verbs_recent", return_value=[]),
        patch("app.routes.home.list_verbs_recent", return_value=[]),
        patch("app.routes.home.load_settings", side_effect=_settings_no_firebase),
    ):
        resp = client.get("/")
    assert resp.status_code == 200
    assert "window.FIREBASE_WEB_CONFIG = null;" in resp.text, "home: empty firebase config must render as null"
    assert "window.FIREBASE_WEB_CONFIG = ;" not in resp.text


# ---------------------------------------------------------------------------
# all three pages must expose an auth mount point for auth.js
# ---------------------------------------------------------------------------


def test_board_has_topbar_actions_auth_mount() -> None:
    """learn page must have #auth-slot where auth.js appends the button."""
    verb = _minimal_verb("en")
    html = render_board_html(_board(verb, "en"), ui_strings=get_strings("en"))
    assert 'id="auth-slot"' in html


def test_verbs_has_auth_slot(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en")
    assert resp.status_code == 200
    assert 'id="auth-slot"' in resp.text


def test_home_has_auth_slot(client: TestClient) -> None:
    with (
        patch("app.routes.home.list_verbs_recent", return_value=[]),
        patch("app.routes.home.list_verbs_recent", return_value=[]),
    ):
        resp = client.get("/")
    assert resp.status_code == 200
    assert 'id="auth-slot"' in resp.text


# ---------------------------------------------------------------------------
# translation toggle -- parametrized matrix
# ---------------------------------------------------------------------------

_TRANSLATIONS_ALL = {
    "en": "I go home.",
    "ru": "Я иду домой.",
    "he": "אני הולך הביתה.",
    "es": "Voy a casa.",
}


def _render_with_translation(verb_lang: str, ui_lang: str) -> str:
    translation = {k: v for k, v in _TRANSLATIONS_ALL.items() if k != verb_lang}
    examples = [Example(dst="source sentence", translations=translation)]
    verb = _minimal_verb(verb_lang, examples)
    return render_board_html(
        _board(verb, verb_lang),
        ui_strings=get_strings(ui_lang),
        ui_lang=ui_lang,
    )


_TOGGLE_VISIBLE_CASES = [(vl, ul) for vl in SUPPORTED_VERB_LANGS for ul in SUPPORTED_VERB_LANGS if ul != vl]


@pytest.mark.parametrize("verb_lang,ui_lang", _TOGGLE_VISIBLE_CASES)
def test_toggle_visible_when_ui_lang_differs_from_verb_lang(verb_lang: str, ui_lang: str) -> None:
    html = _render_with_translation(verb_lang, ui_lang)
    assert "toggle-translations" in html, f"toggle missing: verb_lang={verb_lang}, ui_lang={ui_lang}"


@pytest.mark.parametrize("lang", SUPPORTED_VERB_LANGS)
def test_toggle_absent_when_ui_lang_equals_verb_lang(lang: str) -> None:
    translation = {k: v for k, v in _TRANSLATIONS_ALL.items() if k != lang}
    examples = [Example(dst="source sentence", translations=translation)]
    verb = _minimal_verb(lang, examples)
    html = render_board_html(
        _board(verb, lang),
        ui_strings=get_strings(lang),
        ui_lang=lang,
    )
    assert "toggle-translations" not in html, f"toggle should be absent when verb_lang == ui_lang == {lang}"


@pytest.mark.parametrize("verb_lang", SUPPORTED_VERB_LANGS)
def test_toggle_absent_when_no_examples_have_translations(verb_lang: str) -> None:
    verb = _minimal_verb(verb_lang, [Example(dst="source sentence")])

    other_lang = next(lang for lang in SUPPORTED_VERB_LANGS if lang != verb_lang)

    html = render_board_html(
        _board(verb, verb_lang),
        ui_strings=get_strings(other_lang),
        ui_lang=other_lang,
    )

    assert 'class="toggle-translations"' not in html


@pytest.mark.parametrize(
    "verb_lang,ui_lang,translation_langs",
    [
        ("ru", "he", ["en"]),
        ("en", "es", ["ru"]),
        ("he", "ru", ["en", "es"]),
    ],
)
def test_toggle_absent_when_translation_missing_for_ui_lang(
    verb_lang: str, ui_lang: str, translation_langs: list[str]
) -> None:
    translation = {k: _TRANSLATIONS_ALL[k] for k in translation_langs}
    examples = [Example(dst="source sentence", translations=translation)]
    verb = _minimal_verb(verb_lang, examples)
    html = render_board_html(
        _board(verb, verb_lang),
        ui_strings=get_strings(ui_lang),
        ui_lang=ui_lang,
    )
    assert "toggle-translations" not in html, f"toggle should be absent: ui_lang={ui_lang} not in {translation_langs}"
