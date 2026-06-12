from __future__ import annotations

from core.languages.config import LANGUAGE
from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    display_forms = getattr(verb, "display_forms", None) or {}
    forms = display_forms or verb.forms
    morph = verb.morph or {}

    present = forms.get("present", {}) or {}
    past = forms.get("past", {}) or {}
    future = forms.get("future", {}) or {}

    infinitive = str(verb.display_lemma or verb.lemma or "")

    sections: list[dict[str, object]] = [
        {
            "rows": [
                {
                    "key": "infinitive",
                    "label": "שם פועל",
                    "text": infinitive,
                },
                {
                    "key": "binyan",
                    "label": "בניין",
                    "text": str(morph.get("binyan", "")),
                },
                {"key": "root", "label": "שורש", "text": str(morph.get("root", ""))},
            ],
        },
        {
            "title": "board.tense_present",
            "rows": [
                {"key": "pres_m_sg", "label": "הוא", "text": present.get("m_sg", ""), "gender": "m", "number": "sg"},
                {"key": "pres_f_sg", "label": "היא", "text": present.get("f_sg", ""), "gender": "f", "number": "sg"},
                {"key": "pres_m_pl", "label": "הם", "text": present.get("m_pl", ""), "gender": "m", "number": "pl"},
                {"key": "pres_f_pl", "label": "הן", "text": present.get("f_pl", ""), "gender": "f", "number": "pl"},
            ],
        },
        {
            "title": "board.tense_past",
            "rows": [
                {"key": "past_1sg", "label": "אני", "text": past.get("1sg", ""), "number": "sg"},
                {"key": "past_2msg", "label": "אתה", "text": past.get("2msg", ""), "gender": "m", "number": "sg"},
                {"key": "past_2fsg", "label": "את", "text": past.get("2fsg", ""), "gender": "f", "number": "sg"},
                {"key": "past_3msg", "label": "הוא", "text": past.get("3msg", ""), "gender": "m", "number": "sg"},
                {"key": "past_3fsg", "label": "היא", "text": past.get("3fsg", ""), "gender": "f", "number": "sg"},
                {"key": "past_1pl", "label": "אנחנו", "text": past.get("1pl", ""), "number": "pl"},
                {"key": "past_2mpl", "label": "אתם", "text": past.get("2mpl", ""), "gender": "m", "number": "pl"},
                {"key": "past_2fpl", "label": "אתן", "text": past.get("2fpl", ""), "gender": "f", "number": "pl"},
                {"key": "past_3pl", "label": "הם / הן", "text": past.get("3pl", ""), "number": "pl"},
            ],
        },
        {
            "title": "board.tense_future",
            "rows": [
                {"key": "fut_1sg", "label": "אני", "text": future.get("1sg", ""), "number": "sg"},
                {"key": "fut_2msg", "label": "אתה", "text": future.get("2msg", ""), "gender": "m", "number": "sg"},
                {"key": "fut_2fsg", "label": "את", "text": future.get("2fsg", ""), "gender": "f", "number": "sg"},
                {"key": "fut_3msg", "label": "הוא", "text": future.get("3msg", ""), "gender": "m", "number": "sg"},
                {"key": "fut_3fsg", "label": "היא", "text": future.get("3fsg", ""), "gender": "f", "number": "sg"},
                {"key": "fut_1pl", "label": "אנחנו", "text": future.get("1pl", ""), "number": "pl"},
                {"key": "fut_2mpl", "label": "אתם", "text": future.get("2mpl", ""), "gender": "m", "number": "pl"},
                {"key": "fut_2fpl", "label": "אתן", "text": future.get("2fpl", ""), "gender": "f", "number": "pl"},
                {"key": "fut_3pl", "label": "הם / הן", "text": future.get("3pl", ""), "number": "pl"},
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
        display_name=LANGUAGE["he"].display,
        build_board=build_board,
    )
)
