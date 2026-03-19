from __future__ import annotations

from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    display_forms = getattr(verb, "display_forms", None) or {}
    forms = display_forms or verb.forms
    morph = verb.morph or {}

    present = forms.get("present", {}) or {}
    past = forms.get("past", {}) or {}
    future = forms.get("future", {}) or {}

    sections = [
        {
            "title": "Metadata",
            "rows": [
                {
                    "key": "binyan",
                    "label": "בניין",
                    "text": str(morph.get("binyan", "")),
                },
                {"key": "root", "label": "שורש", "text": str(morph.get("root", ""))},
            ],
        },
        {
            "title": "Present",
            "rows": [
                {
                    "key": "pres_m_sg",
                    "label": "he / הוא",
                    "text": present.get("m_sg", ""),
                },
                {
                    "key": "pres_f_sg",
                    "label": "she / היא",
                    "text": present.get("f_sg", ""),
                },
                {
                    "key": "pres_m_pl",
                    "label": "they (m.) / הם",
                    "text": present.get("m_pl", ""),
                },
                {
                    "key": "pres_f_pl",
                    "label": "they (f.) / הן",
                    "text": present.get("f_pl", ""),
                },
            ],
        },
        {
            "title": "Past",
            "rows": [
                {
                    "key": "past_1sg",
                    "label": "I / אני",
                    "text": past.get("1sg", ""),
                },
                {
                    "key": "past_2msg",
                    "label": "you (m.sg.) / אתה",
                    "text": past.get("2msg", ""),
                },
                {
                    "key": "past_2fsg",
                    "label": "you (f.sg.) / את",
                    "text": past.get("2fsg", ""),
                },
                {
                    "key": "past_3msg",
                    "label": "he / הוא",
                    "text": past.get("3msg", ""),
                },
                {
                    "key": "past_3fsg",
                    "label": "she / היא",
                    "text": past.get("3fsg", ""),
                },
                {
                    "key": "past_1pl",
                    "label": "we / אנחנו",
                    "text": past.get("1pl", ""),
                },
                {
                    "key": "past_2mpl",
                    "label": "you (m.pl.) / אתם",
                    "text": past.get("2mpl", ""),
                },
                {
                    "key": "past_2fpl",
                    "label": "you (f.pl.) / אתן",
                    "text": past.get("2fpl", ""),
                },
                {
                    "key": "past_3pl",
                    "label": "they / הם, הן",
                    "text": past.get("3pl", ""),
                },
            ],
        },
        {
            "title": "Future",
            "rows": [
                {
                    "key": "fut_1sg",
                    "label": "I / אני",
                    "text": future.get("1sg", ""),
                },
                {
                    "key": "fut_2msg",
                    "label": "you (m.sg.) / אתה",
                    "text": future.get("2msg", ""),
                },
                {
                    "key": "fut_2fsg",
                    "label": "you (f.sg.) / את",
                    "text": future.get("2fsg", ""),
                },
                {
                    "key": "fut_3msg",
                    "label": "he / הוא",
                    "text": future.get("3msg", ""),
                },
                {
                    "key": "fut_3fsg",
                    "label": "she / היא",
                    "text": future.get("3fsg", ""),
                },
                {
                    "key": "fut_1pl",
                    "label": "we / אנחנו",
                    "text": future.get("1pl", ""),
                },
                {
                    "key": "fut_2mpl",
                    "label": "you (m.pl.) / אתם",
                    "text": future.get("2mpl", ""),
                },
                {
                    "key": "fut_2fpl",
                    "label": "you (f.pl.) / אתן",
                    "text": future.get("2fpl", ""),
                },
                {
                    "key": "fut_3pl",
                    "label": "they / הם, הן",
                    "text": future.get("3pl", ""),
                },
            ],
        },
    ]

    return Board(
        language="he",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="he",
        display_name="Hebrew",
        build_board=build_board,
    )
)
