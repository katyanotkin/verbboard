from __future__ import annotations

from core.languages.config import LANGUAGE
from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def _tense_rows(prefix: str, tense: dict) -> list:
    return [
        {"key": f"{prefix}_yo", "label": "yo", "text": tense.get("yo", "")},
        {"key": f"{prefix}_tu", "label": "tú", "text": tense.get("tu", "")},
        {"key": f"{prefix}_el", "label": "él/ella", "text": tense.get("el", "")},
        {"key": f"{prefix}_nos", "label": "nosotros", "text": tense.get("nos", "")},
        {"key": f"{prefix}_ellos", "label": "ellos", "text": tense.get("ellos", "")},
    ]


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}

    present = forms.get("present", {}) or {}
    preterite = forms.get("preterite", {}) or {}
    imperfect = forms.get("imperfect", {}) or {}
    future = forms.get("future", {}) or {}
    imperative = forms.get("imperative", {}) or {}

    sections = [
        {
            "title": "Verbo",
            "rows": [
                {"key": "lemma", "label": "infinitivo", "text": lemma},
            ],
        },
        {"title": "Presente", "rows": _tense_rows("pres", present)},
        {"title": "Pretérito", "rows": _tense_rows("pret", preterite)},
    ]

    if imperfect:
        sections.append({"title": "Imperfecto", "rows": _tense_rows("imp", imperfect)})

    if future:
        sections.append({"title": "Futuro", "rows": _tense_rows("fut", future)})

    if imperative:
        imp_slots = [
            ("tu", "tú"),
            ("vosotros", "vosotros"),
            ("usted", "usted"),
            ("ustedes", "ustedes"),
        ]
        imperative_rows = [
            {"key": f"imper_{slot}", "label": label, "text": imperative.get(slot, "")}
            for slot, label in imp_slots
            if imperative.get(slot)
        ]
        if imperative_rows:
            sections.append({"title": "Imperativo", "rows": imperative_rows})

    sections.append(
        {
            "title": "Otros",
            "rows": [
                {"key": "gerund", "label": "gerundio", "text": forms.get("gerund", "")},
                {
                    "key": "participle",
                    "label": "participio",
                    "text": forms.get("participle", ""),
                },
            ],
        }
    )

    return Board(
        language="es",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="es",
        display_name=LANGUAGE["es"].display,
        build_board=build_board,
    )
)
