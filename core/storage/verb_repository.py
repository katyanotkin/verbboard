from __future__ import annotations

from typing import Any

from core.storage.firestore_db import get_db
from core.storage.verb_document import build_verb_doc_id

COLLECTION = "verbs"


def get_verb(verb_id: str) -> dict[str, Any] | None:
    db = get_db()
    document = db.collection(COLLECTION).document(build_verb_doc_id(verb_id)).get()

    if not document.exists:
        return None

    return document.to_dict()


def upsert_verb(
    verb_id: str,
    payload: dict[str, Any],
) -> None:
    db = get_db()
    db.collection(COLLECTION).document(build_verb_doc_id(verb_id)).set(payload)
