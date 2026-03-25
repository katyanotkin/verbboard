from __future__ import annotations

import re
from typing import Any


def flatten_values(value: Any) -> list[str]:
    """Extract all non-empty string values from nested dict/list structures."""
    result: list[str] = []

    if isinstance(value, str):
        if value.strip():
            result.append(value)
    elif isinstance(value, dict):
        for nested_value in value.values():
            result.extend(flatten_values(nested_value))
    elif isinstance(value, list):
        for nested_value in value:
            result.extend(flatten_values(nested_value))

    return result


def normalize_text(text: str) -> str:
    """Normalize text for matching."""
    return re.sub(r"\s+", " ", text.strip().casefold())


def tokenize_text(text: str) -> list[str]:
    """
    Split into simple tokens.
    Keeps Cyrillic/Latin letters, strips punctuation-ish separators.
    """
    normalized = normalize_text(text)
    if not normalized:
        return []

    return [token for token in re.split(r"[^0-9a-zа-яё]+", normalized) if token]


def build_search_candidates(entry: Any) -> list[str]:
    """Extract all searchable strings from a verb entry."""
    candidates: list[str] = []

    if getattr(entry, "id", None):
        candidates.append(str(entry.id))

    lemma = getattr(entry, "lemma", None)
    if isinstance(lemma, dict):
        candidates.extend(flatten_values(lemma))
    elif lemma:
        candidates.append(str(lemma))

    display_lemma = getattr(entry, "display_lemma", None)
    if isinstance(display_lemma, dict):
        candidates.extend(flatten_values(display_lemma))
    elif display_lemma:
        candidates.append(str(display_lemma))

    forms = getattr(entry, "forms", None)
    if forms:
        candidates.extend(flatten_values(forms))

    # de-duplicate while preserving order
    seen: set[str] = set()
    unique_candidates: list[str] = []

    for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if not normalized_candidate or normalized_candidate in seen:
            continue
        seen.add(normalized_candidate)
        unique_candidates.append(candidate)

    return unique_candidates


def score_candidate(query: str, candidate: str) -> int | None:
    """
    Score a candidate against the query.
    Higher is better.
    Returns None if no match at all.

    Ranking:
    - 100: exact full-string match
    - 90: exact token match
    - 75: candidate starts with query
    - 65: token starts with query
    - 40: substring match (disabled for very short queries)
    """
    normalized_query = normalize_text(query)
    normalized_candidate = normalize_text(candidate)

    if not normalized_query or not normalized_candidate:
        return None

    if normalized_query == normalized_candidate:
        return 100

    candidate_tokens = tokenize_text(normalized_candidate)

    if normalized_query in candidate_tokens:
        return 90

    if normalized_candidate.startswith(normalized_query):
        return 75

    if any(token.startswith(normalized_query) for token in candidate_tokens):
        return 65

    # Weak substring only for longer queries.
    # This prevents nonsense like "пить" -> "купить" from winning too easily.
    if len(normalized_query) >= 4 and normalized_query in normalized_candidate:
        return 40

    return None


def score_entry(query: str, entry: Any) -> int | None:
    """Return best score across all candidates for an entry."""
    best_score: int | None = None

    for candidate in build_search_candidates(entry):
        score = score_candidate(query, candidate)
        if score is None:
            continue
        if best_score is None or score > best_score:
            best_score = score

    return best_score


def find_best_entry(entries: list[Any], query: str, min_score: int = 65) -> Any | None:
    """
    Return the best-matching entry for the query.

    Only returns a match if its score is at least min_score.
    This prevents weak substring matches like "пить" -> "купить".
    """
    best_entry: Any | None = None
    best_score: int | None = None

    for entry in entries:
        score = score_entry(query, entry)
        if score is None:
            continue

        if best_score is None or score > best_score:
            best_score = score
            best_entry = entry

    if best_score is None or best_score < min_score:
        return None

    return best_entry
