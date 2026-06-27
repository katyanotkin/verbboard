from __future__ import annotations

from core.languages.config import LANGUAGE
from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def _tense_rows(prefix: str, tense: dict) -> list:
    rows = [
        {"key": f"{prefix}_yo", "label": "yo", "text": tense.get("yo", ""), "number": "sg"},
        {"key": f"{prefix}_tu", "label": "tú", "text": tense.get("tu", ""), "number": "sg"},
        {"key": f"{prefix}_el", "label": "él/ella/Ud.", "text": tense.get("el", ""), "number": "sg"},
        {"key": f"{prefix}_nos", "label": "nosotros", "text": tense.get("nos", ""), "number": "pl"},
    ]
    if tense.get("vosotros"):
        rows.append({"key": f"{prefix}_vos", "label": "vosotros", "text": tense["vosotros"], "number": "pl"})
    rows.append({"key": f"{prefix}_ellos", "label": "ellos/Uds.", "text": tense.get("ellos", ""), "number": "pl"})
    return rows


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}

    present = forms.get("present", {}) or {}
    preterite = forms.get("preterite", {}) or {}
    imperfect = forms.get("imperfect", {}) or {}
    future = forms.get("future", {}) or {}
    imperative = forms.get("imperative", {}) or {}

    sections: list[dict[str, object]] = [
        {
            "rows": [
                {"key": "lemma", "label": "infinitivo", "text": lemma},
            ],
        },
        {"title": "board.tense_present", "rows": _tense_rows("pres", present)},
        {"title": "board.tense_preterite", "rows": _tense_rows("pret", preterite)},
    ]

    if imperfect:
        sections.append({"title": "board.tense_imperfect", "rows": _tense_rows("imp", imperfect)})

    if future:
        sections.append({"title": "board.tense_future", "rows": _tense_rows("fut", future)})

    if imperative:
        imp_slots = [
            ("tu", "tú", "sg"),
            ("vosotros", "vosotros", "pl"),
            ("usted", "usted", "sg"),
            ("ustedes", "ustedes", "pl"),
        ]
        imperative_rows = [
            {"key": f"imper_{slot}", "label": label, "text": imperative.get(slot, ""), "number": number}
            for slot, label, number in imp_slots
            if imperative.get(slot)
        ]
        if imperative_rows:
            sections.append({"title": "board.tense_imperative", "rows": imperative_rows})

    sections.append(
        {
            "title": "board.tense_others",
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
