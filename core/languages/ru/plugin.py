from __future__ import annotations

from core.models import Board, VerbEntry


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = verb.lemma  # dict: {imperfective, perfective}
    forms = verb.forms

    present = forms.get("imperfective_present", {})
    past = forms.get("imperfective_past", {})
    imp = forms.get("imperative", {})

    sections = [
        {
            "title": "Aspect",
            "rows": [
                {"key": "lemma_imperf", "label": "imperfective", "text": lemma.get("imperfective", "")},
                {"key": "lemma_perf", "label": "perfective", "text": lemma.get("perfective", "")},
            ],
        },
        {
            "title": "Present (imperfective)",
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
            "title": "Past (imperfective)",
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
    return Board(language="ru", verb=verb, voice_key=voice_key, voice_label=voice_label, sections=sections)
