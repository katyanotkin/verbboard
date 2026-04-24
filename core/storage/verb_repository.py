from __future__ import annotations

from typing import Any

from core.settings import load_settings
from core.storage.firestore_db import get_db
from core.storage.verb_document import build_verb_doc_id

COLLECTION = "verbs"


def get_verb(verb_id: str) -> dict[str, Any] | None:
    db = get_db()
    document = db.collection(COLLECTION).document(build_verb_doc_id(verb_id)).get()

    if not document.exists:
        return None

    return document.to_dict()


def list_verbs(language: str) -> list[dict[str, Any]]:
    db = get_db()
    documents = db.collection(COLLECTION).where("language", "==", language).stream()
    return [document.to_dict() for document in documents]


def upsert_verb(
    verb_id: str,
    payload: dict[str, Any],
) -> None:
    db = get_db()
    doc_ref = db.collection(COLLECTION).document(build_verb_doc_id(verb_id))

    existing = doc_ref.get()

    if existing.exists:
        existing_data = existing.to_dict()
        payload["created_at"] = existing_data.get("created_at")

    doc_ref.set(payload)


def find_verb_by_search_extract(language: str, query: str) -> dict[str, Any] | None:
    normalized = query.strip().casefold()
    if not normalized:
        return None

    db = get_db()
    docs = (
        db.collection(COLLECTION)
        .where("language", "==", language)
        .where("search_extract", "array_contains", normalized)
        .limit(1)
        .stream()
    )

    for doc in docs:
        return doc.to_dict()

    return None


def get_candidate(verb_id: str) -> dict[str, Any] | None:
    db = get_db()
    collection = load_settings().verb_candidates_collection
    document = db.collection(collection).document(verb_id).get()
    if not document.exists:
        return None
    return document.to_dict()


def find_verb_by_lemma(language: str, lemma: str) -> dict[str, Any] | None:
    db = get_db()
    docs = (
        db.collection(COLLECTION)
        .where("language", "==", language)
        .where("lemma", "==", lemma)
        .limit(1)
        .stream()
    )
    for doc in docs:
        return doc.to_dict()
    return None


def list_verbs_recent(language: str, limit: int = 20) -> list[dict[str, Any]]:
    """Return the most recently added verbs for a language."""
    db = get_db()
    docs = (
        db.collection(COLLECTION)
        .where("language", "==", language)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
        .stream()
    )
    return [d.to_dict() for d in docs]
