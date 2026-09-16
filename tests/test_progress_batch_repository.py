"""Unit tests for core/progress/progress_repository.py's set_known_batch().

Endpoint-level (auth, validation, real-Firestore round trip) coverage lives in
tests/test_progress_api.py alongside the rest of /api/progress/*. This file
isolates the batching/chunking and per-verb SRS-seeding logic with a mocked
Firestore db, since asserting "db.batch() called twice" and "the ladder is
only seeded for verbs that don't already have srs_box" is much more direct
against the repository function than through the full HTTP + real-Firestore
stack.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from core.progress.progress_repository import set_known_batch

# ---------------------------------------------------------------------------
# Fake Firestore chain -- only tracks what set_known_batch actually needs:
# leaf verb doc refs carrying `.id` == verb_id, db.get_all() reflecting a
# preset existing-srs_box map, and db.batch() returning inspectable batches.
# ---------------------------------------------------------------------------


class _FakeSnapshot:
    def __init__(self, doc_id: str, data: dict[str, Any] | None) -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict[str, Any] | None:
        return dict(self._data) if self._data is not None else None


class _FakeDocRef:
    def __init__(self, doc_id: str) -> None:
        self.id = doc_id

    def collection(self, name: str) -> "_FakeCollection":
        return _FakeCollection()

    def set(self, *args, **kwargs) -> None:
        pass  # language-container doc upsert; not under test here

    def get(self) -> _FakeSnapshot:
        return _FakeSnapshot(self.id, None)


class _FakeCollection:
    def document(self, doc_id: str) -> _FakeDocRef:
        return _FakeDocRef(doc_id)


def _make_fake_db(existing_srs_box: dict[str, int] | None = None) -> MagicMock:
    existing_srs_box = existing_srs_box or {}

    def _get_all(refs):
        return [
            _FakeSnapshot(ref.id, {"srs_box": existing_srs_box[ref.id]} if ref.id in existing_srs_box else {})
            for ref in refs
        ]

    created_batches: list[MagicMock] = []

    def _new_batch() -> MagicMock:
        batch = MagicMock()
        created_batches.append(batch)
        return batch

    db = MagicMock()
    db.collection.return_value = _FakeCollection()
    db.get_all.side_effect = _get_all
    db.batch.side_effect = _new_batch
    db.created_batches = created_batches
    return db


# ---------------------------------------------------------------------------
# Empty input is a no-op
# ---------------------------------------------------------------------------


def test_empty_verb_ids_is_a_noop() -> None:
    db = _make_fake_db()

    with patch("core.progress.progress_repository.get_db", return_value=db):
        set_known_batch(user_id="u1", language="en", verb_ids=[])

    assert db.batch.call_count == 0
    assert db.get_all.call_count == 0


# ---------------------------------------------------------------------------
# Per-verb SRS ladder seeding is preserved in the batched write
# ---------------------------------------------------------------------------


def test_srs_ladder_seeded_only_for_verbs_without_existing_srs_box() -> None:
    db = _make_fake_db(existing_srs_box={"en_has_box": 3})

    with patch("core.progress.progress_repository.get_db", return_value=db):
        set_known_batch(user_id="u1", language="en", verb_ids=["en_has_box", "en_no_box"])

    assert len(db.created_batches) == 1
    batch = db.created_batches[0]

    payload_by_verb = {call.args[0].id: call.args[1] for call in batch.set.call_args_list}
    assert set(payload_by_verb.keys()) == {"en_has_box", "en_no_box"}

    with_box_payload = payload_by_verb["en_has_box"]
    assert with_box_payload["known"] is True
    assert "srs_box" not in with_box_payload, "must not reset the ladder for a verb already on it"
    assert "srs_due_at" not in with_box_payload
    assert "srs_reviewed_at" not in with_box_payload

    without_box_payload = payload_by_verb["en_no_box"]
    assert without_box_payload["known"] is True
    assert without_box_payload["srs_box"] == 1
    assert without_box_payload["srs_due_at"] is not None
    assert without_box_payload["srs_reviewed_at"] is not None

    for call in batch.set.call_args_list:
        assert call.kwargs.get("merge") is True

    batch.commit.assert_called_once()


# ---------------------------------------------------------------------------
# Chunking: more than 400 verb_ids splits into two committed batches
# ---------------------------------------------------------------------------


def test_batches_of_more_than_400_verb_ids_split_into_two_chunks() -> None:
    verb_ids = [f"en_v{i}" for i in range(450)]
    db = _make_fake_db()

    with patch("core.progress.progress_repository.get_db", return_value=db):
        set_known_batch(user_id="u1", language="en", verb_ids=verb_ids)

    assert db.batch.call_count == 2
    assert len(db.created_batches) == 2

    first_batch, second_batch = db.created_batches
    assert len(first_batch.set.call_args_list) == 400
    assert len(second_batch.set.call_args_list) == 50
    first_batch.commit.assert_called_once()
    second_batch.commit.assert_called_once()

    all_written_ids = {call.args[0].id for batch in db.created_batches for call in batch.set.call_args_list}
    assert all_written_ids == set(verb_ids)


def test_exactly_400_verb_ids_is_a_single_batch() -> None:
    verb_ids = [f"en_v{i}" for i in range(400)]
    db = _make_fake_db()

    with patch("core.progress.progress_repository.get_db", return_value=db):
        set_known_batch(user_id="u1", language="en", verb_ids=verb_ids)

    assert db.batch.call_count == 1
    assert len(db.created_batches[0].set.call_args_list) == 400
    db.created_batches[0].commit.assert_called_once()
