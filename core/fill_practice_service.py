"""Data for the "fill the form" practice page (/practice/fill).

Pure functions over cached verb entries: pick examples that carry a validated
`target` (core/example_targets.py), cut each sentence around the target word,
and label the blank with tense + person (the lemma travels separately) so the learner knows exactly
which form to type. No Firestore writes.
"""

from __future__ import annotations

import json
import random
from functools import lru_cache
from typing import Any

from core.audio_service import build_hashed_audio_key
from core.entitlements import can_study, has_plus_entitlement
from core.i18n import get_strings
from core.languages.config import ALL_STUDY_LANGUAGES
from core.models import Example, VerbEntry
from core.settings import Settings, load_settings
from core.verb_loader import load_entries_for_language, load_entry_by_id

SESSION_SIZE = 8
VERB_SCOPED_MAX_ITEMS = 12
AUDIO_VOICE = "female"
STRINGS_PREFIX = "fill."

_PERSONS_6 = ("1sg", "2sg", "3sg", "1pl", "2pl", "3pl")
_HE_PERSONS = ("1sg", "2msg", "2fsg", "3msg", "3fsg", "1pl", "2mpl", "2fpl", "3pl")

# Shape of `forms` per language: tense -> person keys, or None for a flat string cell. Only used to
# build a placeholder verb whose board tells us which row (section title + row label) each
# (tense, person) path appears under, so labels follow the real board instead of a second table.
_FORM_SHAPES: dict[str, dict[str, tuple[str, ...] | None]] = {
    "en": {"base": None, "present_3sg": None, "gerund": None, "past": None, "past_participle": None},
    "es": {
        **{
            tense: ("yo", "tu", "el", "nos", "vosotros", "ellos")
            for tense in (
                "present",
                "preterite",
                "imperfect",
                "future",
                "conditional",
                "subjunctive_present",
                "subjunctive_imperfect",
            )
        },
        "imperative": ("tu", "vosotros", "usted", "ustedes"),
        "gerund": None,
        "participle": None,
    },
    "fr": {
        **{
            tense: ("je", "tu", "il", "nous", "vous", "ils")
            for tense in (
                "present",
                "passe_compose",
                "imparfait",
                "futur",
                "conditionnel_present",
                "subjonctif_present",
            )
        },
        "imperatif": ("tu", "nous", "vous"),
        "gerondif": None,
        "participe_passe": None,
    },
    "it": {
        **{
            tense: ("io", "tu", "lui", "noi", "voi", "loro")
            for tense in (
                "presente",
                "passato_prossimo",
                "imperfetto",
                "futuro",
                "condizionale_presente",
                "congiuntivo_presente",
                "congiuntivo_imperfetto",
            )
        },
        "imperativo": ("tu", "lei", "noi", "voi"),
        "gerundio": None,
        "participio": None,
    },
    "ru": {
        "present": _PERSONS_6,
        "future": _PERSONS_6,
        "past": ("m", "f", "n", "pl"),
        "imperative": ("sg", "pl"),
    },
    "tr": {
        **{
            tense: ("ben", "sen", "o", "biz", "siz", "onlar")
            for tense in ("present_continuous", "aorist", "past", "future")
        },
        "imperative": ("sen", "siz"),
    },
    "he": {
        "present": ("m_sg", "f_sg", "m_pl", "f_pl"),
        "past": _HE_PERSONS,
        "future": _HE_PERSONS,
        "imperative": ("ms", "fs", "mp"),
    },
}


def _humanize(key: str) -> str:
    return key.replace("_", " ").strip()


@lru_cache(maxsize=None)
def _board_labels(language: str) -> dict[str, tuple[str, str]]:
    """Map "tense" / "tense.person" -> (section title i18n key, row label) from the language's own board."""
    from core.registry import get as get_plugin

    shape = _FORM_SHAPES.get(language)
    if not shape:
        return {}
    forms: dict[str, Any] = {}
    for tense, persons in shape.items():
        forms[tense] = tense if persons is None else {person: f"{tense}.{person}" for person in persons}
    morph = {"aspect": "biaspectual"} if language == "ru" else {}
    placeholder = VerbEntry(
        id=f"{language}_placeholder", rank=0, lemma="placeholder", forms=forms, examples=[], morph=morph
    )
    board = get_plugin(language).build_board(placeholder, AUDIO_VOICE, "")
    labels: dict[str, tuple[str, str]] = {}
    for section in board.sections:
        title = section.get("title")
        if not title:
            continue
        for row in section["rows"]:  # type: ignore[attr-defined]
            text = str(row.get("text") or "")
            if text and text not in labels:
                labels[text] = (str(title), str(row.get("label") or ""))
    return labels


