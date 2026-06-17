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

    tts = getattr(verb, "tts_forms", None) or {}
    tts_present = tts.get("present", {}) or {}
    tts_past = tts.get("past", {}) or {}
    tts_future = tts.get("future", {}) or {}

    def _row(key: str, label: str, text: str, tts_src: dict, tts_key: str, **extra) -> dict:
        r: dict = {"key": key, "label": label, "text": text, **extra}
        tts_text = (tts_src.get(tts_key) or "").strip()
        if tts_text and tts_text != text:
            r["tts_text"] = tts_text
        return r

    infinitive = str(verb.display_lemma or verb.lemma or "")

    sections: list[dict[str, object]] = [
        {
            "rows": [
                {"key": "infinitive", "label": "שם פועל", "text": infinitive},
                {"key": "binyan", "label": "בניין", "text": str(morph.get("binyan", ""))},
                {"key": "root", "label": "שורש", "text": str(morph.get("root", ""))},
            ],
        },
        {
            "title": "board.tense_present",
            "rows": [
                _row("pres_m_sg", "הוא", present.get("m_sg", ""), tts_present, "m_sg", gender="m", number="sg"),
                _row("pres_f_sg", "היא", present.get("f_sg", ""), tts_present, "f_sg", gender="f", number="sg"),
                _row("pres_m_pl", "הם", present.get("m_pl", ""), tts_present, "m_pl", gender="m", number="pl"),
                _row("pres_f_pl", "הן", present.get("f_pl", ""), tts_present, "f_pl", gender="f", number="pl"),
            ],
        },
        {
            "title": "board.tense_past",
            "rows": [
                _row("past_1sg", "אני", past.get("1sg", ""), tts_past, "1sg", number="sg"),
                _row("past_2msg", "אתה", past.get("2msg", ""), tts_past, "2msg", gender="m", number="sg"),
                _row("past_2fsg", "את", past.get("2fsg", ""), tts_past, "2fsg", gender="f", number="sg"),
                _row("past_3msg", "הוא", past.get("3msg", ""), tts_past, "3msg", gender="m", number="sg"),
                _row("past_3fsg", "היא", past.get("3fsg", ""), tts_past, "3fsg", gender="f", number="sg"),
                _row("past_1pl", "אנחנו", past.get("1pl", ""), tts_past, "1pl", number="pl"),
                _row("past_2mpl", "אתם", past.get("2mpl", ""), tts_past, "2mpl", gender="m", number="pl"),
                _row("past_2fpl", "אתן", past.get("2fpl", ""), tts_past, "2fpl", gender="f", number="pl"),
                _row("past_3pl", "הם / הן", past.get("3pl", ""), tts_past, "3pl", number="pl"),
            ],
        },
        {
            "title": "board.tense_future",
            "rows": [
                _row("fut_1sg", "אני", future.get("1sg", ""), tts_future, "1sg", number="sg"),
                _row("fut_2msg", "אתה", future.get("2msg", ""), tts_future, "2msg", gender="m", number="sg"),
                _row("fut_2fsg", "את", future.get("2fsg", ""), tts_future, "2fsg", gender="f", number="sg"),
                _row("fut_3msg", "הוא", future.get("3msg", ""), tts_future, "3msg", gender="m", number="sg"),
                _row("fut_3fsg", "היא", future.get("3fsg", ""), tts_future, "3fsg", gender="f", number="sg"),
                _row("fut_1pl", "אנחנו", future.get("1pl", ""), tts_future, "1pl", number="pl"),
                _row("fut_2mpl", "אתם", future.get("2mpl", ""), tts_future, "2mpl", gender="m", number="pl"),
                _row("fut_2fpl", "אתן", future.get("2fpl", ""), tts_future, "2fpl", gender="f", number="pl"),
                _row("fut_3pl", "הם / הן", future.get("3pl", ""), tts_future, "3pl", number="pl"),
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
