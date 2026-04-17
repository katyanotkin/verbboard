from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any

from core.search_utils import flatten_values, normalize_text


_CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}


_HEBREW_TO_LATIN = {
    "א": "",
    "ב": "b",
    "ג": "g",
    "ד": "d",
    "ה": "h",
    "ו": "v",
    "ז": "z",
    "ח": "kh",
    "ט": "t",
    "י": "y",
    "כ": "k",
    "ך": "k",
    "ל": "l",
    "מ": "m",
    "ם": "m",
    "נ": "n",
    "ן": "n",
    "ס": "s",
    "ע": "",
    "פ": "p",
    "ף": "p",
    "צ": "ts",
    "ץ": "ts",
    "ק": "k",
    "ר": "r",
    "ש": "sh",
    "ת": "t",
}


def _strip_combining_marks(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def _transliterate_for_id(value: str) -> str:
    value = value.strip().lower()
    if not value:
        return ""

    value = _strip_combining_marks(value)

    result: list[str] = []
    for char in value:
        if char in _CYRILLIC_TO_LATIN:
            result.append(_CYRILLIC_TO_LATIN[char])
        elif char in _HEBREW_TO_LATIN:
            result.append(_HEBREW_TO_LATIN[char])
        elif char.isascii():
            result.append(char)
        else:
            result.append(" ")

    transliterated = "".join(result)
    transliterated = transliterated.replace("/", " ")
    transliterated = re.sub(r"[^a-z0-9]+", "_", transliterated)
    transliterated = re.sub(r"_+", "_", transliterated).strip("_")

    return transliterated


def build_verb_doc_id(verb_id: str) -> str:
    parts = verb_id.split("_", 1)
    if len(parts) == 2:
        language, raw_value = parts
        normalized_value = _transliterate_for_id(raw_value)
        if normalized_value:
            return f"{language}_{normalized_value}"
        return language

    normalized_value = _transliterate_for_id(verb_id)
    return normalized_value or "verb"


def build_storage_verb_id(*, language: str, lemma: str) -> str:
    normalized_lemma = _transliterate_for_id(lemma)
    if normalized_lemma:
        return f"{language}_{normalized_lemma}"
    return language


def build_verb_document(
    *,
    language: str,
    verb_id: str,
    lemma: str,
    rank: int | None,
    forms: dict[str, Any],
    examples: list[dict[str, Any]],
    display_lemma: str | None,
    display_forms: dict[str, Any] | None,
    morph: dict[str, Any] | None,
    search_extract: list[str],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()

    return {
        "language": language,
        "verb_id": verb_id,
        "lemma": lemma,
        "rank": rank,
        "forms": forms,
        "examples": examples,
        "display_lemma": display_lemma,
        "display_forms": display_forms,
        "morph": morph,
        "search_extract": search_extract,
        "created_at": now,
        "updated_at": now,
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        normalized = normalize_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(value)

    return result


def build_search_extract_from_entry(
    *,
    language: str,
    entry: dict[str, Any],
) -> list[str]:
    candidates: list[str] = []

    lemma = entry.get("lemma")
    if isinstance(lemma, dict):
        candidates.extend(flatten_values(lemma))
    elif isinstance(lemma, str) and lemma.strip():
        candidates.append(lemma)

    forms = entry.get("forms")
    if forms:
        candidates.extend(flatten_values(forms))

    if language == "he":
        morph = entry.get("morph")
        if isinstance(morph, dict):
            root = morph.get("root")
            if isinstance(root, str) and root.strip():
                candidates.append(root)
    else:
        display_lemma = entry.get("display_lemma")
        if isinstance(display_lemma, dict):
            candidates.extend(flatten_values(display_lemma))
        elif isinstance(display_lemma, str) and display_lemma.strip():
            candidates.append(display_lemma)

    return _dedupe(candidates)


def build_verb_document_from_lexicon_entry(
    *,
    language: str,
    entry: dict[str, Any],
) -> dict[str, Any]:
    verb_id = entry["id"]

    return build_verb_document(
        language=language,
        verb_id=verb_id,
        lemma=entry.get("lemma", verb_id),
        rank=entry.get("rank"),
        forms=entry.get("forms", {}),
        examples=entry.get("examples", []),
        display_lemma=entry.get("display_lemma"),
        display_forms=entry.get("display_forms"),
        morph=entry.get("morph"),
        search_extract=build_search_extract_from_entry(
            language=language,
            entry=entry,
        ),
    )
