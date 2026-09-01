"""
Unit tests for core/progress/progress_repository.py

Structure under test:
  user_progress/{uid}/languages/{lang}             <- language container {language}
  user_progress/{uid}/languages/{lang}/verbs/{vid} <- verb progress
  user_practice/{uid}/languages/{lang}             <- practice badges
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from core.progress import progress_repository as repo
from core.progress.models import LEITNER_MAX_BOX, PracticeProgress, VerbProgress


def _make_db():
    return MagicMock()


# Helpers for common reference depths in the mock chain.
# 4-level: user_progress/{uid}/languages/{lang}
def _lang_ref(db):
    return db.collection().document().collection().document()


# 6-level: user_progress/{uid}/languages/{lang}/verbs/{verb_id}
def _verb_ref(db):
    return db.collection().document().collection().document().collection().document()


# 5-level: the verbs *collection* under the language doc (stream lives here)
def _verbs_col(db):
    return db.collection().document().collection().document().collection()


# ---------------------------------------------------------------------------
# mark_seen  ->  user_progress/{uid}/languages/{lang}/verbs/{verb_id}
#                also upserts the language container doc
# ---------------------------------------------------------------------------


def test_mark_seen_targets_correct_path() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo.mark_seen(user_id="u1", language="en", verb_id="en_go")

    db.collection.assert_called_with("user_progress")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("languages")
    db.collection().document().collection().document.assert_called_with("en")
    db.collection().document().collection().document().collection.assert_called_with("verbs")
    db.collection().document().collection().document().collection().document.assert_called_with("en_go")


def test_mark_seen_writes_language_container_doc() -> None:
    """mark_seen must upsert the language container doc with a language field."""
    db = _make_db()
    lang_doc = _lang_ref(db)

    with patch.object(repo, "get_db", return_value=db):
        repo.mark_seen(user_id="u1", language="en", verb_id="en_go")

    args, kwargs = lang_doc.set.call_args
    payload = args[0]
    assert payload["language"] == "en"
    assert "user" not in payload, "user field is redundant (uid is in the path)"
    assert kwargs.get("merge") is True


def test_mark_seen_verb_payload() -> None:
    db = _make_db()
    verb_doc = _verb_ref(db)

    with patch.object(repo, "get_db", return_value=db):
        repo.mark_seen(user_id="u1", language="en", verb_id="en_go")

    args, kwargs = verb_doc.set.call_args
    payload = args[0]
    assert payload["seen"] is True
    assert payload["language"] == "en"
    assert payload["verb_id"] == "en_go"
    assert kwargs.get("merge") is True


# ---------------------------------------------------------------------------
# set_known  ->  user_progress/{uid}/languages/{lang}/verbs/{verb_id}
#                also upserts the language container doc
# ---------------------------------------------------------------------------


def test_set_known_targets_correct_path() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=True)

    db.collection.assert_called_with("user_progress")
    db.collection().document().collection().document().collection.assert_called_with("verbs")
    db.collection().document().collection().document().collection().document.assert_called_with("en_go")


def test_set_known_writes_language_container_doc() -> None:
    """set_known must also upsert the language container doc with a language field."""
    db = _make_db()
    lang_doc = _lang_ref(db)

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=True)

    args, kwargs = lang_doc.set.call_args
    payload = args[0]
    assert payload["language"] == "en"
    assert "user" not in payload, "user field is redundant (uid is in the path)"
    assert kwargs.get("merge") is True


def test_set_known_verb_payload_reflects_value() -> None:
    db = _make_db()
    verb_doc = _verb_ref(db)

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=False)

    args, _ = verb_doc.set.call_args
    assert args[0]["known"] is False


# ---------------------------------------------------------------------------
# set_known -- SRS ladder entry point (srs_box init on first known=True)
# ---------------------------------------------------------------------------


def test_set_known_true_initializes_srs_box_when_absent() -> None:
    """Marking known=True on a verb with no prior srs_box starts the ladder
    at box 1 with a due date and a reviewed_at timestamp."""
    db = _make_db()
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {}

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=True)

    args, _ = verb_doc.set.call_args
    payload = args[0]
    assert payload["srs_box"] == 1
    assert isinstance(payload["srs_due_at"], datetime)
    assert isinstance(payload["srs_reviewed_at"], datetime)


def test_set_known_true_treats_missing_srs_box_field_as_absent() -> None:
    """A verb doc that exists but has no srs_box field at all (pre-SRS-feature
    data) must also be initialized, not skipped."""
    db = _make_db()
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {"known": False, "seen": True}

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=True)

    args, _ = verb_doc.set.call_args
    assert args[0]["srs_box"] == 1


def test_set_known_true_does_not_reset_existing_srs_box() -> None:
    """Re-toggling known=True on a verb already in the ladder must not reset
    its box/due date -- explicit design decision (see repo docstring)."""
    db = _make_db()
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {
        "srs_box": 3,
        "srs_due_at": "existing-due",
        "srs_reviewed_at": "existing-reviewed",
    }

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=True)

    args, _ = verb_doc.set.call_args
    payload = args[0]
    assert "srs_box" not in payload
    assert "srs_due_at" not in payload
    assert "srs_reviewed_at" not in payload


def test_set_known_false_does_not_touch_srs_fields() -> None:
    """known=False must not read or write any srs_* field, and must not
    even query existing state (the SRS-init branch is known-only)."""
    db = _make_db()
    verb_doc = _verb_ref(db)

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=False)

    args, _ = verb_doc.set.call_args
    payload = args[0]
    assert "srs_box" not in payload
    assert "srs_due_at" not in payload
    assert "srs_reviewed_at" not in payload
    verb_doc.get.assert_not_called()


# ---------------------------------------------------------------------------
# record_review  ->  user_progress/{uid}/languages/{lang}/verbs/{verb_id}
#                     also upserts the language container doc
# ---------------------------------------------------------------------------


def test_record_review_targets_correct_path() -> None:
    db = _make_db()
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {}

    with patch.object(repo, "get_db", return_value=db):
        repo.record_review(user_id="u1", language="en", verb_id="en_go", recalled=True)

    db.collection.assert_called_with("user_progress")
    db.collection().document().collection().document().collection.assert_called_with("verbs")
    db.collection().document().collection().document().collection().document.assert_called_with("en_go")


def test_record_review_writes_language_container_doc() -> None:
    db = _make_db()
    lang_doc = _lang_ref(db)
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {}

    with patch.object(repo, "get_db", return_value=db):
        repo.record_review(user_id="u1", language="en", verb_id="en_go", recalled=True)

    args, kwargs = lang_doc.set.call_args
    assert args[0]["language"] == "en"
    assert kwargs.get("merge") is True


def test_record_review_promotes_from_existing_box() -> None:
    db = _make_db()
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {"srs_box": 2}

    with patch.object(repo, "get_db", return_value=db):
        result = repo.record_review(user_id="u1", language="en", verb_id="en_go", recalled=True)

    args, kwargs = verb_doc.set.call_args
    payload = args[0]
    assert payload["srs_box"] == 3
    assert payload["known"] is True
    assert isinstance(payload["srs_due_at"], datetime)
    assert isinstance(payload["srs_reviewed_at"], datetime)
    assert kwargs.get("merge") is True
    assert result["box"] == 3
    assert isinstance(result["due_at"], datetime)


def test_record_review_not_recalled_demotes_to_box_one() -> None:
    db = _make_db()
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {"srs_box": 4}

    with patch.object(repo, "get_db", return_value=db):
        result = repo.record_review(user_id="u1", language="en", verb_id="en_go", recalled=False)

    args, _ = verb_doc.set.call_args
    assert args[0]["srs_box"] == 1
    assert result["box"] == 1


def test_record_review_promotion_caps_at_max_box() -> None:
    db = _make_db()
    verb_doc = _verb_ref(db)
    verb_doc.get.return_value.to_dict.return_value = {"srs_box": LEITNER_MAX_BOX}

    with patch.object(repo, "get_db", return_value=db):
        result = repo.record_review(user_id="u1", language="en", verb_id="en_go", recalled=True)

    assert result["box"] == LEITNER_MAX_BOX


def test_record_review_no_prior_box_lands_on_box_one_regardless_of_recalled() -> None:
    """A verb with srs_box 0 (e.g. reviewed via the practice loop before ever
    being marked known through the normal set_known path) lands on box 1
    whether or not the review was recalled -- per leitner_next_box's box-0
    rule. Confirmed here against the actual repository function, not just
    asserted from reading the code."""
    for recalled in (True, False):
        db = _make_db()
        verb_doc = _verb_ref(db)
        verb_doc.get.return_value.to_dict.return_value = {}

        with patch.object(repo, "get_db", return_value=db):
            result = repo.record_review(user_id="u1", language="en", verb_id="en_go", recalled=recalled)

        assert result["box"] == 1, f"recalled={recalled} should still land on box 1"


# ---------------------------------------------------------------------------
# save_practice_progress  ->  user_practice/{uid}/languages/{lang}
# ---------------------------------------------------------------------------


def test_save_practice_targets_correct_path() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo.save_practice_progress(user_id="u1", language="en", badges=[3, 6])

    db.collection.assert_called_with("user_practice")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("languages")
    db.collection().document().collection().document.assert_called_with("en")


def test_save_practice_payload() -> None:
    db = _make_db()
    doc_ref = _lang_ref(db)

    with patch.object(repo, "get_db", return_value=db):
        repo.save_practice_progress(user_id="u1", language="en", badges=[3, 6, 9])

    args, kwargs = doc_ref.set.call_args
    payload = args[0]
    assert payload["badges"] == [3, 6, 9]
    assert payload["language"] == "en"
    assert kwargs.get("merge") is True


def test_save_practice_sets_started_at_on_first_write() -> None:
    """started_at is included in the payload when the doc does not yet exist."""
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = False
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        repo.save_practice_progress(user_id="u1", language="en", badges=[3])

    args, _ = doc_ref.set.call_args
    assert "started_at" in args[0]


def test_save_practice_sets_started_at_when_field_missing() -> None:
    """started_at is also written when the doc exists but lacks the field."""
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {"badges": [3], "language": "en"}
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        repo.save_practice_progress(user_id="u1", language="en", badges=[3, 6])

    args, _ = doc_ref.set.call_args
    assert "started_at" in args[0]


def test_save_practice_preserves_started_at_on_update() -> None:
    """started_at is NOT overwritten when the doc already has the field."""
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "badges": [3],
        "language": "en",
        "started_at": "2026-01-01T00:00:00Z",
    }
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        repo.save_practice_progress(user_id="u1", language="en", badges=[3, 6])

    args, _ = doc_ref.set.call_args
    assert "started_at" not in args[0]


# ---------------------------------------------------------------------------
# get_practice_progress  ->  user_practice/{uid}/languages/{lang}
# ---------------------------------------------------------------------------


def test_get_practice_targets_correct_path() -> None:
    db = _make_db()
    _lang_ref(db).get().to_dict.return_value = {}

    with patch.object(repo, "get_db", return_value=db):
        repo.get_practice_progress(user_id="u1", language="he")

    db.collection.assert_called_with("user_practice")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("languages")
    db.collection().document().collection().document.assert_called_with("he")


def test_get_practice_returns_model() -> None:
    db = _make_db()
    _lang_ref(db).get().to_dict.return_value = {
        "badges": [3, 6],
        "language": "en",
    }

    with patch.object(repo, "get_db", return_value=db):
        result = repo.get_practice_progress(user_id="u1", language="en")

    assert isinstance(result, PracticeProgress)
    assert result.language == "en"
    assert result.badges == [3, 6]


def test_get_practice_missing_doc_returns_empty_badges() -> None:
    db = _make_db()
    _lang_ref(db).get().to_dict.return_value = {}

    with patch.object(repo, "get_db", return_value=db):
        result = repo.get_practice_progress(user_id="u1", language="en")

    assert result.badges == []


# ---------------------------------------------------------------------------
# list_progress_for_language
#   path: user_progress/{uid}/languages/{lang}/verbs  (stream)
# ---------------------------------------------------------------------------


def test_list_progress_queries_correct_path() -> None:
    db = _make_db()
    _verbs_col(db).stream.return_value = iter([])

    with patch.object(repo, "get_db", return_value=db):
        repo.list_progress_for_language(user_id="u1", language="en")

    db.collection.assert_called_with("user_progress")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_any_call("languages")
    db.collection().document().collection().document.assert_called_with("en")
    db.collection().document().collection().document().collection.assert_called_with("verbs")


def test_list_progress_returns_verb_progress_models() -> None:
    db = _make_db()
    fake_doc = MagicMock()
    fake_doc.to_dict.return_value = {
        "language": "en",
        "verb_id": "en_go",
        "seen": True,
        "known": False,
    }
    _verbs_col(db).stream.return_value = iter([fake_doc])

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    assert len(results) == 1
    vp = results[0]
    assert isinstance(vp, VerbProgress)
    assert vp.verb_id == "en_go"
    assert vp.seen is True
    assert vp.known is False


def test_list_progress_skips_docs_without_verb_id() -> None:
    db = _make_db()
    bad_doc = MagicMock()
    bad_doc.to_dict.return_value = {"language": "en", "seen": True}
    _verbs_col(db).stream.return_value = iter([bad_doc])

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    assert results == []


def test_list_progress_empty_collection_returns_empty_list() -> None:
    db = _make_db()
    _verbs_col(db).stream.return_value = iter([])

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    assert results == []


def test_list_progress_multiple_verbs() -> None:
    db = _make_db()
    doc1 = MagicMock()
    doc1.to_dict.return_value = {
        "language": "en",
        "verb_id": "en_go",
        "seen": True,
        "known": True,
    }
    doc2 = MagicMock()
    doc2.to_dict.return_value = {
        "language": "en",
        "verb_id": "en_run",
        "seen": True,
        "known": False,
    }
    _verbs_col(db).stream.return_value = iter([doc1, doc2])

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    verb_ids = {r.verb_id for r in results}
    assert verb_ids == {"en_go", "en_run"}
    assert len(results) == 2


def test_list_progress_uses_language_param_as_fallback() -> None:
    """If the doc has no 'language' field, the function parameter is used."""
    db = _make_db()
    doc = MagicMock()
    doc.to_dict.return_value = {"verb_id": "en_go", "seen": True}
    _verbs_col(db).stream.return_value = iter([doc])

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    assert results[0].language == "en"


def test_list_progress_includes_srs_fields_when_box_positive() -> None:
    db = _make_db()
    now = datetime(2026, 8, 1, 12, 0, 0)
    due = datetime(2026, 8, 8, 12, 0, 0)
    doc = MagicMock()
    doc.to_dict.return_value = {
        "language": "en",
        "verb_id": "en_go",
        "seen": True,
        "known": True,
        "srs_box": 2,
        "srs_due_at": due,
        "srs_reviewed_at": now,
    }
    _verbs_col(db).stream.return_value = iter([doc])

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    vp = results[0]
    assert vp.srs_box == 2
    assert vp.srs_due_at == due
    assert vp.srs_reviewed_at == now


def test_list_progress_srs_box_defaults_to_zero_when_absent() -> None:
    db = _make_db()
    doc = MagicMock()
    doc.to_dict.return_value = {
        "language": "en",
        "verb_id": "en_go",
        "seen": True,
        "known": False,
    }
    _verbs_col(db).stream.return_value = iter([doc])

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    vp = results[0]
    assert vp.srs_box == 0
    assert vp.srs_due_at is None
    assert vp.srs_reviewed_at is None


# ---------------------------------------------------------------------------
# delete_all_progress_data
#   user_progress/{uid}/languages/{lang}/verbs/{vid} (+ parents)
#   user_practice/{uid}/languages/{lang} (+ parent, no verbs subcollection)
#   users/{uid}
# ---------------------------------------------------------------------------


def _make_deletion_db() -> MagicMock:
    """A db double whose .collection(name) is stable per collection name
    (unlike the bare-MagicMock helpers above, this test needs distinct
    mocks for "user_progress" vs "user_practice" vs "users" at once)."""
    db = MagicMock()
    cache: dict[str, MagicMock] = {}

    def _collection(name):
        return cache.setdefault(name, MagicMock())

    db.collection.side_effect = _collection
    return db


def test_delete_all_progress_data_deletes_verbs_before_language_before_parent() -> None:
    db = _make_deletion_db()
    order: list[str] = []

    progress_doc_ref = db.collection("user_progress").document.return_value

    verb_go = MagicMock()
    verb_go.reference.delete.side_effect = lambda: order.append("verb:en_go")
    verb_run = MagicMock()
    verb_run.reference.delete.side_effect = lambda: order.append("verb:en_run")

    lang_en = MagicMock()
    lang_en.reference.delete.side_effect = lambda: order.append("language:en")
    lang_en.reference.collection.return_value.stream.return_value = iter([verb_go, verb_run])

    progress_doc_ref.collection.return_value.stream.return_value = iter([lang_en])
    progress_doc_ref.delete.side_effect = lambda: order.append("parent:user_progress")

    practice_doc_ref = db.collection("user_practice").document.return_value
    practice_lang_en = MagicMock()
    practice_lang_en.reference.delete.side_effect = lambda: order.append("practice_language:en")
    practice_doc_ref.collection.return_value.stream.return_value = iter([practice_lang_en])
    practice_doc_ref.delete.side_effect = lambda: order.append("parent:user_practice")

    users_doc_ref = db.collection("users").document.return_value
    users_doc_ref.delete.side_effect = lambda: order.append("users_doc")

    with patch.object(repo, "get_db", return_value=db):
        repo.delete_all_progress_data("u1")

    # Verb docs deleted before their parent language doc.
    assert order.index("verb:en_go") < order.index("language:en")
    assert order.index("verb:en_run") < order.index("language:en")
    # Language docs deleted before the parent user_progress/{uid} doc.
    assert order.index("language:en") < order.index("parent:user_progress")
    # user_practice's language doc is also cleaned up (no verbs subcollection there).
    assert order.index("practice_language:en") < order.index("parent:user_practice")
    # users/{uid} is removed too.
    assert "users_doc" in order

    db.collection.assert_any_call("user_progress")
    db.collection.assert_any_call("user_practice")
    db.collection.assert_any_call("users")
    db.collection("user_progress").document.assert_any_call("u1")
    db.collection("user_practice").document.assert_any_call("u1")
    db.collection("users").document.assert_any_call("u1")


def test_delete_all_progress_data_handles_account_with_no_data() -> None:
    """A user with no progress/practice history yet must not crash the
    deletion pipeline -- empty streams, parent docs still get delete() calls
    (a Firestore delete() on a nonexistent doc is a no-op, not an error)."""
    db = _make_deletion_db()

    progress_doc_ref = db.collection("user_progress").document.return_value
    progress_doc_ref.collection.return_value.stream.return_value = iter([])

    practice_doc_ref = db.collection("user_practice").document.return_value
    practice_doc_ref.collection.return_value.stream.return_value = iter([])

    with patch.object(repo, "get_db", return_value=db):
        repo.delete_all_progress_data("u1")  # must not raise

    progress_doc_ref.delete.assert_called_once()
    practice_doc_ref.delete.assert_called_once()
    db.collection("users").document.return_value.delete.assert_called_once()
