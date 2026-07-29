from __future__ import annotations

from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def _tense_rows(prefix: str, tense: dict) -> list:
    return [
        {"key": f"{prefix}_io", "label": "io", "text": tense.get("io", ""), "number": "sg"},
        {"key": f"{prefix}_tu", "label": "tu", "text": tense.get("tu", ""), "number": "sg"},
        {"key": f"{prefix}_lui", "label": "lui/lei", "text": tense.get("lui", ""), "number": "sg"},
        {"key": f"{prefix}_noi", "label": "noi", "text": tense.get("noi", ""), "number": "pl"},
        {"key": f"{prefix}_voi", "label": "voi", "text": tense.get("voi", ""), "number": "pl"},
        {"key": f"{prefix}_loro", "label": "loro", "text": tense.get("loro", ""), "number": "pl"},
    ]


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}

    presente = forms.get("presente", {}) or {}
    passato_prossimo = forms.get("passato_prossimo", {}) or {}
    imperfetto = forms.get("imperfetto", {}) or {}
    futuro = forms.get("futuro", {}) or {}
    imperativo = forms.get("imperativo", {}) or {}

    sections: list[dict[str, object]] = [
        {
            "rows": [
                {"key": "lemma", "label": "infinito", "text": lemma},
            ],
        },
        {"title": "board.tense_present", "rows": _tense_rows("pres", presente)},
        {"title": "board.tense_perfect", "rows": _tense_rows("pp", passato_prossimo)},
    ]

    if imperfetto:
        sections.append({"title": "board.tense_imperfect", "rows": _tense_rows("imp", imperfetto)})

    if futuro:
        sections.append({"title": "board.tense_future", "rows": _tense_rows("fut", futuro)})

    if imperativo:
        imp_slots = [
            ("tu", "tu", "sg"),
            ("lei", "Lei", "sg"),
            ("noi", "noi", "pl"),
            ("voi", "voi", "pl"),
        ]
        imperative_rows = [
            {"key": f"imper_{slot}", "label": label, "text": imperativo.get(slot, ""), "number": number}
            for slot, label, number in imp_slots
            if imperativo.get(slot)
        ]
        if imperative_rows:
            sections.append({"title": "board.tense_imperative", "rows": imperative_rows})

    sections.append(
        {
            "title": "board.tense_others",
            "rows": [
                {"key": "gerund", "label": "gerundio", "text": forms.get("gerundio", "")},
                {
                    "key": "participle",
                    "label": "participio",
                    "text": forms.get("participio", ""),
                },
            ],
        }
    )

    return Board(
        language="it",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="it",
        display_name="Italian",
        build_board=build_board,
    )
)
