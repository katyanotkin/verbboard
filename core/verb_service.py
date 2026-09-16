from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import anthropic

from core.settings import _load_anthropic_api_key
from core.settings_ai import get_cached_system
from core.storage.firestore_db import get_db
from core.storage.verb_document import (
    build_search_extract_from_entry,
    build_storage_verb_id,
)

logger = logging.getLogger(__name__)

VERBS_COLLECTION = "verbs"
# Bookkeeping only -- never read as a source of verb data, just a marker that a
# given input lemma was already tried and either failed outright or resolved
# to a different lemma. Prevents an unbounded retry loop from paying a fresh
# Claude call on every render of a page that keeps missing the same lookup key
# (see core/languages/ru/plugin.py's pair-lemma lookup). Bounded by
# _PAIR_ATTEMPT_RETRY_AFTER: a transient failure (network blip, a malformed
# one-off Claude response) must not permanently blacklist a lemma with no
# recovery path, so an attempt older than the window is treated as expired
# and retried.
_PAIR_ATTEMPTS_COLLECTION = "verb_pair_generation_attempts"
_PAIR_ATTEMPT_RETRY_AFTER = timedelta(hours=24)

# In-process dedup: prevents redundant concurrent generation for the same
# (language, lemma) -- mirrors core/verb_autogen.py's _GENERATING set.
_GENERATING: set[str] = set()


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


def _pair_attempt_status(verb_id: str) -> tuple[bool, str | None]:
    """Return (blocked, resolved_verb_id).

    resolved_verb_id is set when a previous attempt recorded that Claude
    resolved this lemma to a different verb_id -- the caller should check
    whether that doc now exists live before giving up, since the generation
    itself may have already succeeded under that other id.
    """
    db = get_db()
    doc = db.collection(_PAIR_ATTEMPTS_COLLECTION).document(verb_id).get()
    if not doc.exists:
        return False, None

    data = doc.to_dict() or {}
    resolved_verb_id = data.get("resolved_verb_id")

    try:
        attempted_at = datetime.fromisoformat(data.get("attempted_at", ""))
    except ValueError:
        return False, resolved_verb_id

    blocked = datetime.now(UTC) - attempted_at <= _PAIR_ATTEMPT_RETRY_AFTER
    return blocked, resolved_verb_id


def _write_pair_attempt(
    verb_id: str, *, language: str, lemma: str, reason: str, resolved_verb_id: str | None = None
) -> None:
    db = get_db()
    db.collection(_PAIR_ATTEMPTS_COLLECTION).document(verb_id).set(
        {
            "verb_id": verb_id,
            "language": language,
            "lemma": lemma,
            "reason": reason,
            "resolved_verb_id": resolved_verb_id,
            "attempted_at": datetime.now(UTC).isoformat(),
        }
    )


def generate_and_promote_verb(language: str, lemma: str) -> dict[str, Any] | None:
    """Generate a verb via Claude and write it directly to the verbs collection.

    Bounded to at most one Claude call per (language, lemma) key: an in-process
    set dedups concurrent callers, and a persisted "attempted" marker stops a
    lookup key that keeps missing (generation failure, or Claude resolving to a
    differently-spelled lemma) from paying a fresh call on every future render.
    """
    verb_id = build_storage_verb_id(language=language, lemma=lemma)
    dedup_key = f"{language}:{verb_id}"
    if dedup_key in _GENERATING:
        return None
    _GENERATING.add(dedup_key)
    try:
        db = get_db()
        existing = db.collection(VERBS_COLLECTION).document(verb_id).get()
        if existing.exists:
            return existing.to_dict()

        blocked, known_resolved_verb_id = _pair_attempt_status(verb_id)
        if known_resolved_verb_id:
            resolved_doc = db.collection(VERBS_COLLECTION).document(known_resolved_verb_id).get()
            if resolved_doc.exists:
                return resolved_doc.to_dict()
        if blocked:
            logger.info(
                "Skipping generation for %s/%s: attempted within the last %s, will retry after that",
                language,
                lemma,
                _PAIR_ATTEMPT_RETRY_AFTER,
            )
            return None

        try:
            api_key = _load_anthropic_api_key()
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                system=get_cached_system(language),
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
            _write_pair_attempt(verb_id, language=language, lemma=lemma, reason="generation_failed")
            return None

        resolved_lemma = generated.get("lemma") or lemma
        resolved_verb_id = build_storage_verb_id(language=language, lemma=resolved_lemma)

        if resolved_verb_id != verb_id:
            # Claude resolved to a different spelling than the key we looked up
            # under -- record the attempt (with the resolved id) so a future
            # call under this exact input lemma checks the resolved doc first
            # instead of unconditionally paying for another Claude call.
            _write_pair_attempt(
                verb_id,
                language=language,
                lemma=lemma,
                reason="resolved_to_different_lemma",
                resolved_verb_id=resolved_verb_id,
            )

        now = datetime.now(UTC).isoformat()
        rank = _get_max_rank(language) + 1

        doc = {
            "language": language,
            "verb_id": resolved_verb_id,
            "lemma": resolved_lemma,
            "morph": generated.get("morph") or None,
            "rank": rank,
            "forms": generated.get("forms", {}),
            "examples": generated.get("examples", []),
            "search_extract": build_search_extract_from_entry(language=language, entry=generated),
            "created_at": now,
            "updated_at": now,
        }

        existing_resolved = db.collection(VERBS_COLLECTION).document(resolved_verb_id).get()
        if existing_resolved.exists:
            return existing_resolved.to_dict()

        db.collection(VERBS_COLLECTION).document(resolved_verb_id).set(doc)
        logger.info("Auto-promoted pair verb %s", resolved_verb_id)
        return doc
    finally:
        _GENERATING.discard(dedup_key)
