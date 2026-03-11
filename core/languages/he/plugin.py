from __future__ import annotations

from core.models import Board, VerbEntry


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    forms = verb.forms
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
                {"key": "pres_m_sg", "label": "m.sg", "text": present.get("m_sg", "")},
                {"key": "pres_f_sg", "label": "f.sg", "text": present.get("f_sg", "")},
                {"key": "pres_m_pl", "label": "m.pl", "text": present.get("m_pl", "")},
                {"key": "pres_f_pl", "label": "f.pl", "text": present.get("f_pl", "")},
            ],
        },
        {
            "title": "Past",
            "rows": [
                # 1st person
                {"key": "past_1sg", "label": "1st sg", "text": past.get("1sg", "")},
                {"key": "past_1pl", "label": "1st pl", "text": past.get("1pl", "")},
                # 2nd person
                {"key": "past_2msg", "label": "2nd m.sg", "text": past.get("2msg", "")},
                {"key": "past_2fsg", "label": "2nd f.sg", "text": past.get("2fsg", "")},
                {"key": "past_2mpl", "label": "2nd m.pl", "text": past.get("2mpl", "")},
                {"key": "past_2fpl", "label": "2nd f.pl", "text": past.get("2fpl", "")},
                # 3rd person
                {"key": "past_3msg", "label": "3rd m.sg", "text": past.get("3msg", "")},
                {"key": "past_3fsg", "label": "3rd f.sg", "text": past.get("3fsg", "")},
                {"key": "past_3pl", "label": "3rd pl", "text": past.get("3pl", "")},
            ],
        },
        {
            "title": "Future",
            "rows": [
                # 1st person
                {"key": "fut_1sg", "label": "1st sg", "text": future.get("1sg", "")},
                {"key": "fut_1pl", "label": "1st pl", "text": future.get("1pl", "")},
                # 2nd person (split plural by gender)
                {
                    "key": "fut_2msg",
                    "label": "2nd m.sg",
                    "text": future.get("2msg", ""),
                },
                {
                    "key": "fut_2fsg",
                    "label": "2nd f.sg",
                    "text": future.get("2fsg", ""),
                },
                {
                    "key": "fut_2mpl",
                    "label": "2nd m.pl",
                    "text": future.get("2mpl", ""),
                },
                {
                    "key": "fut_2fpl",
                    "label": "2nd f.pl",
                    "text": future.get("2fpl", ""),
                },
                # 3rd person
                {
                    "key": "fut_3msg",
                    "label": "3rd m.sg",
                    "text": future.get("3msg", ""),
                },
                {
                    "key": "fut_3fsg",
                    "label": "3rd f.sg",
                    "text": future.get("3fsg", ""),
                },
                {"key": "fut_3pl", "label": "3rd pl", "text": future.get("3pl", "")},
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
