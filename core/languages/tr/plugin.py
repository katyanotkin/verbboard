from __future__ import annotations

from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register

# Turkish person endings are suffixes on one word (geliyorum), so the pronoun is
# only a row label here; the stored forms never include it.
_PERSONS = [
    ("ben", "ben", "sg"),
    ("sen", "sen", "sg"),
    ("o", "o", "sg"),
    ("biz", "biz", "pl"),
    ("siz", "siz", "pl"),
    ("onlar", "onlar", "pl"),
]


def _tense_rows(prefix: str, tense: dict) -> list:
    return [
        {"key": f"{prefix}_{slot}", "label": label, "text": tense.get(slot, ""), "number": number}
        for slot, label, number in _PERSONS
    ]


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}

    present_continuous = forms.get("present_continuous", {}) or {}
    aorist = forms.get("aorist", {}) or {}
    past = forms.get("past", {}) or {}
    future = forms.get("future", {}) or {}
    imperative = forms.get("imperative", {}) or {}

    sections: list[dict[str, object]] = [
        {"rows": [{"key": "lemma", "label": "mastar", "text": lemma}]},
        {"title": "board.tense_present", "rows": _tense_rows("pres", present_continuous)},
    ]

    if aorist:
        sections.append({"title": "board.tense_aorist", "rows": _tense_rows("aor", aorist)})

    sections.append({"title": "board.tense_past", "rows": _tense_rows("past", past)})

    if future:
        sections.append({"title": "board.tense_future", "rows": _tense_rows("fut", future)})

    imperative_rows = [
        {"key": f"imper_{slot}", "label": slot, "text": imperative.get(slot, ""), "number": number}
        for slot, number in (("sen", "sg"), ("siz", "pl"))
        if imperative.get(slot)
    ]
    if imperative_rows:
        sections.append({"title": "board.tense_imperative", "rows": imperative_rows})

    return Board(
        language="tr",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="tr",
        display_name="Turkish",
        build_board=build_board,
    )
)
