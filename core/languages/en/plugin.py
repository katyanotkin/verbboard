from __future__ import annotations

from typing import Any

from core.languages.config import LANGUAGE
from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def render_form_value(value: Any) -> str:
    if isinstance(value, list):
        return " / ".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    forms = verb.forms

    sections: list[dict[str, object]] = [
        {
            "rows": [
                {
                    "key": "base",
                    "label": "infinitive",
                    "text": render_form_value(forms.get("base", "")),
                },
            ],
        },
        {
            "title": "board.tense_present",
            "rows": [
                {
                    "key": "present_1sg",
                    "label": "I / you / we / they",
                    "text": render_form_value(forms.get("base", "")),
                },
                {
                    "key": "present_3sg",
                    "label": "he / she / it",
                    "text": render_form_value(forms.get("present_3sg", "")),
                },
                {
                    "key": "gerund",
                    "label": "gerund (-ing)",
                    "text": render_form_value(forms.get("gerund", "")),
                },
            ],
        },
        {
            "title": "board.tense_past",
            "rows": [
                {
                    "key": "past",
                    "label": "past simple",
                    "text": render_form_value(forms.get("past", "")),
                },
                {
                    "key": "past_participle",
                    "label": "past participle",
                    "text": render_form_value(forms["past_participle"]),
                },
            ],
        },
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
        display_name=LANGUAGE["en"].display,
        build_board=build_board,
    )
)
