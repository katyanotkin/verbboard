"""upsert_verb's created_at handling (issue #56)."""

from __future__ import annotations

from datetime import UTC, datetime

from core.storage import verb_repository

FIRST = datetime(2026, 1, 1, tzinfo=UTC)
LATER = datetime(2026, 9, 1, tzinfo=UTC)


def _stored(fake_db, verb_id: str) -> dict:
    return fake_db.collection("verbs").document(verb_repository.build_verb_doc_id(verb_id)).get().to_dict()


def test_upsert_preserves_existing_created_at(fake_db) -> None:
    verb_repository.upsert_verb("en_go", {"lemma": "go", "created_at": FIRST})
    verb_repository.upsert_verb("en_go", {"lemma": "go", "created_at": LATER})
    assert _stored(fake_db, "en_go")["created_at"] == FIRST


def test_upsert_keeps_caller_created_at_when_existing_doc_lacks_it(fake_db) -> None:
    verb_repository.upsert_verb("en_go", {"lemma": "go"})
    verb_repository.upsert_verb("en_go", {"lemma": "go", "created_at": LATER})
    assert _stored(fake_db, "en_go")["created_at"] == LATER


def test_upsert_does_not_mutate_caller_payload(fake_db) -> None:
    verb_repository.upsert_verb("en_go", {"lemma": "go", "created_at": FIRST})
    payload = {"lemma": "go", "created_at": LATER}
    verb_repository.upsert_verb("en_go", payload)
    assert payload["created_at"] == LATER
