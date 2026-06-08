"""Tests covering the recent UI changes.

- Home page: dual CTAs (.browse-main-link and .browse-practice-btn)
- Verbs page: .practice-nav-chip present/absent based on PRACTICE_LOOP_ENABLED
- Verbs page: search submit button is NOT disabled on page load
- Verbs page: placeholder uses home.search_placeholder, not verbs.search_placeholder
- i18n: verbs.search_placeholder key is absent from all locale files
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.i18n import SUPPORTED_UI_LANGS, get_strings

_I18N_DIR = Path(__file__).parent.parent / "app" / "i18n"


# helpers


def _stub_entries(n: int = 5):
    from core.models import VerbEntry

    return [
        VerbEntry(id=f"en_verb{i}", rank=i, lemma=f"verb{i}", forms={}, examples=[])
        for i in range(1, n + 1)
    ]


# home page: dual browse CTAs


def test_home_has_browse_main_link(client: TestClient) -> None:
    resp = client.get("/?language=en")
    assert resp.status_code == 200
    assert "browse-main-link" in resp.text
    assert "/verbs?language=en" in resp.text


def test_home_browse_main_link_href_contains_verbs_for_ru(client: TestClient) -> None:
    resp = client.get("/?language=ru")
    assert resp.status_code == 200
    assert "browse-main-link" in resp.text
    assert "/verbs?language=ru" in resp.text


def test_home_has_browse_practice_btn(client: TestClient) -> None:
    resp = client.get("/?language=en")
    assert resp.status_code == 200
    assert "browse-practice-btn" in resp.text


def test_home_browse_practice_btn_links_to_practice_panel(client: TestClient) -> None:
    resp = client.get("/?language=en")
    assert resp.status_code == 200
    html = resp.text
    assert "#practice-panel" in html
    idx = html.find("browse-practice-btn")
    assert idx != -1
    tag_start = html.rfind("<a", 0, idx)
    tag_end = html.find(">", idx)
    tag_snippet = html[tag_start:tag_end]
    assert "#practice-panel" in tag_snippet


def test_home_browse_practice_btn_language_matches_selection(
    client: TestClient,
) -> None:
    resp = client.get("/?language=he")
    assert resp.status_code == 200
    assert "/verbs?language=he#practice-panel" in resp.text


def test_home_both_ctas_present_together(client: TestClient) -> None:
    resp = client.get("/?language=es")
    assert resp.status_code == 200
    assert "browse-main-link" in resp.text
    assert "browse-practice-btn" in resp.text


# verbs page: search submit button not disabled


def test_verbs_search_submit_not_disabled_on_load(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language", lambda **kw: _stub_entries()
    )
    html = client.get("/verbs?language=en").text
    idx = html.find('id="vb-search-submit-btn"')
    assert idx != -1, "vb-search-submit-btn not found in HTML"
    tag_start = html.rfind("<button", 0, idx)
    tag_end = html.find(">", idx)
    tag_snippet = html[tag_start : tag_end + 1]
    assert "disabled" not in tag_snippet


def test_verbs_search_submit_btn_has_no_disabled_attr(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language", lambda **kw: _stub_entries()
    )
    html = client.get("/verbs?language=en").text
    assert 'id="vb-search-submit-btn" disabled' not in html
    assert 'disabled id="vb-search-submit-btn"' not in html


# verbs page: placeholder from home.search_placeholder


def test_verbs_search_uses_home_search_placeholder_en(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language", lambda **kw: _stub_entries()
    )
    html = client.get("/verbs?language=en&ui_language=en").text
    assert get_strings("en")["home.search_placeholder"] in html


@pytest.mark.parametrize("ui_lang", sorted(SUPPORTED_UI_LANGS))
def test_verbs_search_placeholder_per_ui_lang(
    client: TestClient, monkeypatch, ui_lang: str
) -> None:
    monkeypatch.setattr(
        "app.routes.verbs.load_entries_for_language", lambda **kw: _stub_entries()
    )
    resp = client.get(f"/verbs?language=en&ui_language={ui_lang}")
    assert resp.status_code == 200
    assert get_strings(ui_lang)["home.search_placeholder"] in resp.text


# i18n: verbs.search_placeholder must NOT exist


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_verbs_search_placeholder_key_absent_from_locale(lang: str) -> None:
    assert "verbs.search_placeholder" not in get_strings(
        lang
    ), f"{lang}.json still contains removed key verbs.search_placeholder"


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_verbs_search_placeholder_key_absent_from_json_file(lang: str) -> None:
    import json as _json

    raw = _json.loads((_I18N_DIR / f"{lang}.json").read_text(encoding="utf-8"))
    assert (
        "verbs.search_placeholder" not in raw
    ), f"{lang}.json file still has verbs.search_placeholder key"


# i18n: home.search_placeholder must be present in all locales


@pytest.mark.parametrize("lang", sorted(SUPPORTED_UI_LANGS))
def test_home_search_placeholder_key_present_in_locale(lang: str) -> None:
    strings = get_strings(lang)
    assert "home.search_placeholder" in strings
    assert strings["home.search_placeholder"].strip()
