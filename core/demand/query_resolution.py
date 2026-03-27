from __future__ import annotations

from typing import Any

from core.search_utils import find_best_entry, normalize_text, score_entry
from core.storage.verb_repository import list_verbs


class FirestoreEntryAdapter:
    def __init__(self, document: dict[str, Any]) -> None:
        self.id = document.get("verb_id")
        self.lemma = document.get("lemma")
        self.forms = document.get("forms")
        self.display_lemma = document.get("display_lemma")


def resolve_query(
    *,
    language: str,
    query: str,
    min_score: int = 65,
) -> dict[str, Any]:
    normalized_query = normalize_text(query)

    if not normalized_query:
        return {
            "language": language,
            "query": query,
            "normalized_query": normalized_query,
            "resolved": False,
            "verb_id": None,
            "lemma": None,
            "match_score": None,
        }

    entries = [FirestoreEntryAdapter(document) for document in list_verbs(language)]

    best_entry = find_best_entry(entries, query, min_score=min_score)

    if best_entry is None:
        return {
            "language": language,
            "query": query,
            "normalized_query": normalized_query,
            "resolved": False,
            "verb_id": None,
            "lemma": None,
            "match_score": None,
        }

    return {
        "language": language,
        "query": query,
        "normalized_query": normalized_query,
        "resolved": True,
        "verb_id": best_entry.id,
        "lemma": best_entry.lemma,
        "match_score": score_entry(query, best_entry),
    }
