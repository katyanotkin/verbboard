from __future__ import annotations

from core.models import Board, VerbEntry
from core.registry import LanguagePlugin, register
from core.storage.verb_repository import find_verb_by_lemma
from core.verb_service import generate_and_promote_verb


def _format_aspect(aspect_value: str) -> str:
    if aspect_value == "imperfective":
        return "несовершенный"
    if aspect_value == "perfective":
        return "совершенный"
    return aspect_value


def _lookup_pair_lemma_and_href(pair_lemma: str) -> tuple[str, str]:
    normalized_pair_lemma = pair_lemma.strip()
    if not normalized_pair_lemma:
        return "", ""

    doc = find_verb_by_lemma("ru", normalized_pair_lemma)
    if doc is not None:
        return normalized_pair_lemma, f"/learn?language=ru&verb_id={doc['verb_id']}"

    try:
        import asyncio

        asyncio.get_running_loop().run_in_executor(
            None, lambda: generate_and_promote_verb("ru", normalized_pair_lemma)
        )
    except RuntimeError:
        generate_and_promote_verb("ru", normalized_pair_lemma)

    return f"{normalized_pair_lemma} ⏳", ""


def build_board(verb: VerbEntry, voice_key: str, voice_label: str) -> Board:
    lemma = str(verb.lemma)
    forms = verb.forms or {}
    morph = verb.morph or {}

    raw_aspect = str(morph.get("aspect", ""))
    aspect = _format_aspect(raw_aspect)
    is_perfective = raw_aspect == "perfective"

    pair_value = morph.get("pair")
    pair_lemma_raw = pair_value.strip() if isinstance(pair_value, str) else ""
    pair_lemma, pair_href = _lookup_pair_lemma_and_href(pair_lemma_raw)

    tense_key = "future" if is_perfective else "present"
    tense_title = "Будущее" if is_perfective else "Настоящее"

    finite_forms = forms.get(tense_key, {}) or {}
    past = forms.get("past", {}) or {}
    imperative = forms.get("imperative", {}) or {}

    metadata_rows = [
        {"key": "lemma", "label": "глагол", "text": lemma},
    ]
    if aspect:
        metadata_rows.append({"key": "aspect", "label": "вид", "text": aspect})
    if pair_lemma:
        metadata_rows.append(
            {
                "key": "pair",
                "label": "пара",
                "text": pair_lemma,
                "href": pair_href,
            }
        )

    finite_rows = [
        {"key": f"{tense_key}_1sg", "label": "я", "text": finite_forms.get("1sg", "")},
        {"key": f"{tense_key}_2sg", "label": "ты", "text": finite_forms.get("2sg", "")},
        {
            "key": f"{tense_key}_3sg",
            "label": "он/она/оно",
            "text": finite_forms.get("3sg", ""),
        },
        {"key": f"{tense_key}_1pl", "label": "мы", "text": finite_forms.get("1pl", "")},
        {"key": f"{tense_key}_2pl", "label": "вы", "text": finite_forms.get("2pl", "")},
        {
            "key": f"{tense_key}_3pl",
            "label": "они",
            "text": finite_forms.get("3pl", ""),
        },
    ]

    sections = [
        {"title": "Основное", "rows": metadata_rows},
        {"title": tense_title, "rows": finite_rows},
        {
            "title": "Прошедшее",
            "rows": [
                {"key": "past_m", "label": "он", "text": past.get("m", "")},
                {"key": "past_f", "label": "она", "text": past.get("f", "")},
                {"key": "past_n", "label": "оно", "text": past.get("n", "")},
                {"key": "past_pl", "label": "они", "text": past.get("pl", "")},
            ],
        },
        {
            "title": "Повелительное",
            "rows": [
                {"key": "imp_sg", "label": "ты", "text": imperative.get("sg", "")},
                {"key": "imp_pl", "label": "вы", "text": imperative.get("pl", "")},
            ],
        },
    ]

    return Board(
        language="ru",
        verb=verb,
        voice_key=voice_key,
        voice_label=voice_label,
        sections=sections,
    )


register(
    LanguagePlugin(
        language="ru",
        display_name="Russian",
        build_board=build_board,
    )
)
