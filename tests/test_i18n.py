from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

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


def _make_request(qp: str = "", cookie: str = "", accept: str = ""):
    from starlette.requests import Request as StarletteRequest

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "query_string": qp.encode(),
        "headers": [
            (b"accept-language", accept.encode()),
            (b"cookie", f"ui_language={cookie}".encode() if cookie else b""),
        ],
    }
    return StarletteRequest(scope)


def test_resolve_query_param_wins() -> None:
    req = _make_request(qp="ui_language=ru", cookie="he", accept="es")
    assert resolve_ui_language(req) == "ru"


def test_resolve_cookie_over_accept() -> None:
    req = _make_request(cookie="es", accept="ru")
    assert resolve_ui_language(req) == "es"


def test_resolve_accept_language() -> None:
    req = _make_request(accept="he-IL,he;q=0.9,en;q=0.8")
    assert resolve_ui_language(req) == "he"


def test_resolve_defaults_to_en() -> None:
    req = _make_request(accept="zh-CN,zh;q=0.9")
    assert resolve_ui_language(req) == "en"


def test_resolve_unsupported_qp_falls_through_to_cookie() -> None:
    req = _make_request(qp="ui_language=fr", cookie="es")
    assert resolve_ui_language(req) == "es"


# ── route integration ─────────────────────────────────────────────────────────


def test_verbs_russian_ui(client: TestClient) -> None:
    ru = get_strings("ru")
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en&ui_language=ru")
    assert resp.status_code == 200
    assert ru["verbs.heading"] in resp.text
    assert ru["verbs.find_button"] in resp.text


def test_verbs_hebrew_has_rtl(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en&ui_language=he")
    assert resp.status_code == 200
    assert 'dir="rtl"' in resp.text


def test_verbs_spanish_cookie(client: TestClient) -> None:
    es = get_strings("es")
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en", cookies={"ui_language": "es"})
    assert resp.status_code == 200
    assert es["verbs.heading"] in resp.text


def test_verbs_has_language_selector(client: TestClient) -> None:
    with patch("app.routes.verbs.load_entries_for_language", return_value=[]):
        resp = client.get("/verbs?language=en&ui_language=en")
    assert resp.status_code == 200
    assert "window.UI" in resp.text


# ── completeness regression ───────────────────────────────────────────────────


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_completeness_vs_english(lang: str) -> None:
    en_keys = set(get_strings("en").keys())
    lang_keys = set(get_strings(lang).keys())
    missing = en_keys - lang_keys
    assert not missing, f"{lang}.json missing keys from en.json: {sorted(missing)}"


# ── about page i18n ───────────────────────────────────────────────────────────


def test_about_default_lang_is_english(client: TestClient) -> None:
    resp = client.get("/about")
    assert resp.status_code == 200
    assert "VerbBoard" in resp.text
    assert 'lang="en"' in resp.text


@pytest.mark.parametrize(
    "lang,title_fragment",
    [
        ("en", "About VerbBoard"),
        ("ru", "О приложении VerbBoard"),
        ("es", "Sobre la app VerbBoard"),
        ("he", "אודות VerbBoard"),
    ],
)
def test_about_title_matches_ui_language(
    client: TestClient, lang: str, title_fragment: str
) -> None:
    resp = client.get(f"/about?ui_language={lang}")
    assert resp.status_code == 200
    assert title_fragment in resp.text


def test_about_hebrew_is_rtl(client: TestClient) -> None:
    resp = client.get("/about?ui_language=he")
    assert 'dir="rtl"' in resp.text


def test_about_uses_ui_language_param_not_lang(client: TestClient) -> None:
    ru = get_strings("ru")
    resp = client.get("/about?ui_language=ru")
    assert ru["about.back"] in resp.text
    assert ru["about.feedback"] in resp.text


def test_about_cookie_resolves_ui_language(client: TestClient) -> None:
    es = get_strings("es")
    resp = client.get("/about", cookies={"ui_language": "es"})
    assert resp.status_code == 200
    assert es["about.title"] in resp.text


def test_about_no_lang_toggle_widget(client: TestClient) -> None:
    resp = client.get("/about")
    assert "lang-toggle" not in resp.text
    assert "setLang(" not in resp.text
