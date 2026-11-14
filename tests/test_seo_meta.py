"""Canonical, noindex, title/description and Open Graph tags (issues #102, #104)."""

from __future__ import annotations

import html
import re

import pytest

from core.i18n import get_strings
from core.models import Board, VerbEntry
from core.render import render_board_html
from core.seo_meta import DESCRIPTION_MAX, TITLE_MAX, truncate_at_word


def _board(lemma, language="en", translations=None, verb_id="en_go") -> Board:
    verb = VerbEntry(id=verb_id, rank=1, lemma=lemma, forms={}, examples=[], lemma_translations=translations or {})
    return Board(language=language, verb=verb, voice_key="female", voice_label="Female", sections=[])


def _render(board, ui_lang="en", **kw) -> str:
    return render_board_html(board, ui_strings=get_strings(ui_lang), ui_lang=ui_lang, **kw)


def _meta(page: str, attr: str, name: str) -> str:
    """Content of a meta tag, or "" when the tag is absent."""
    m = re.search(rf'<meta {attr}="{re.escape(name)}" content="([^"]*)"', page)
    return html.unescape(m.group(1)) if m else ""


def _title(page: str) -> str:
    match = re.search(r"<title>(.*?)</title>", page, re.S)
    assert match is not None
    return html.unescape(match.group(1))


def test_canonical_drops_every_other_param() -> None:
    page = _render(
        _board("go"),
        ui_lang="ru",
        return_to="/verbs?language=en&x=1",
        translated_from="идти",
        source_lang="ru",
    )
    canon_match = re.search(r'<link rel="canonical" href="([^"]*)"', page)
    assert canon_match is not None
    canon = canon_match.group(1)
    assert html.unescape(canon) == "https://verbboard.com/learn?language=en&verb_id=en_go&ui_language=en"
    assert _meta(page, "property", "og:url") == html.unescape(canon)
    assert "hreflang" not in page
    assert "noindex" not in page


