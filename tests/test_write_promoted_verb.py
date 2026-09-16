"""Tests for core/verb_autogen.py's _write_promoted_verb().

_write_promoted_verb dual-writes a candidate record (verb_candidates,
status="promoted") and the live record (verbs) atomically via a single
Firestore batch, so a crash mid-write can't leave one collection updated
without the other. This isolates that batching behavior with a mocked
Firestore db, following the same pattern as
tests/test_progress_batch_repository.py (db.batch() returning an
inspectable MagicMock rather than relying on chained-mock auto-creation,
which would silently "pass" without validating what was actually written).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.verb_autogen import _CANDIDATES_COLLECTION, _VERBS_COLLECTION, _write_promoted_verb


def _make_fake_db() -> MagicMock:
    """A db mock whose .batch() returns a fresh, inspectable MagicMock each
    call, and whose .collection(name).document(id) returns a ref carrying
    identifying `.collection_name` / `.id` attributes so batch.set() calls
    can be matched back to which collection+doc they targeted."""

    created_batches: list[MagicMock] = []

    def _new_batch() -> MagicMock:
        batch = MagicMock()
        created_batches.append(batch)
        return batch

    def _collection(name: str) -> MagicMock:
        col = MagicMock()

        def _document(doc_id: str) -> MagicMock:
            ref = MagicMock()
            ref.collection_name = name
            ref.id = doc_id
            return ref

        col.document.side_effect = _document
        return col

    db = MagicMock()
    db.collection.side_effect = _collection
    db.batch.side_effect = _new_batch
    db.created_batches = created_batches
    return db


def _call_write_promoted_verb(db: MagicMock) -> None:
    with (
        patch("core.verb_autogen.get_db", return_value=db),
        patch("core.admin_logging.resolve_signal_label") as mock_resolve_signal_label,
    ):
        _write_promoted_verb(
            language="en",
            verb_id="en_go",
            lemma="go",
            rank=5,
            forms={"base": "go"},
            examples=[{"src": "I go.", "dst": "I go."}],
            morph={"pos": "verb"},
            search_extract=["go"],
            pronoun_forms=None,
            query="go",
        )
    mock_resolve_signal_label.assert_called_once_with(language="en", query="go")


def test_write_promoted_verb_commits_a_single_batch_with_both_docs() -> None:
    db = _make_fake_db()

    _call_write_promoted_verb(db)

    assert len(db.created_batches) == 1
    batch = db.created_batches[0]

    assert batch.set.call_count == 2
    batch.commit.assert_called_once()


def test_write_promoted_verb_writes_correctly_shaped_candidate_and_live_docs() -> None:
    db = _make_fake_db()

    _call_write_promoted_verb(db)

    batch = db.created_batches[0]
    payload_by_collection = {
        call.args[0].collection_name: (call.args[0].id, call.args[1]) for call in batch.set.call_args_list
    }

    assert set(payload_by_collection.keys()) == {_CANDIDATES_COLLECTION, _VERBS_COLLECTION}

    candidate_id, candidate_doc = payload_by_collection[_CANDIDATES_COLLECTION]
    live_id, live_doc = payload_by_collection[_VERBS_COLLECTION]

    assert candidate_id == "en_go"
    assert live_id == "en_go"

    # Candidate record carries the auditable trail fields...
    assert candidate_doc["status"] == "promoted"
    assert candidate_doc["source"] == "autogen"
    assert candidate_doc["query"] == "go"

    # ...the live record must NOT carry them (matches manually-promoted verb shape).
    assert "status" not in live_doc
    assert "source" not in live_doc
    assert "query" not in live_doc

    # Both share the same underlying verb data.
    for doc in (candidate_doc, live_doc):
        assert doc["verb_id"] == "en_go"
        assert doc["language"] == "en"
        assert doc["lemma"] == "go"
        assert doc["rank"] == 5
        assert doc["forms"] == {"base": "go"}
        assert doc["examples"] == [{"src": "I go.", "dst": "I go."}]
        assert doc["morph"] == {"pos": "verb"}
        assert doc["search_extract"] == ["go"]
        assert "pronoun_forms" not in doc


def test_write_promoted_verb_includes_pronoun_forms_when_present() -> None:
    db = _make_fake_db()

    with (
        patch("core.verb_autogen.get_db", return_value=db),
        patch("core.admin_logging.resolve_signal_label"),
    ):
        _write_promoted_verb(
            language="en",
            verb_id="en_go",
            lemma="go",
            rank=5,
            forms={"base": "go"},
            examples=[],
            morph=None,
            search_extract=["go"],
            pronoun_forms={"1sg": "I"},
            query="go",
        )

    batch = db.created_batches[0]
    for call in batch.set.call_args_list:
        doc = call.args[1]
        assert doc["pronoun_forms"] == {"1sg": "I"}


def test_write_promoted_verb_does_not_commit_if_first_set_raises() -> None:
    """If the batch construction/set step blows up before commit, no partial
    write should be flushed -- guards against a future refactor accidentally
    calling commit() outside the batch's own atomicity guarantee."""
    db = _make_fake_db()
    batch = MagicMock()
    batch.set.side_effect = RuntimeError("boom")
    db.batch.side_effect = lambda: batch

    with (
        patch("core.verb_autogen.get_db", return_value=db),
        patch("core.admin_logging.resolve_signal_label"),
    ):
        try:
            _write_promoted_verb(
                language="en",
                verb_id="en_go",
                lemma="go",
                rank=5,
                forms={"base": "go"},
                examples=[],
                morph=None,
                search_extract=["go"],
                pronoun_forms=None,
                query="go",
            )
        except RuntimeError:
            pass

    batch.commit.assert_not_called()
