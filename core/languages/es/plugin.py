from __future__ import annotations

from core.languages.config import LANGUAGE
from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}

    present = forms.get("present", {}) or {}
    preterite = forms.get("preterite", {}) or {}
    imperative = forms.get("imperative", {}) or {}

    sections = [
        {
            "title": "Verbo",
            "rows": [
                {"key": "lemma", "label": "infinitivo", "text": lemma},
            ],
        },
        {
            "title": "Presente",
            "rows": [
                {"key": "pres_yo", "label": "yo", "text": present.get("yo", "")},
                {"key": "pres_tu", "label": "tú", "text": present.get("tu", "")},
                {"key": "pres_el", "label": "él/ella", "text": present.get("el", "")},
                {
                    "key": "pres_nos",
                    "label": "nosotros",
                    "text": present.get("nos", ""),
                },
                {
                    "key": "pres_ellos",
                    "label": "ellos",
                    "text": present.get("ellos", ""),
                },
            ],
        },
        {
            "title": "Pretérito",
            "rows": [
                {"key": "pret_yo", "label": "yo", "text": preterite.get("yo", "")},
                {"key": "pret_tu", "label": "tú", "text": preterite.get("tu", "")},
                {"key": "pret_el", "label": "él/ella", "text": preterite.get("el", "")},
                {
                    "key": "pret_nos",
                    "label": "nosotros",
                    "text": preterite.get("nos", ""),
                },
                {
                    "key": "pret_ellos",
                    "label": "ellos",
                    "text": preterite.get("ellos", ""),
                },
            ],
        },
    ]

    if imperative:
        imperative_rows = []
        if imperative.get("tu"):
            imperative_rows.append(
                {"key": "imp_tu", "label": "tú", "text": imperative.get("tu", "")}
            )
        if imperative.get("vosotros"):
            imperative_rows.append(
                {
                    "key": "imp_vosotros",
                    "label": "vosotros",
                    "text": imperative.get("vosotros", ""),
                }
            )
        if imperative.get("usted"):
            imperative_rows.append(
                {
                    "key": "imp_usted",
                    "label": "usted",
                    "text": imperative.get("usted", ""),
                }
            )
        if imperative.get("ustedes"):
            imperative_rows.append(
                {
                    "key": "imp_ustedes",
                    "label": "ustedes",
                    "text": imperative.get("ustedes", ""),
                }
            )
        if imperative_rows:
            sections.append(
                {
                    "title": "Imperativo",
                    "rows": imperative_rows,
                }
            )

    sections.append(
        {
            "title": "Otros",
            "rows": [
                {"key": "gerund", "label": "gerundio", "text": forms.get("gerund", "")},
                {
                    "key": "participle",
                    "label": "participio",
                    "text": forms.get("participle", ""),
                },
            ],
        }
    )

    return Board(
        language="es",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="es",
        display_name=LANGUAGE["es"].display,
        build_board=build_board,
    )
)