def _cell_label(language: str, path: str, strings: dict[str, str], fallback_strings: dict[str, str]) -> str:
    """ "Tense · person" for a "tense.person" path, localized; readable fallback, never raw underscores."""
    hit = _board_labels(language).get(path)
    if hit is not None:
        title_key, row_label = hit
        title = (
            strings.get(title_key) or fallback_strings.get(title_key) or _humanize(title_key.rsplit("tense_", 1)[-1])
        )
        return f"{title} · {row_label}" if row_label else title
    tense, _, person = path.partition(".")
    return " · ".join(part for part in (_humanize(tense), _humanize(person)) if part)


def _verb_lemma(entry: VerbEntry) -> str:
    lemma: Any = entry.display_lemma or entry.lemma
    if isinstance(lemma, dict):
        lemma = lemma.get("imperfective") or lemma.get("perfective") or ""
    return str(lemma)


def usable_target(example: Example) -> dict[str, Any] | None:
    """The example's target if it can be cut out of the sentence, else None."""
    target = example.target
    sentence = example.dst
    if not isinstance(target, dict) or not sentence:
        return None
    start, end = target.get("start"), target.get("end")
    if not (isinstance(start, int) and isinstance(end, int)) or isinstance(start, bool) or isinstance(end, bool):
        return None
    if not 0 <= start < end <= len(sentence):
        return None
    answer = sentence[start:end]
    if not answer.strip() or not target.get("tense"):
        return None
    return target


def verb_has_fill_items(entry: VerbEntry) -> bool:
    return any(usable_target(example) is not None for example in entry.examples or [])


def target_label(
    language: str, target: dict[str, Any], strings: dict[str, str], fallback_strings: dict[str, str]
) -> str:
    """Localized tense + person label(s) of a target, shared labels joined with " / "."""
    person = target.get("person")
    paths = [f"{target['tense']}.{person}" if person else str(target["tense"])]
    paths += [str(p) for p in target.get("also") or [] if isinstance(p, str) and p]
    return " / ".join(_cell_label(language, path, strings, fallback_strings) for path in paths)


def target_alternatives(target: dict[str, Any], answer: str) -> list[str]:
    alternatives: list[str] = []
    for alt in target.get("alternatives") or []:
        if isinstance(alt, str) and alt.strip() and alt != answer and alt not in alternatives:
            alternatives.append(alt)
    return alternatives


def _build_item(
    entry: VerbEntry,
    index: int,
    example: Example,
    target: dict[str, Any],
    *,
    language: str,
    ui_language: str,
    strings: dict[str, str],
    fallback_strings: dict[str, str],
) -> dict[str, Any]:
    sentence = example.dst
    start, end = target["start"], target["end"]
    answer = sentence[start:end]

    label = target_label(language, target, strings, fallback_strings)
    lemma = _verb_lemma(entry)
    alternatives = target_alternatives(target, answer)

    translation = ""
    if ui_language != language:
        translation = example.translations.get(ui_language, "") or ""

    audio_key = build_hashed_audio_key(f"example_{index}", sentence)
    return {
        "id": f"{entry.id}:{index}",
        "verbId": entry.id,
        "lemma": lemma,
        "label": label,
        "prefix": sentence[:start],
        "answer": answer,
        "suffix": sentence[end:],
        "alternatives": alternatives,
        "translation": translation,
        "audioSrc": f"/audio/{language}/{entry.id}/{AUDIO_VOICE}/{audio_key}.mp3",
    }


