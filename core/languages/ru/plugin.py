from __future__ import annotations

import unicodedata
from typing import Any, cast

from core.languages.config import LANGUAGE
from core.languages.ru.stress import strip_stress_marks
from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register
from core.storage.verb_repository import find_verb_by_lemma
from core.verb_service import generate_and_promote_verb


def _format_aspect(aspect_value: str) -> str:
    if aspect_value == "imperfective":
        return "несовершенный"
    if aspect_value == "perfective":
        return "совершенный"
    if aspect_value == "biaspectual":
        return "двувидовой"
    return aspect_value


def _tense_rows(tense_key: str, tense_forms: dict) -> list:
    labels = [
        ("1sg", "я", "sg"),
        ("2sg", "ты", "sg"),
        ("3sg", "он/она/оно", "sg"),
        ("1pl", "мы", "pl"),
        ("2pl", "вы", "pl"),
        ("3pl", "они", "pl"),
    ]
    return [
        {
            "key": f"{tense_key}_{slot}",
            "label": label,
            "text": tense_forms.get(slot, ""),
            "number": number,
        }
        for slot, label, number in labels
    ]


_PAST_ROW_KEYS = {"m": "past_m", "f": "past_f", "n": "past_n", "pl": "past_pl"}
_IMPERATIVE_ROW_KEYS = {"sg": "imp_sg", "pl": "imp_pl"}


def _display_overrides(display_forms: dict) -> dict[str, str]:
    """Flatten sparse display-only forms (e.g. a stress mark) to row key -> shown text."""
    overrides: dict[str, str] = {}
    for tense_key, tense_forms in display_forms.items():
        for slot, shown in (tense_forms or {}).items():
            if tense_key == "past":
                row_key = _PAST_ROW_KEYS.get(slot)
            elif tense_key == "imperative":
                row_key = _IMPERATIVE_ROW_KEYS.get(slot)
            else:
                row_key = f"{tense_key}_{slot}"
            if row_key and shown:
                overrides[row_key] = shown
    return overrides


def _lookup_pair_lemma_and_href(pair_lemma: str) -> tuple[str, str]:
    normalized_pair_lemma = pair_lemma.strip()
    if not normalized_pair_lemma:
        return "", ""

    doc = find_verb_by_lemma("ru", normalized_pair_lemma)
    if doc is not None:
        return normalized_pair_lemma, f"/learn?language=ru&verb_id={doc['verb_id']}"

    try:
        import asyncio

        asyncio.get_running_loop().run_in_executor(None, lambda: generate_and_promote_verb("ru", normalized_pair_lemma))
    except RuntimeError:
        generate_and_promote_verb("ru", normalized_pair_lemma)

    return f"{normalized_pair_lemma} ⏳", ""


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}
    morph = verb.morph or {}

    raw_aspect = str(morph.get("aspect", ""))
    aspect = _format_aspect(raw_aspect)
    is_perfective = raw_aspect == "perfective"
    is_biaspectual = raw_aspect == "biaspectual"

    pair_value = morph.get("pair")
    pair_lemma_raw = pair_value.strip() if isinstance(pair_value, str) else ""
    pair_lemma, pair_href = _lookup_pair_lemma_and_href(pair_lemma_raw)

    past = forms.get("past", {}) or {}
    imperative = forms.get("imperative", {}) or {}

    metadata_rows = [{"key": "lemma", "label": "глагол", "text": lemma}]
    if aspect:
        metadata_rows.append({"key": "aspect", "label": "вид", "text": aspect})
    if pair_lemma:
        metadata_rows.append({"key": "pair", "label": "пара", "text": pair_lemma, "href": pair_href})

    if is_biaspectual:
        tense_sections: list[dict[str, object]] = [
            {
                "title": "board.tense_present",
                "rows": _tense_rows("present", forms.get("present", {}) or {}),
            },
            {
                "title": "board.tense_future",
                "rows": _tense_rows("future", forms.get("future", {}) or {}),
            },
        ]
    elif is_perfective:
        tense_sections = [
            {
                "title": "board.tense_future",
                "rows": _tense_rows("future", forms.get("future", {}) or {}),
            }
        ]
    else:
        tense_sections = [
            {
                "title": "board.tense_present",
                "rows": _tense_rows("present", forms.get("present", {}) or {}),
            }
        ]

    sections: list[dict[str, object]] = [
        {"rows": metadata_rows},
        *tense_sections,
        {
            "title": "board.tense_past",
            "rows": [
                {"key": "past_m", "label": "он", "text": past.get("m", ""), "gender": "m", "number": "sg"},
                {"key": "past_f", "label": "она", "text": past.get("f", ""), "gender": "f", "number": "sg"},
                {"key": "past_n", "label": "оно", "text": past.get("n", ""), "gender": "n", "number": "sg"},
                {"key": "past_pl", "label": "они", "text": past.get("pl", ""), "number": "pl"},
            ],
        },
        {
            "title": "board.tense_imperative",
            "rows": [
                {"key": "imp_sg", "label": "ты", "text": imperative.get("sg", ""), "number": "sg"},
                {"key": "imp_pl", "label": "вы", "text": imperative.get("pl", ""), "number": "pl"},
            ],
        },
    ]

    # Display-only text (stress marks) is shown on the board, while audio keeps
    # using the plain form: edge-tts reads marked text worse (issue #46).
    overrides = _display_overrides(getattr(verb, "display_forms", None) or {})
    for section in sections:
        for row in cast(list[dict[str, Any]], section["rows"]):
            shown = overrides.get(str(row["key"]))
            plain = str(row["text"] or "")
            # Only a pure stress-marked copy of the current plain form counts, so a
            # stale override left over after a regenerate is ignored.
            if shown and plain and shown != plain and strip_stress_marks(shown) == unicodedata.normalize("NFC", plain):
                row["tts_text"] = row["text"]
                row["text"] = shown

    return Board(
        language="ru",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="ru",
        display_name=LANGUAGE["ru"].display,
        build_board=build_board,
    )
)
