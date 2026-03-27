from __future__ import annotations

from typing import Any
from datetime import datetime, timezone


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
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()

    return {
        "language": language,
        "verb_id": verb_id,
        "lemma": lemma,
        "rank": rank,
        "forms": forms,
        "examples": examples,
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
        rank=entry.get("rank"),
        forms=entry.get("forms", {}),
        examples=entry.get("examples", []),
    )
