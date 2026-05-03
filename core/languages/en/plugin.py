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

    present_label = "3rd person sg"
    present_text = render_form_value(forms.get("present_3sg", ""))

    if forms.get("present_1sg") or forms.get("present_other"):
        present_label = "present"
        present_parts = [
            forms.get("present_1sg", ""),
            forms.get("present_3sg", ""),
            forms.get("present_other", ""),
        ]
        present_text = render_form_value([part for part in present_parts if part])

    sections = [
        {
            "title": "Principal forms",
            "rows": [
                {
                    "key": "base",
                    "label": "base",
                    "text": render_form_value(forms.get("base", "")),
                },
                {
                    "key": "past",
                    "label": "past",
                    "text": render_form_value(forms.get("past", "")),
                },
                {
                    "key": "past_participle",
                    "label": "past participle",
                    "text": render_form_value(forms["past_participle"]),
                },
                {
                    "key": "present_3sg",
                    "label": present_label,
                    "text": present_text,
                },
                {
                    "key": "gerund",
                    "label": "gerund",
                    "text": render_form_value(forms.get("gerund", "")),
                },
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
        display_name=LANGUAGE["en"].display,
        build_board=build_board,
    )
)