def test_canonical_uses_public_base_url_setting(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test/")
    page = _render(_board("go"))
    assert 'href="https://example.test/learn?language=en' in page


def test_canonical_url_encodes_verb_id() -> None:
    page = _render(_board("x", verb_id="en_a b&c"))
    assert "verb_id=en_a%20b%26c&amp;ui_language=en" in page


def test_candidate_preview_is_noindex_without_canonical() -> None:
    page = _render(_board("go"), candidate_verb_id="en_go")
    assert '<meta name="robots" content="noindex"/>' in page
    assert 'rel="canonical"' not in page
    assert "og:url" not in page


@pytest.mark.parametrize("ui_lang", ["en", "ru", "he", "es"])
def test_all_ui_locales_have_tags_within_limits(ui_lang: str) -> None:
    page = _render(_board("go", translations={ui_lang: "ir"}), ui_lang=ui_lang)
    title = _title(page)
    desc = _meta(page, "name", "description")
    assert "go" in title and title.endswith("VerbBoard")
    assert len(title) <= TITLE_MAX
    assert desc and len(desc) <= DESCRIPTION_MAX
    assert _meta(page, "property", "og:title") == title
    assert _meta(page, "property", "og:description") == desc
    assert _meta(page, "property", "og:type") == "website"
    assert _meta(page, "property", "og:site_name") == "VerbBoard"
    assert _meta(page, "name", "twitter:card") == "summary"
    assert "og:image" not in page
    assert '<h1 lang="en">go</h1>' in page


def test_translation_in_ui_language_used_in_description() -> None:
    page = _render(_board("go", translations={"es": "ir"}), ui_lang="es")
    assert "(ir)" in _meta(page, "name", "description")


def test_hebrew_ui_is_rtl_with_hebrew_text() -> None:
    page = _render(_board("go", translations={"he": "ללכת"}), ui_lang="he")
    assert 'dir="rtl"' in page
    assert "הטיית go" in _title(page)
    assert "ללכת" in _meta(page, "name", "description")


def test_hebrew_study_language_title() -> None:
    page = _render(_board("לכתוב", language="he", verb_id="he_lktv"), ui_lang="en")
    assert "לכתוב" in _title(page)
    assert "Hebrew" in _meta(page, "name", "description")


def test_russian_pair_lemma_renders_both_aspects() -> None:
    page = _render(_board({"imperfective": "делать", "perfective": "сделать"}, "ru", verb_id="ru_delat"), "en")
    assert "делать / сделать" in _meta(page, "name", "description")
    assert "делать / сделать" in _title(page) or "делать" in _title(page)


def test_lemma_with_quotes_and_angle_brackets_is_escaped() -> None:
    evil = '"><script>alert(1)</script>'
    page = _render(_board(evil, translations={"en": evil}), ui_lang="ru")
    head = page.split("</head>")[0]
    assert "<script>alert(1)" not in head
    assert evil not in head
    assert "&lt;script&gt;" in head


def test_long_lemma_title_and_description_stay_within_limits() -> None:
    long_lemma = "extraordinarily long verb phrase " * 8
    page = _render(_board(long_lemma, translations={"en": long_lemma}), ui_lang="es")
    assert len(_title(page)) <= TITLE_MAX
    assert len(_meta(page, "name", "description")) <= DESCRIPTION_MAX


def test_truncate_at_word_boundary() -> None:
    out = truncate_at_word("alpha beta gamma delta", 14)
    assert out == "alpha beta…"
    assert truncate_at_word("short", 14) == "short"


@pytest.mark.parametrize("ui_lang", ["en", "ru", "he", "es"])
def test_static_page_i18n_keys_present_and_short(ui_lang: str) -> None:
    ui = get_strings(ui_lang)
    for page in ("home", "verbs", "about"):
        assert 0 < len(ui[f"seo.{page}_title"]) <= TITLE_MAX
        assert 0 < len(ui[f"seo.{page}_desc"]) <= DESCRIPTION_MAX
    for key in ("seo.learn_title", "seo.learn_desc", "seo.learn_desc_plain", "seo.learn_desc_short"):
        assert "{lemma}" in ui[key]


def test_static_pages_render_tags_and_noindex_states() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    home = client.get("/?ui_language=ru").text
    assert _title(home) == get_strings("ru")["seo.home_title"]
    assert _meta(home, "property", "og:url") == "https://verbboard.com/"
    assert "noindex" not in home
    assert "noindex" in client.get("/?ui_language=en&not_available=1&search=zzz").text
    about = client.get("/about?ui_language=es").text
    assert _title(about) == get_strings("es")["seo.about_title"]
    verbs = client.get("/verbs?language=en&ui_language=he").text
    assert _title(verbs) == get_strings("he")["seo.verbs_title"]
    assert "noindex" not in verbs


@pytest.mark.parametrize("ui_lang", ["en", "ru", "he", "es"])
def test_about_title_matches_locale_about_title(ui_lang: str) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    page = TestClient(app).get(f"/about?ui_language={ui_lang}").text
    assert _title(page) == get_strings(ui_lang)["about.title"]


_LONG = "extraordinarily long verb phrase that keeps going " * 6
_STUDY_CASES = [
    ("es", "es_hablar", "hablar"),
    ("es", "es_hablar", _LONG),
    ("ru", "ru_delat", {"imperfective": "делать", "perfective": "сделать"}),
    ("ru", "ru_delat", {"imperfective": _LONG, "perfective": _LONG}),
    ("he", "he_lktv", "לכתוב"),
    ("he", "he_lktv", _LONG),
]


@pytest.mark.parametrize("ui_lang", ["en", "ru", "he", "es"])
@pytest.mark.parametrize(("language", "verb_id", "lemma"), _STUDY_CASES)
def test_learn_meta_limits_across_ui_and_study_languages(ui_lang, language, verb_id, lemma) -> None:
    text = lemma if isinstance(lemma, str) else f"{lemma['imperfective']} / {lemma['perfective']}"
    page = _render(_board(lemma, language, translations={ui_lang: text}, verb_id=verb_id), ui_lang=ui_lang)
    assert 0 < len(_title(page)) <= TITLE_MAX
    desc = _meta(page, "name", "description")
    assert desc and len(desc) <= DESCRIPTION_MAX


def test_sitemap_learn_urls_equal_canonical_learn_url(monkeypatch) -> None:
    import xml.etree.ElementTree as ET

    from core import sitemap_service
    from core.sitemap_service import canonical_learn_url

    entries = [VerbEntry(id=i, rank=1, lemma="x", forms={}, examples=[]) for i in ("es_hablar", "es_a b&c")]
    monkeypatch.setattr(sitemap_service, "free_sitemap_languages", lambda: ["es"])
    monkeypatch.setattr(sitemap_service, "load_entries_for_language", lambda language: entries)
    root = ET.fromstring(sitemap_service.build_sitemap_xml())
    locs = {el.text for el in root.iter() if el.tag.endswith("loc")}
    for entry in entries:
        assert canonical_learn_url("es", entry.id) in locs


def test_verbs_page_noindex_only_for_state_params() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    assert "noindex" not in client.get("/verbs?language=es&ui_language=en").text
    miss = client.get("/verbs?language=es&ui_language=en&not_available=1&search=zzz").text
    assert '<meta name="robots" content="noindex"/>' in miss


def _canonical(page: str) -> str:
    m = re.search(r'<link rel="canonical" href="([^"]*)"', page)
    return html.unescape(m.group(1)) if m else ""


def test_static_page_canonicals_drop_variant_params() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    for url in ("/", "/?ui_language=he&language=es"):
        page = client.get(url).text
        assert _canonical(page) == "https://verbboard.com/"
        assert _meta(page, "property", "og:url") == "https://verbboard.com/"
    about = client.get("/about?ui_language=he").text
    assert _canonical(about) == "https://verbboard.com/about"
    assert _meta(about, "property", "og:url") == "https://verbboard.com/about"
    for url in (
        "/verbs?language=es&ui_language=en&focus_search=1",
        "/verbs?language=es&ui_language=he&return_to=%2Fx",
    ):
        page = client.get(url).text
        assert _canonical(page) == "https://verbboard.com/verbs?language=es&ui_language=en"
        assert _meta(page, "property", "og:url") == _canonical(page)
        assert "noindex" not in page


def test_canonical_follows_public_base_url_not_request_host(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test")
    page = TestClient(app, base_url="http://evil.test").get("/about").text
    assert _canonical(page) == "https://example.test/about"


@pytest.mark.parametrize(
    "url",
    [
        "/verbs?language=&ui_language=he",
        "/verbs?language=zz&ui_language=en",
        "/verbs?ui_language=en",
        "/verbs?language=es&ui_language=en&not_available=1&search=zzz",
        "/?ui_language=en&not_available=1&search=zzz",
    ],
)
def test_noindex_pages_have_no_canonical(url: str) -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    page = TestClient(app).get(url).text
    assert '<meta name="robots" content="noindex"/>' in page
    assert 'rel="canonical"' not in page
    assert "og:url" not in page


def test_sitemap_verbs_urls_equal_canonical_verbs_url(monkeypatch) -> None:
    from fastapi.testclient import TestClient

    from app.main import app
    from core.sitemap_service import canonical_verbs_url, free_sitemap_languages

    locs = TestClient(app).get("/sitemap.xml").text
    for language in free_sitemap_languages():
        assert html.escape(canonical_verbs_url(language), quote=False) in locs
