from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from core.i18n import SUPPORTED_UI_LANGS, get_strings, resolve_ui_language

_I18N_DIR = Path(__file__).parent.parent / "app" / "i18n"

# ── resource file loading ─────────────────────────────────────────────────────


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_resource_file_loads(lang: str) -> None:
    strings = get_strings(lang)
    assert isinstance(strings, dict)
    assert len(strings) > 0


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_no_empty_values(lang: str) -> None:
    strings = get_strings(lang)
    empty = [k for k, v in strings.items() if not v or not v.strip()]
    assert not empty, f"Empty values in {lang}.json: {empty}"


def test_all_languages_have_same_keys() -> None:
    en_keys = set(get_strings("en").keys())
    for lang in SUPPORTED_UI_LANGS - {"en"}:
        lang_keys = set(get_strings(lang).keys())
        missing = en_keys - lang_keys
        extra = lang_keys - en_keys
        assert not missing, f"{lang}.json is missing keys: {missing}"
        assert not extra, f"{lang}.json has unexpected keys: {extra}"


# ── resolve_ui_language ───────────────────────────────────────────────────────


def _make_request(qp: str = "", accept: str = ""):
    from starlette.requests import Request as StarletteRequest

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": qp.encode(),
        "headers": [(b"accept-language", accept.encode())],
    }
    return StarletteRequest(scope)


def test_resolve_query_param_wins() -> None:
    req = _make_request(qp="ui_language=ru", accept="es")
    assert resolve_ui_language(req) == "ru"


def test_resolve_accept_language() -> None:
    req = _make_request(accept="he-IL,he;q=0.9,en;q=0.8")
    assert resolve_ui_language(req) == "he"


def test_resolve_defaults_to_en() -> None:
    req = _make_request(accept="zh-CN,zh;q=0.9")
    assert resolve_ui_language(req) == "en"


def test_resolve_unsupported_qp_falls_through_to_accept() -> None:
    req = _make_request(qp="ui_language=fr", accept="es")
    assert resolve_ui_language(req) == "es"


# ── route integration ─────────────────────────────────────────────────────────


def test_verbs_russian_ui(client: TestClient) -> None:
    ru = get_strings("ru")
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=[]),
        patch("app.routes.verbs.list_verbs_recent", return_value=[]),
    ):
        resp = client.get("/verbs?language=en&ui_language=ru")
    assert resp.status_code == 200
    assert ru["verbs.heading"] in resp.text
    assert ru["verbs.find_button"] in resp.text


def test_verbs_filter_options_all_present(client: TestClient) -> None:
    with (
        patch("app.routes.verbs.load_entries_for_language", return_value=[]),
        patch("app.routes.verbs.list_verbs_recent", return_value=[]),
    ):
        resp = client.get("/verbs?language=ru&ui_language=ru")
    assert resp.status_code == 200
    assert 'id="vb-filter-toggle"' in resp.text
    for f in ("new", "seen", "known", "all"):
        assert f'value="{f}"' in resp.text, f"filter option '{f}' missing from HTML"


def test_verbs_hebrew_has_rtl(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en&ui_language=he")
    assert resp.status_code == 200
    assert 'dir="rtl"' in resp.text


def test_verbs_has_language_selector(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en&ui_language=en")
    assert resp.status_code == 200
    assert "window.UI" in resp.text


# ── about page i18n ───────────────────────────────────────────────────────────


def test_about_default_lang_is_english(client: TestClient) -> None:
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "VerbBoard" in resp.text
    assert 'lang="en"' in resp.text


def test_about_hebrew_is_rtl(client: TestClient) -> None:
    resp = client.get("/about?ui_language=he")
    assert 'dir="rtl"' in resp.text


def test_about_uses_ui_language_param_not_lang(client: TestClient) -> None:
    ru = get_strings("ru")
    resp = client.get("/about?ui_language=ru")
    assert ru["about.back"] in resp.text
    assert ru["about.feedback"] in resp.text


def test_about_no_lang_toggle_widget(client: TestClient) -> None:
    resp = client.get("/about")
    assert "lang-toggle" not in resp.text
    assert "setLang(" not in resp.text
