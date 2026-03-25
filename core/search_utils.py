from __future__ import annotations
import re
from typing import Any


def flatten_values(value: Any) -> list[str]:
    """Extract all string values from nested dict/list structures."""
    result: list[str] = []

    if isinstance(value, str):
        if value.strip():
            result.append(value)

    elif isinstance(value, dict):
        for v in value.values():
            result.extend(flatten_values(v))

    elif isinstance(value, list):
        for v in value:
            result.extend(flatten_values(v))

    return result


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    return re.sub(r"\s+", " ", text.strip().lower())


def build_search_candidates(entry) -> list[str]:
    """Extract all searchable strings from a verb entry."""
    candidates: list[str] = []

    # id
    if entry.id:
        candidates.append(str(entry.id))

    # lemma
    lemma = entry.lemma
    if isinstance(lemma, dict):
        candidates.extend(flatten_values(lemma))
    elif lemma:
        candidates.append(str(lemma))

    # display lemma
    display = getattr(entry, "display_lemma", None)
    if isinstance(display, dict):
        candidates.extend(flatten_values(display))
    elif display:
        candidates.append(str(display))

    # forms
    forms = getattr(entry, "forms", None)
    if forms:
        candidates.extend(flatten_values(forms))

    return candidates


def match_entry(query: str, entry) -> bool:
    """Check if query matches entry."""
    q = normalize_text(query)

    for candidate in build_search_candidates(entry):
        c = normalize_text(candidate)

        if q == c:
            return True

        if q in c:
            return True

    return False
