from __future__ import annotations

from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}
    morph = verb.morph or {}

    aspect = str(morph.get("aspect", ""))
    pair = str(morph.get("pair", ""))

    # Runtime RU schema from generate_lexicon.py
    present = forms.get("present", {})
    past = forms.get("past", {})
    imp = forms.get("imperative", {})

    sections = [
        {
            "title": "Metadata",
            "rows": [
                {"key": "lemma", "label": "verb", "text": lemma},
                {"key": "aspect", "label": "aspect", "text": aspect},
                {"key": "pair", "label": "pair", "text": pair},
            ],
        },
        {
            "title": "Present",
            "rows": [
                {"key": "pres_1sg", "label": "я", "text": present.get("1sg", "")},
                {"key": "pres_2sg", "label": "ты", "text": present.get("2sg", "")},
                {"key": "pres_3sg", "label": "он/она", "text": present.get("3sg", "")},
                {"key": "pres_1pl", "label": "мы", "text": present.get("1pl", "")},
                {"key": "pres_2pl", "label": "вы", "text": present.get("2pl", "")},
                {"key": "pres_3pl", "label": "они", "text": present.get("3pl", "")},
            ],
        },
        {
            "title": "Past",
            "rows": [
                {"key": "past_m", "label": "m", "text": past.get("m", "")},
                {"key": "past_f", "label": "f", "text": past.get("f", "")},
                {"key": "past_n", "label": "n", "text": past.get("n", "")},
                {"key": "past_pl", "label": "pl", "text": past.get("pl", "")},
            ],
        },
        {
            "title": "Imperative",
            "rows": [
                {"key": "imp_sg", "label": "sg", "text": imp.get("sg", "")},
                {"key": "imp_pl", "label": "pl", "text": imp.get("pl", "")},
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
        display_name="Russian",
        build_board=build_board,
    )
)
