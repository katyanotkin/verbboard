from __future__ import annotations

from typing import Any

from core.lexicon import index_by_id, load_lexicon
from core.models import Example, VerbEntry
from core.paths import DATA_DIR
from core.storage.verb_repository import get_verb, list_verbs


def _firestore_document_to_verb_entry(document: dict[str, Any]) -> VerbEntry:
    examples = [
        Example(dst=example["dst"])
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
    if source == "firestore":
        documents = list_verbs(language)
        entries = [
            _firestore_document_to_verb_entry(document) for document in documents
        ]
        entries.sort(key=lambda entry: entry.rank)
        return entries

    lexicon_path = DATA_DIR / language / "lexicon.json"
    return load_lexicon(lexicon_path)


def load_entry_by_id(
    *,
    language: str,
    verb_id: str,
    source: str,
) -> VerbEntry | None:
    if source == "firestore":
        document = get_verb(verb_id)
        if document is None:
            return None
        if document.get("language") != language:
            return None
        return _firestore_document_to_verb_entry(document)

    entries = load_entries_for_language(language=language, source=source)
    return index_by_id(entries).get(verb_id)
