from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.search_utils import flatten_values, normalize_text


def build_verb_doc_id(verb_id: str) -> str:
    return verb_id


def _dedupe_search_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        normalized_value = normalize_text(value)
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        result.append(value)

    return result


def build_search_extract_from_lexicon_entry(
    *,
    language: str,
    entry: dict[str, Any],
) -> list[str]:
    candidates: list[str] = []

    lemma = entry.get("lemma")
    if isinstance(lemma, str) and lemma.strip():
        candidates.append(lemma)

    display_lemma = entry.get("display_lemma")
    if isinstance(display_lemma, str) and display_lemma.strip():
        candidates.append(display_lemma)

    forms = entry.get("forms")
    if forms:
        candidates.extend(flatten_values(forms))

    display_forms = entry.get("display_forms")
    if display_forms:
        candidates.extend(flatten_values(display_forms))

    if language == "he":
        morph = entry.get("morph")
        if isinstance(morph, dict):
            root = morph.get("root")
            if isinstance(root, str) and root.strip():
                candidates.append(root)

    return _dedupe_search_values(candidates)


def build_verb_document(
    *,
    language: str,
    verb_id: str,
    lemma: str,
    display_lemma: str | None,
    rank: int | None,
    forms: dict[str, Any],
    display_forms: dict[str, Any] | None,
    examples: list[dict[str, Any]],
    morph: dict[str, Any] | None,
    search_extract: list[str],
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()

    return {
        "language": language,
        "verb_id": verb_id,
        "lemma": lemma,
        "display_lemma": display_lemma,
        "rank": rank,
        "forms": forms,
        "display_forms": display_forms,
        "examples": examples,
        "morph": morph,
        "search_extract": search_extract,
        "created_at": now,
        "updated_at": now,
    }


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
        display_lemma=entry.get("display_lemma"),
        rank=entry.get("rank"),
        forms=entry.get("forms", {}),
        display_forms=entry.get("display_forms"),
        examples=entry.get("examples", []),
        morph=entry.get("morph"),
        search_extract=build_search_extract_from_lexicon_entry(
            language=language,
            entry=entry,
        ),
    )
