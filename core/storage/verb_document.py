from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from core.search_utils import flatten_values, normalize_text


def build_verb_doc_id(verb_id: str) -> str:
    return verb_id


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