def _usable_items_for_verb(
    entry: VerbEntry, *, language: str, ui_language: str, strings: dict[str, str], fallback_strings: dict[str, str]
) -> list[dict[str, Any]]:
    items = []
    for index, example in enumerate(entry.examples or [], start=1):
        target = usable_target(example)
        if target is None:
            continue
        items.append(
            _build_item(
                entry,
                index,
                example,
                target,
                language=language,
                ui_language=ui_language,
                strings=strings,
                fallback_strings=fallback_strings,
            )
        )
    return items


def _fill_strings(ui_language: str) -> dict[str, str]:
    merged = {k: v for k, v in get_strings("en").items() if k.startswith(STRINGS_PREFIX)}
    if ui_language != "en":
        merged.update({k: v for k, v in get_strings(ui_language).items() if k.startswith(STRINGS_PREFIX)})
    return merged


def build_fill_page_data(
    language: str,
    ui_language: str,
    verb_id: str | None = None,
    *,
    max_items: int = 120,
    max_per_verb: int = 2,
    seed: int | None = None,
) -> dict[str, Any]:
    rng = random.Random(seed)
    strings = get_strings(ui_language)
    fallback_strings = get_strings("en")

    def usable(entry: VerbEntry) -> list[dict[str, Any]]:
        return _usable_items_for_verb(
            entry, language=language, ui_language=ui_language, strings=strings, fallback_strings=fallback_strings
        )

    items: list[dict[str, Any]] = []
    if verb_id:
        entry = next((e for e in load_entries_for_language(language=language) if e.id == verb_id), None)
        if entry is None:
            entry = load_entry_by_id(language=language, verb_id=verb_id)
        if entry is not None:
            items = usable(entry)
            rng.shuffle(items)
            items = items[:VERB_SCOPED_MAX_ITEMS]
    else:
        entries = sorted(load_entries_for_language(language=language), key=lambda e: e.id)
        rng.shuffle(entries)
        for entry in entries:
            if len(items) >= max_items:
                break
            verb_items = usable(entry)
            if not verb_items:
                continue
            rng.shuffle(verb_items)
            items.extend(verb_items[:max_per_verb])
        items = items[:max_items]
        rng.shuffle(items)

    return {
        "language": language,
        "uiLanguage": ui_language,
        "verbId": verb_id or None,
        "studyDir": "rtl" if language == "he" else "ltr",
        "items": items,
        "strings": _fill_strings(ui_language),
        "limits": {"sessionSize": SESSION_SIZE},
    }


def page_data_to_json(data: dict[str, Any]) -> str:
    """JSON safe inside <script type="application/json">: no raw <, >, & or JS line separators."""
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
        .replace(" ", "\\u2028")
        .replace(" ", "\\u2029")
    )


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

ACCESS_OK = "ok"
ACCESS_NOT_FOUND = "not_found"
ACCESS_PLUS_LANGUAGE = "plus_language"  # Plus-only study language, user not entitled
ACCESS_PLUS_FEATURE = "plus_feature"  # fill practice itself is switched to Plus-only


def fill_practice_available(language: str, settings: Settings | None = None) -> bool:
    """Switch on and language in the allow-list (independent of who is asking)."""
    settings = settings or load_settings()
    return (
        settings.fill_practice_enabled
        and language in settings.fill_practice_languages
        and language in ALL_STUDY_LANGUAGES
    )


def fill_inline_available(language: str, settings: Settings | None = None) -> bool:
    """In-place fill mode on /learn: practice switch on, and the language in FILL_INLINE_LANGUAGES."""
    settings = settings or load_settings()
    return (
        settings.fill_practice_enabled
        and language in settings.fill_inline_languages
        and language in ALL_STUDY_LANGUAGES
    )


def user_has_fill_access(uid: str | None, settings: Settings | None = None) -> bool:
    """False only when fill practice is Plus-only and this user has no active entitlement."""
    settings = settings or load_settings()
    if not settings.fill_practice_plus_only:
        return True
    return uid is not None and has_plus_entitlement(uid)


def check_fill_access(language: str, uid: str | None, settings: Settings | None = None) -> str:
    settings = settings or load_settings()
    if not fill_practice_available(language, settings):
        return ACCESS_NOT_FOUND
    if not can_study(language, uid, settings):
        return ACCESS_PLUS_LANGUAGE
    if not user_has_fill_access(uid, settings):
        return ACCESS_PLUS_FEATURE
    return ACCESS_OK
