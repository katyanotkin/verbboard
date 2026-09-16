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
    entries list. Same date-hash idiom as session fingerprinting
    (core/analytics/session_tracker.py).

    Indexes into entries sorted by id, not the caller's rank order: ranks can
    change (an admin edit, a promotion) between cache refreshes, which would
    otherwise shift every entry's list position and flip the pick mid-day.

    This alone does NOT guarantee stability across catalog-size changes --
    the demand-driven generation pipeline can add a verb mid-day, changing
    `len(entries)` and therefore the index. get_verb_of_the_day() below is
    the actual stable entry point; call that, not this, unless you're
    computing a fresh pick to persist.
    """
    if not entries:
        return None
    stable_entries = sorted(entries, key=lambda entry: entry.id)
    digest = hashlib.sha256(f"{language}|{date_str}".encode()).hexdigest()
    index = int(digest, 16) % len(stable_entries)
    return stable_entries[index]


_VOTD_COLLECTION = "verb_of_the_day"


def get_verb_of_the_day(entries: list[VerbEntry], *, language: str, date_str: str) -> VerbEntry | None:
    """Stable Verb of the Day: persists the day's pick so it can't flip mid-day.

    pick_verb_of_the_day()'s hash-modulo-length approach breaks its own
    stability guarantee the moment the demand-driven generation pipeline adds
    a verb mid-day (len(entries) changes, so the index changes) -- and since
    core.verb_loader's own _ENTRIES_CACHE is process-local, two Cloud Run
    instances with differently-sized cached entries lists could independently
    compute two different picks for the same (language, date) even without
    that mid-day change. Persisting the first computed pick in Firestore
    fixes both: every instance reads the same stored verb_id for the rest of
    the day, and a later catalog-size change can't retroactively alter it.

    Uses create() (not set()) so a race between two near-simultaneous
    first-of-day requests across instances resolves to a single winner --
    same idempotent-first-write idiom as
    core.analytics.session_tracker._create_session().
    """
    if not entries:
        return None

    from google.api_core.exceptions import AlreadyExists

    from core.storage.firestore_db import get_db

    doc_id = f"{language}_{date_str}"
    db = get_db()
    doc_ref = db.collection(_VOTD_COLLECTION).document(doc_id)

    doc = doc_ref.get()
    doc_existed = doc.exists
    if doc_existed:
        stored_verb_id = (doc.to_dict() or {}).get("verb_id")
        for entry in entries:
            if entry.id == stored_verb_id:
                return entry
        # Stored pick no longer exists in the current catalog (e.g. manually
        # deleted) -- fall through and repick, then overwrite the stale doc
        # directly below (no create()/AlreadyExists race to resolve here,
        # since the doc already exists -- that's how we got into this branch).

    picked = pick_verb_of_the_day(entries, language=language, date_str=date_str)
    if picked is None:
        return None

    payload = {"language": language, "date": date_str, "verb_id": picked.id}

    if doc_existed:
        doc_ref.set(payload)
        return picked

    try:
        doc_ref.create(payload)
    except AlreadyExists:
        # Another request won the race and persisted first -- defer to it.
        doc = doc_ref.get()
        stored_verb_id = (doc.to_dict() or {}).get("verb_id")
        for entry in entries:
            if entry.id == stored_verb_id:
                return entry

    return picked


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
