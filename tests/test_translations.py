"""
Tests for the inline translation feature:
  - verb_loader reads translations from Firestore documents
  - render_board_html populates spans and RTL attribute correctly
  - generate_and_promote_verb persists translations for all 4 languages

Toggle show/hide logic (absent when no translations, absent when ui_lang==verb_lang,
absent when translation key missing, present when available) is covered by
test_auth_localization.py::test_toggle_* parametrized tests.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from core.models import Board, Example, VerbEntry
from core.render import render_board_html

SUPPORTED_LANGS = ["en", "ru", "he", "es"]


def _other_langs(verb_lang: str) -> list[str]:
    return [lang for lang in SUPPORTED_LANGS if lang != verb_lang]


def _render(verb_lang: str, ui_lang: str, examples: list[Example]) -> str:
    verb = VerbEntry(
        id=f"{verb_lang}_test", rank=1, lemma="test", forms={}, examples=examples
    )
    board = Board(
        language=verb_lang,
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[],
    )
    return render_board_html(board, ui_lang=ui_lang)


# ---------------------------------------------------------------------------
# verb_loader — reading translations from Firestore documents
# ---------------------------------------------------------------------------


def test_firestore_document_reads_translations() -> None:
    from core.verb_loader import _firestore_document_to_verb_entry

    doc = {
        "verb_id": "ru_idti",
        "rank": 1,
        "lemma": "идти",
        "forms": {},
        "examples": [
            {
                "dst": "Я иду домой.",
                "translations": {"en": "I'm going home.", "he": "אני הולך הביתה."},
            },
        ],
    }
    entry = _firestore_document_to_verb_entry(doc)
    assert entry.examples[0].translations["en"] == "I'm going home."
    assert entry.examples[0].translations["he"] == "אני הולך הביתה."


def test_firestore_document_without_translations_gives_empty_dict() -> None:
    from core.verb_loader import _firestore_document_to_verb_entry

    doc = {
        "verb_id": "en_go",
        "rank": 1,
        "lemma": "go",
        "forms": {},
        "examples": [{"dst": "I go to school."}],
    }
    entry = _firestore_document_to_verb_entry(doc)
    assert entry.examples[0].translations == {}


def test_firestore_document_ignores_non_string_translation_values() -> None:
    from core.verb_loader import _firestore_document_to_verb_entry

    doc = {
        "verb_id": "es_ir",
        "rank": 1,
        "lemma": "ir",
        "forms": {},
        "examples": [
            {"dst": "Voy.", "translations": {"en": "I go.", "ru": 42, "he": None}}
        ],
    }
    entry = _firestore_document_to_verb_entry(doc)
    assert entry.examples[0].translations == {"en": "I go."}


# ---------------------------------------------------------------------------
# render_board_html — translation span content and RTL attribute
# ---------------------------------------------------------------------------


def test_translation_text_rendered_in_span() -> None:
    html = _render(
        "ru",
        "en",
        [Example(dst="Я иду домой.", translations={"en": "I'm going home."})],
    )
    assert "I&#x27;m going home." in html or "I'm going home." in html


def test_translation_not_leaked_when_ui_lang_matches_verb_lang() -> None:
    html = _render(
        "ru",
        "ru",
        [Example(dst="Я иду домой.", translations={"en": "I'm going home."})],
    )
    assert "I'm going home." not in html


def test_hebrew_ui_translation_span_has_rtl_dir() -> None:
    html = _render(
        "en", "he", [Example(dst="I go home.", translations={"he": "אני הולך הביתה."})]
    )
    assert "dir='rtl'" in html
    assert "אני הולך הביתה." in html


# ---------------------------------------------------------------------------
# generate_and_promote_verb — translations persisted for all 4 languages
# ---------------------------------------------------------------------------

_FIXTURES: dict[str, dict[str, Any]] = {
    "en": {
        "lemma": "go",
        "morph": {},
        "forms": {
            "base": "go",
            "past": "went",
            "past_participle": "gone",
            "present_3sg": "goes",
            "gerund": "going",
        },
        "examples": [
            {
                "dst": "I go to school.",
                "translations": {
                    "ru": "Я иду в школу.",
                    "he": "אני הולך לבית הספר.",
                    "es": "Voy a la escuela.",
                },
            },
            {
                "dst": "She goes to the gym.",
                "translations": {
                    "ru": "Она ходит в зал.",
                    "he": "היא הולכת לחדר כושר.",
                    "es": "Ella va al gimnasio.",
                },
            },
        ],
    },
    "ru": {
        "lemma": "идти",
        "morph": {"aspect": "imperfective", "pair": "пойти"},
        "forms": {
            "present": {
                "1sg": "иду",
                "2sg": "идёшь",
                "3sg": "идёт",
                "1pl": "идём",
                "2pl": "идёте",
                "3pl": "идут",
            },
            "past": {"m": "шёл", "f": "шла", "n": "шло", "pl": "шли"},
            "imperative": {"sg": "иди", "pl": "идите"},
        },
        "pronoun_forms": {
            "m": "он шёл",
            "f": "она шла",
            "n": "оно шло",
            "pl": "они шли",
        },
        "examples": [
            {
                "dst": "Я иду домой.",
                "translations": {
                    "en": "I'm going home.",
                    "he": "אני הולך הביתה.",
                    "es": "Voy a casa.",
                },
            },
            {
                "dst": "Оно шло медленно.",
                "translations": {
                    "en": "It moved slowly.",
                    "he": "זה הלך לאט.",
                    "es": "Iba despacio.",
                },
            },
        ],
    },
    "he": {
        "lemma": "לָלֶכֶת",
        "morph": {"binyan": "פָּעַל", "root": "ה.ל.כ"},
        "forms": {
            "present": {
                "m_sg": "הולך",
                "f_sg": "הולכת",
                "m_pl": "הולכים",
                "f_pl": "הולכות",
            },
            "past": {
                "1sg": "הלכתי",
                "2msg": "הלכת",
                "2fsg": "הלכת",
                "3msg": "הלך",
                "3fsg": "הלכה",
                "1pl": "הלכנו",
                "2mpl": "הלכתם",
                "2fpl": "הלכתן",
                "3pl": "הלכו",
            },
            "future": {
                "1sg": "אלך",
                "2msg": "תלך",
                "2fsg": "תלכי",
                "3msg": "ילך",
                "3fsg": "תלך",
                "1pl": "נלך",
                "2mpl": "תלכו",
                "2fpl": "תלכו",
                "3pl": "ילכו",
            },
            "imperative": {"ms": "לך", "fs": "לכי", "mp": "לכו", "fp": "לכו"},
        },
        "examples": [
            {
                "dst": "אני הולך הביתה.",
                "translations": {
                    "en": "I'm going home.",
                    "ru": "Я иду домой.",
                    "es": "Voy a casa.",
                },
            },
        ],
    },
    "es": {
        "lemma": "ir",
        "morph": {},
        "forms": {
            "present": {
                "yo": "voy",
                "tu": "vas",
                "el": "va",
                "nos": "vamos",
                "ellos": "van",
            },
            "preterite": {
                "yo": "fui",
                "tu": "fuiste",
                "el": "fue",
                "nos": "fuimos",
                "ellos": "fueron",
            },
            "imperative": {
                "tu": "ve",
                "vosotros": "id",
                "usted": "vaya",
                "ustedes": "vayan",
            },
            "gerund": "yendo",
            "participle": "ido",
        },
        "examples": [
            {
                "dst": "Voy a la escuela.",
                "translations": {
                    "en": "I go to school.",
                    "ru": "Я иду в школу.",
                    "he": "אני הולך לבית הספר.",
                },
            },
        ],
    },
}


def _make_mocks(fixture: dict[str, Any]) -> tuple[MagicMock, list[dict], MagicMock]:
    written: list[dict] = []
    doc_ref = MagicMock()
    doc_ref.get.return_value = MagicMock(exists=False)
    doc_ref.set.side_effect = lambda d: written.append(d)
    collection_mock = MagicMock()
    collection_mock.where.return_value.stream.return_value = iter([])
    collection_mock.document.return_value = doc_ref
    db_mock = MagicMock()
    db_mock.collection.return_value = collection_mock
    get_db_mock = MagicMock(return_value=db_mock)

    message_mock = MagicMock()
    message_mock.content = [MagicMock(text=json.dumps(fixture))]
    client_mock = MagicMock()
    client_mock.messages.create.return_value = message_mock
    anthropic_cls = MagicMock(return_value=client_mock)

    return get_db_mock, written, anthropic_cls


@pytest.mark.parametrize("verb_lang", SUPPORTED_LANGS)
def test_generated_verb_examples_have_translations_for_all_other_langs(
    verb_lang: str,
) -> None:
    fixture = _FIXTURES[verb_lang]
    get_db_mock, written, anthropic_cls = _make_mocks(fixture)

    with (
        patch("core.verb_service.anthropic.Anthropic", anthropic_cls),
        patch("core.verb_service._load_anthropic_api_key", return_value="test-key"),
        patch("core.verb_service.get_db", get_db_mock),
    ):
        from core.verb_service import generate_and_promote_verb

        result = generate_and_promote_verb(verb_lang, fixture["lemma"])

    assert result is not None
    assert len(written) == 1
    examples = written[0].get("examples", [])
    assert examples

    for i, ex in enumerate(examples):
        translations = ex.get("translations", {})
        for target in _other_langs(verb_lang):
            assert (
                target in translations
            ), f"example {i} lang={verb_lang}: missing translation for '{target}'"
            assert translations[
                target
            ].strip(), f"example {i} lang={verb_lang}: empty translation for '{target}'"


# ---------------------------------------------------------------------------
# /learn URL flow — toggle and span content in rendered HTML
# ---------------------------------------------------------------------------

_RU_VERB_WITH_TRANSLATIONS = VerbEntry(
    id="ru_viset",
    rank=1,
    lemma="висеть",
    forms={
        "present": {
            "1sg": "вишу",
            "2sg": "висишь",
            "3sg": "висит",
            "1pl": "висим",
            "2pl": "висите",
            "3pl": "висят",
        },
        "past": {"m": "висел", "f": "висела", "n": "висело", "pl": "висели"},
        "imperative": {"sg": "виси", "pl": "висите"},
    },
    examples=[
        Example(
            dst="Картина висит на стене.",
            translations={
                "en": "The painting hangs on the wall.",
                "he": "התמונה תלויה על הקיר.",
                "es": "El cuadro está colgado en la pared.",
            },
        ),
        Example(
            dst="Пальто висело на вешалке.",
            translations={
                "en": "The coat was hanging on the rack.",
                "he": "המעיל היה תלוי על הקולב.",
                "es": "El abrigo estaba colgado en el perchero.",
            },
        ),
    ],
)


@pytest.mark.parametrize(
    "ui_lang,expected_phrase",
    [
        ("en", "The painting hangs on the wall."),
        ("he", "התמונה תלויה על הקיר."),
        ("es", "El cuadro está colgado en la pared."),
    ],
)
def test_learn_url_toggle_appears_for_translated_verb(
    client, monkeypatch, ui_lang: str, expected_phrase: str
) -> None:
    from tests.conftest import noop_ensure_audio

    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: _RU_VERB_WITH_TRANSLATIONS,
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)

    resp = client.get(f"/learn?language=ru&verb_id=ru_viset&ui_language={ui_lang}")
    assert resp.status_code == 200
    assert "toggle-translations" in resp.text, "toggle button missing"
    assert (
        expected_phrase in resp.text
    ), f"translation phrase not found for ui_lang={ui_lang}"


def test_learn_url_no_toggle_when_ui_lang_matches_verb_lang(
    client, monkeypatch
) -> None:
    from tests.conftest import noop_ensure_audio

    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: _RU_VERB_WITH_TRANSLATIONS,
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)

    resp = client.get("/learn?language=ru&verb_id=ru_viset&ui_language=ru")
    assert resp.status_code == 200
    assert "toggle-translations" not in resp.text


def test_learn_url_no_toggle_without_translations(client, monkeypatch) -> None:
    from tests.conftest import noop_ensure_audio

    verb_no_translations = VerbEntry(
        id="ru_viset",
        rank=1,
        lemma="висеть",
        forms={},
        examples=[Example(dst="Картина висит на стене.")],
    )
    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: verb_no_translations,
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)

    resp = client.get("/learn?language=ru&verb_id=ru_viset&ui_language=en")
    assert resp.status_code == 200
    assert "toggle-translations" not in resp.text
