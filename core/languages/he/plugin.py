from __future__ import annotations

from core.models import Board, VerbEntry


BINYAN_HE = {
    "paal": "פעל",
    "piel": "פיעל",
    "hitpael": "התפעל",
}

def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    forms = verb.forms
    morph = verb.morph or {}
    present = forms.get("present", {})
    past = forms.get("past", {})
    future = forms.get("future", {})

    sections = [
        {
            "title": "Metadata",
            "rows": [
                {"key": "binyan", "label": "binyan", "text": str(morph.get("binyan", ""))},
                {"key": "root", "label": "root", "text": str(morph.get("root", ""))},
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
                {"key": "past_1sg", "label": "I", "text": past.get("1sg", "")},
                {"key": "past_2msg", "label": "you m.sg", "text": past.get("2msg", "")},
                {"key": "past_2fsg", "label": "you f.sg", "text": past.get("2fsg", "")},
                {"key": "past_3msg", "label": "he", "text": past.get("3msg", "")},
                {"key": "past_3fsg", "label": "she", "text": past.get("3fsg", "")},
                {"key": "past_1pl", "label": "we", "text": past.get("1pl", "")},
                {"key": "past_2mpl", "label": "you m.pl", "text": past.get("2mpl", "")},
                {"key": "past_2fpl", "label": "you f.pl", "text": past.get("2fpl", "")},
                {"key": "past_3pl", "label": "they", "text": past.get("3pl", "")},
            ],
        },
        {
            "title": "Future",
            "rows": [
                {"key": "fut_1sg", "label": "I", "text": future.get("1sg", "")},
                {"key": "fut_2msg", "label": "you m.sg", "text": future.get("2msg", "")},
                {"key": "fut_2fsg", "label": "you f.sg", "text": future.get("2fsg", "")},
                {"key": "fut_3msg", "label": "he", "text": future.get("3msg", "")},
                {"key": "fut_3fsg", "label": "she", "text": future.get("3fsg", "")},
                {"key": "fut_1pl", "label": "we", "text": future.get("1pl", "")},
                {"key": "fut_2pl", "label": "you pl", "text": future.get("2pl", "")},
                {"key": "fut_3pl", "label": "they", "text": future.get("3pl", "")},
            ],
        },
    ]

    return Board(language="he", verb=verb, voice_key=voice_key, voice_label=voice_label, sections=sections)
