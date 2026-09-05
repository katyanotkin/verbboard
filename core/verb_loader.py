from __future__ import annotations

import hashlib
import time
from typing import Any

from core.models import Example, VerbEntry
from core.storage.verb_repository import get_candidate, get_verb, list_verbs

_ENTRIES_CACHE: dict[str, tuple[float, list[VerbEntry]]] = {}
_CACHE_TTL = 300.0


def _firestore_document_to_verb_entry(document: dict[str, Any]) -> VerbEntry:
    examples = [
        Example(
            # regen-format examples store the native sentence in "src" and English in "dst";
            # old-format examples store the native sentence directly in "dst"
            dst=example.get("src") or example["dst"],
            translations={
                k: v for k, v in example.get("translations", {}).items() if isinstance(k, str) and isinstance(v, str)
            },
        )
        for example in document.get("examples", [])
        if isinstance(example, dict) and isinstance(example.get("dst"), str)
    ]

    rank = document.get("rank")
    if rank is None:
        rank = 999999

    return VerbEntry(
        id=document["verb_id"],
        rank=int(rank),
        lemma=document["lemma"],
        forms=document.get("forms", {}),
        examples=examples,
        morph=document.get("morph"),
        tags=document.get("tags"),
        display_lemma=document.get("display_lemma"),
        display_forms=document.get("display_forms"),
        tts_forms=document.get("tts_forms"),
        lemma_translations={
            k: v
            for k, v in (document.get("lemma_translations") or {}).items()
            if isinstance(k, str) and isinstance(v, str)
        },
        created_at=document.get("created_at", ""),
    )


def load_entries_for_language(*, language: str) -> list[VerbEntry]:
    now = time.monotonic()
    cached = _ENTRIES_CACHE.get(language)
    if cached is not None and now - cached[0] < _CACHE_TTL:
        return cached[1]

    documents = list_verbs(language)
    entries = [_firestore_document_to_verb_entry(document) for document in documents]
    entries.sort(key=lambda entry: entry.rank)

    _ENTRIES_CACHE[language] = (now, entries)
    return entries


def invalidate_entries_cache(language: str) -> None:
    _ENTRIES_CACHE.pop(language, None)


def pick_verb_of_the_day(entries: list[VerbEntry], *, language: str, date_str: str) -> VerbEntry | None:
    """Deterministically pick one verb per (language, date) from an already-loaded
    entries list -- no new storage, no extra Firestore read. Same date-hash idiom
    as session fingerprinting (core/analytics/session_tracker.py).

    Indexes into entries sorted by id, not the caller's rank order: ranks can
    change (an admin edit, a promotion) between cache refreshes, which would
    otherwise shift every entry's list position and flip the pick mid-day.
    """
    if not entries:
        return None
    stable_entries = sorted(entries, key=lambda entry: entry.id)
    digest = hashlib.sha256(f"{language}|{date_str}".encode()).hexdigest()
    index = int(digest, 16) % len(stable_entries)
    return stable_entries[index]


def load_entry_by_id(
    *,
    language: str,
    verb_id: str,
    source: str = "firestore",
) -> VerbEntry | None:
    if source == "candidate":
        document = get_candidate(verb_id)
        if document is None:
            return None
        if document.get("language") != language:
            return None
        return _firestore_document_to_verb_entry(document)
    # Serve from the in-process list cache when it's warm -- avoids a Firestore
    # round-trip on every /learn page load after /verbs has been fetched.
    cached = _ENTRIES_CACHE.get(language)
    if cached is not None and time.monotonic() - cached[0] < _CACHE_TTL:
        for entry in cached[1]:
            if entry.id == verb_id:
                return entry

    document = get_verb(verb_id)
    if document is None:
        return None
    if document.get("language") != language:
        return None
    return _firestore_document_to_verb_entry(document)
