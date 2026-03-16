from __future__ import annotations

from core.models import Board, VerbEntry

from core.registry import LanguagePlugin, register


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    forms = verb.forms
    sections = [
        {
            "title": "Principal forms",
            "rows": [
                {"key": "base", "label": "base", "text": forms.get("base", "")},
                {"key": "past", "label": "past", "text": forms.get("past", "")},
                {
                    "key": "past_participle",
                    "label": "past participle",
                    "text": forms["past_participle"],
                },
                {
                    "key": "present_3sg",
                    "label": "3rd person sg",
                    "text": forms.get("present_3sg", ""),
                },
                {"key": "gerund", "label": "gerund", "text": forms.get("gerund", "")},
            ],
        }
    ]
    return Board(
        language="en",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="en",
        display_name="English",
        build_board=build_board,
    )
)
