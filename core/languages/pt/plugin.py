from __future__ import annotations

from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register

# Brazilian Portuguese: "tu" and "vós" are not part of the standard paradigm, and
# "você/vocês" take the third-person forms, so four slots cover the whole table.
_PERSONS = [
    ("eu", "eu", "sg"),
    ("ele", "ele/ela/você", "sg"),
    ("nos", "nós", "pl"),
    ("eles", "eles/elas/vocês", "pl"),
]
_SLOTS = tuple(slot for slot, _label, _number in _PERSONS)


def _tense_rows(prefix: str, tense: dict) -> list:
    return [
        {"key": f"{prefix}_{slot}", "label": label, "text": tense.get(slot, ""), "number": number}
        for slot, label, number in _PERSONS
    ]


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}

    present = forms.get("present", {}) or {}
    preterite = forms.get("preterite", {}) or {}
    imperfect = forms.get("imperfect", {}) or {}
    future = forms.get("future", {}) or {}
    conditional = forms.get("conditional", {}) or {}
    subjunctive_present = forms.get("subjunctive_present", {}) or {}
    subjunctive_imperfect = forms.get("subjunctive_imperfect", {}) or {}
    subjunctive_future = forms.get("subjunctive_future", {}) or {}
    imperative = forms.get("imperative", {}) or {}

    sections: list[dict[str, object]] = [
        {"rows": [{"key": "lemma", "label": "infinitivo", "text": lemma}]},
        {"title": "board.tense_present", "rows": _tense_rows("pres", present)},
        {"title": "board.tense_preterite", "rows": _tense_rows("pret", preterite)},
    ]

    optional_tenses = (
        (imperfect, "board.tense_imperfect", "imp"),
        (future, "board.tense_future", "fut"),
        (conditional, "board.tense_conditional", "cond"),
        (subjunctive_present, "board.tense_subjunctive_present", "subjpres"),
        (subjunctive_imperfect, "board.tense_subjunctive_imperfect", "subjimp"),
        (subjunctive_future, "board.tense_subjunctive_future", "subjfut"),
    )
    for tense, title, prefix in optional_tenses:
        if any(tense.get(slot) for slot in _SLOTS):
            sections.append({"title": title, "rows": _tense_rows(prefix, tense)})

    imperative_rows = [
        {"key": f"imper_{slot}", "label": label, "text": imperative.get(slot, ""), "number": number}
        for slot, label, number in (("voce", "você", "sg"), ("nos", "nós", "pl"), ("voces", "vocês", "pl"))
        if imperative.get(slot)
    ]
    if imperative_rows:
        sections.append({"title": "board.tense_imperative", "rows": imperative_rows})

    sections.append(
        {
            "title": "board.tense_others",
            "rows": [
                {"key": "gerund", "label": "gerúndio", "text": forms.get("gerund", "")},
                {"key": "participle", "label": "particípio", "text": forms.get("participle", "")},
            ],
        }
    )

    return Board(
        language="pt",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="pt",
        display_name="Portuguese",
        build_board=build_board,
    )
)
