from __future__ import annotations

from core.languages.config import LANGUAGE
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
        ("1sg", "я"),
        ("2sg", "ты"),
        ("3sg", "он/она/оно"),
        ("1pl", "мы"),
        ("2pl", "вы"),
        ("3pl", "они"),
    ]
    return [
        {
            "key": f"{tense_key}_{slot}",
            "label": label,
            "text": tense_forms.get(slot, ""),
        }
        for slot, label in labels
    ]


def _lookup_pair_lemma_and_href(pair_lemma: str) -> tuple[str, str]:
    normalized_pair_lemma = pair_lemma.strip()
    if not normalized_pair_lemma:
        return "", ""

    doc = find_verb_by_lemma("ru", normalized_pair_lemma)
    if doc is not None:
        return normalized_pair_lemma, f"/learn?language=ru&verb_id={doc['verb_id']}"

    try:
        import asyncio

        asyncio.get_running_loop().run_in_executor(
            None, lambda: generate_and_promote_verb("ru", normalized_pair_lemma)
        )
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
        metadata_rows.append(
            {"key": "pair", "label": "пара", "text": pair_lemma, "href": pair_href}
        )

    if is_biaspectual:
        tense_sections = [
            {
                "title": "Настоящее",
                "rows": _tense_rows("present", forms.get("present", {}) or {}),
            },
            {
                "title": "Будущее",
                "rows": _tense_rows("future", forms.get("future", {}) or {}),
            },
        ]
    elif is_perfective:
        tense_sections = [
            {
                "title": "Будущее",
                "rows": _tense_rows("future", forms.get("future", {}) or {}),
            }
        ]
    else:
        tense_sections = [
            {
                "title": "Настоящее",
                "rows": _tense_rows("present", forms.get("present", {}) or {}),
            }
        ]

    sections = [
        {"title": "Основное", "rows": metadata_rows},
        *tense_sections,
        {
            "title": "Прошедшее",
            "rows": [
                {"key": "past_m", "label": "он", "text": past.get("m", "")},
                {"key": "past_f", "label": "она", "text": past.get("f", "")},
                {"key": "past_n", "label": "оно", "text": past.get("n", "")},
                {"key": "past_pl", "label": "они", "text": past.get("pl", "")},
            ],
        },
        {
            "title": "Повелительное",
            "rows": [
                {"key": "imp_sg", "label": "ты", "text": imperative.get("sg", "")},
                {"key": "imp_pl", "label": "вы", "text": imperative.get("pl", "")},
            ],
        },
    ]

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
