from __future__ import annotations

import time
from typing import Any

from core.lexicon import index_by_id, load_lexicon
from core.models import Example, VerbEntry
from core.paths import DATA_DIR
from core.storage.verb_repository import get_candidate, get_verb, list_verbs

_ENTRIES_CACHE: dict[tuple[str, str], tuple[float, list[VerbEntry]]] = {}
_CACHE_TTL = 60.0


def _firestore_document_to_verb_entry(document: dict[str, Any]) -> VerbEntry:
    examples = [
        Example(
            dst=example["dst"],
            translations={
                k: v
                for k, v in example.get("translations", {}).items()
                if isinstance(k, str) and isinstance(v, str)
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
    )


def load_entries_for_language(*, language: str, source: str) -> list[VerbEntry]:
    cache_key = (language, source)
    now = time.monotonic()
    cached = _ENTRIES_CACHE.get(cache_key)
    if cached is not None and now - cached[0] < _CACHE_TTL:
        return cached[1]

    if source == "firestore":
        documents = list_verbs(language)
        entries = [
            _firestore_document_to_verb_entry(document) for document in documents
        ]
        entries.sort(key=lambda entry: entry.rank)
    else:
        lexicon_path = DATA_DIR / language / "lexicon.json"
        entries = load_lexicon(lexicon_path)

    _ENTRIES_CACHE[cache_key] = (now, entries)
    return entries


def load_entry_by_id(
    *,
    language: str,
    verb_id: str,
    source: str,
) -> VerbEntry | None:
    if source == "candidate":
        document = get_candidate(verb_id)
        if document is None:
            return None
        if document.get("language") != language:
            return None
        return _firestore_document_to_verb_entry(document)
    if source == "firestore":
        document = get_verb(verb_id)
        if document is None:
            return None
        if document.get("language") != language:
            return None
        return _firestore_document_to_verb_entry(document)
    entries = load_entries_for_language(language=language, source=source)
    return index_by_id(entries).get(verb_id)
