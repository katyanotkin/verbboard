from __future__ import annotations

from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def _tense_rows(prefix: str, tense: dict) -> list:
    return [
        {"key": f"{prefix}_je", "label": "je", "text": tense.get("je", ""), "number": "sg"},
        {"key": f"{prefix}_tu", "label": "tu", "text": tense.get("tu", ""), "number": "sg"},
        {"key": f"{prefix}_il", "label": "il/elle", "text": tense.get("il", ""), "number": "sg"},
        {"key": f"{prefix}_nous", "label": "nous", "text": tense.get("nous", ""), "number": "pl"},
        {"key": f"{prefix}_vous", "label": "vous", "text": tense.get("vous", ""), "number": "pl"},
        {"key": f"{prefix}_ils", "label": "ils/elles", "text": tense.get("ils", ""), "number": "pl"},
    ]


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}

    present = forms.get("present", {}) or {}
    passe_compose = forms.get("passe_compose", {}) or {}
    imparfait = forms.get("imparfait", {}) or {}
    futur = forms.get("futur", {}) or {}
    imperatif = forms.get("imperatif", {}) or {}

    sections: list[dict[str, object]] = [
        {
            "rows": [
                {"key": "lemma", "label": "infinitif", "text": lemma},
            ],
        },
        {"title": "board.tense_present", "rows": _tense_rows("pres", present)},
        {"title": "board.tense_perfect", "rows": _tense_rows("pc", passe_compose)},
    ]

    if imparfait:
        sections.append({"title": "board.tense_imperfect", "rows": _tense_rows("imp", imparfait)})

    if futur:
        sections.append({"title": "board.tense_future", "rows": _tense_rows("fut", futur)})

    if imperatif:
        imp_slots = [
            ("tu", "tu", "sg"),
            ("nous", "nous", "pl"),
            ("vous", "vous", "pl"),
        ]
        imperative_rows = [
            {"key": f"imper_{slot}", "label": label, "text": imperatif.get(slot, ""), "number": number}
            for slot, label, number in imp_slots
            if imperatif.get(slot)
        ]
        if imperative_rows:
            sections.append({"title": "board.tense_imperative", "rows": imperative_rows})

    sections.append(
        {
            "title": "board.tense_others",
            "rows": [
                {"key": "gerund", "label": "gérondif", "text": forms.get("gerondif", "")},
                {
                    "key": "participle",
                    "label": "participe passé",
                    "text": forms.get("participe_passe", ""),
                },
            ],
        }
    )

    return Board(
        language="fr",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="fr",
        display_name="French",
        build_board=build_board,
    )
)
