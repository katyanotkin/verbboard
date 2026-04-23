from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import anthropic

from core.settings import _load_anthropic_api_key, _GENERATION_SYSTEM_PROMPT
from core.storage.firestore_db import get_db
from core.storage.verb_document import (
    build_storage_verb_id,
    build_search_extract_from_entry,
)

logger = logging.getLogger(__name__)

VERBS_COLLECTION = "verbs"


def _get_max_rank(language: str) -> int:
    db = get_db()
    docs = db.collection(VERBS_COLLECTION).where("language", "==", language).stream()
    max_rank = 0
    for doc in docs:
        data = doc.to_dict()
        rank = data.get("rank")
        if isinstance(rank, (int, float)) and rank > max_rank:
            max_rank = int(rank)
    return max_rank


def generate_and_promote_verb(language: str, lemma: str) -> dict[str, Any] | None:
    """Generate a verb via Claude and write it directly to the verbs collection."""
    try:
        api_key = _load_anthropic_api_key()
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=_GENERATION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"language: {language}\nraw query (may be any inflected form): {lemma}",
                }
            ],
        )
        raw = message.content[0].text.strip()
        generated = json.loads(raw)
    except Exception:
        logger.exception("Failed to generate verb for %s/%s", language, lemma)
        return None

    resolved_lemma = generated.get("lemma") or lemma
    verb_id = build_storage_verb_id(language=language, lemma=resolved_lemma)
    now = datetime.now(UTC).isoformat()
    rank = _get_max_rank(language) + 1

    doc = {
        "language": language,
        "verb_id": verb_id,
        "lemma": resolved_lemma,
        "morph": generated.get("morph") or None,
        "rank": rank,
        "forms": generated.get("forms", {}),
        "examples": generated.get("examples", []),
        "search_extract": build_search_extract_from_entry(
            language=language, entry=generated
        ),
        "created_at": now,
        "updated_at": now,
    }

    db = get_db()
    existing = db.collection(VERBS_COLLECTION).document(verb_id).get()
    if existing.exists:
        logger.info("Verb %s already exists, skipping promotion", verb_id)
        return existing.to_dict()

    db.collection(VERBS_COLLECTION).document(verb_id).set(doc)
    logger.info("Auto-promoted pair verb %s", verb_id)
    return doc
