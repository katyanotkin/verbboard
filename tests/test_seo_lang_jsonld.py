"""Study-language `lang` attributes, JSON-LD and no-JS server-rendered tables (issues #115, #116)."""

from __future__ import annotations

import json
import re

import pytest

from core.i18n import get_strings
from core.models import Board, Example, VerbEntry
from core.render import render_board_html
from core.sitemap_service import canonical_learn_url, public_base_url

CASES = [
    # language, verb_id, lemma, form text, example sentence, expected lang
    ("es", "es_hablar", "hablar", "hablo", "Yo hablo con ella.", "es"),
    ("he", "he_ldbr", "לדבר", "מדבר", "אני מדבר איתה.", "he"),
    ("pt", "pt_falar", "falar", "falo", "Eu falo com ela.", "pt-BR"),
]


def _board(language, verb_id, lemma, form, sentence) -> Board:
    verb = VerbEntry(id=verb_id, rank=1, lemma=lemma, forms={}, examples=[Example(dst=sentence)])
    rows = [{"key": "present_1sg", "label": "yo", "text": form, "href": ""}]
    return Board(
        language=language,
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[{"title": "Present", "rows": rows}],
    )


def _render(board, ui_lang="en", **kw) -> str:
    return render_board_html(board, ui_strings=get_strings(ui_lang), ui_lang=ui_lang, **kw)


def _jsonld(page: str) -> list[dict]:
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    return [json.loads(block) for block in blocks]


@pytest.mark.parametrize("language,verb_id,lemma,form,sentence,code", CASES)
def test_lang_attributes_and_no_js_content(language, verb_id, lemma, form, sentence, code) -> None:
    page = _render(_board(language, verb_id, lemma, form, sentence))
    assert re.search(rf"<h1 lang=\"{code}\">{re.escape(lemma)}</h1>", page)
    assert f"<span class='example-src' lang='{code}'>{sentence}</span>" in page
    assert re.search(rf"<span class='form-value' lang='{code}'>{re.escape(form)}</span>", page)
    # #115: the tables and their text are in the initial HTML (no JS needed)
    assert "<table" in page and "conj-form" in page


def test_russian_aspect_pair_title_and_lang() -> None:
    verb = VerbEntry(
        id="ru_delat",
        rank=1,
        lemma={"imperfective": "делать", "perfective": "сделать"},
        forms={},
        examples=[Example(dst="Я делаю уроки.")],
    )
    rows = [{"key": "present_1sg", "label": "я", "text": "делаю", "href": ""}]
    board = Board(
        language="ru", verb=verb, voice_key="female", voice_label="F", sections=[{"title": "Present", "rows": rows}]
    )
    page = _render(board, ui_lang="ru")
    assert '<h1 lang="ru">делать / сделать</h1>' in page
    assert "<span class='example-src' lang='ru'>Я делаю уроки.</span>" in page
    assert "<span class='form-value' lang='ru'>делаю</span>" in page
    assert "<table" in page
    # html lang stays the UI language
    assert re.search(r'<html lang="ru"', page)


def test_html_lang_override_is_only_pt() -> None:
    from core.languages.config import ALL_STUDY_LANGUAGES, html_lang_for

    assert {code: html_lang_for(code) for code in ALL_STUDY_LANGUAGES if html_lang_for(code) != code} == {"pt": "pt-BR"}


def test_breadcrumb_jsonld_is_valid_and_absolute() -> None:
    page = _render(_board("es", "es_hablar", "hablar", "hablo", "Yo hablo."), ui_lang="ru")
    (data,) = _jsonld(page)
    assert data["@type"] == "BreadcrumbList"
    items = data["itemListElement"]
    base = public_base_url()
    assert [i["position"] for i in items] == [1, 2, 3]
    assert items[0]["item"] == f"{base}/"
    assert items[1]["item"] == f"{base}/verbs?language=es&ui_language=en"
    assert items[2]["item"] == canonical_learn_url("es", "es_hablar")
    assert items[2]["name"] == "hablar"
    assert all(i["item"].startswith("http") for i in items)


def test_hostile_lemma_cannot_break_out_of_script() -> None:
    hostile = '"</script><script>alert(1)</script>'
    page = _render(_board("es", "es_x", hostile, "x", "y"))
    block = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    assert block is not None
    assert "<" not in block.group(1) and ">" not in block.group(1)
    (data,) = _jsonld(page)
    assert data["itemListElement"][2]["name"] == hostile
    assert "<script>alert(1)" not in page


def test_line_separators_escaped() -> None:
    from core.seo_meta import jsonld_script_json

    out = jsonld_script_json({"a": "x y z&"})
    assert " " not in out and " " not in out and "&" not in out
    assert json.loads(out)["a"] == "x y z&"


def test_candidate_preview_has_no_jsonld() -> None:
    page = _render(_board("es", "es_hablar", "hablar", "hablo", "Yo hablo."), candidate_verb_id="es_hablar")
    assert "application/ld+json" not in page


def test_home_has_website_jsonld_only() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    page = TestClient(app).get("/?ui_language=en").text
    (data,) = _jsonld(page)
    assert data == {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "VerbBoard",
        "url": f"{public_base_url()}/",
    }
    assert "BreadcrumbList" not in page
