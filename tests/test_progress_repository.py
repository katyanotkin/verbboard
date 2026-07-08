"""
Unit tests for core/progress/progress_repository.py

Structure under test:
  user_progress/{uid}/languages/{lang}             <- language container {language}
  user_progress/{uid}/languages/{lang}/verbs/{vid} <- verb progress
  user_practice/{uid}/languages/{lang}             <- practice badges
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.progress import progress_repository as repo
from core.progress.models import PracticeProgress, VerbProgress


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


# ---------------------------------------------------------------------------
# Practice streak: _read_streak, get_practice_progress, save_practice_progress
# ---------------------------------------------------------------------------


def test_read_streak_returns_none_when_absent() -> None:
    assert repo._read_streak({}) is None


def test_read_streak_returns_none_when_last_day_missing() -> None:
    assert repo._read_streak({"streak_len": 5}) is None


def test_read_streak_returns_none_when_len_below_one() -> None:
    assert repo._read_streak({"streak_last_day": "2026-07-08", "streak_len": 0}) is None


def test_read_streak_degrades_non_numeric_len_to_none_without_raising() -> None:
    """Garbage streak_len (e.g. a stray string) must degrade to 'no streak'
    rather than raise, so a corrupted doc doesn't break GET/POST /practice."""
    payload = {"streak_last_day": "2026-07-08", "streak_len": "not-a-number"}

    result = repo._read_streak(payload)

    assert result is None


def test_read_streak_valid_payload() -> None:
    result = repo._read_streak({"streak_last_day": "2026-07-08", "streak_len": 5})

    assert result == {"last_day": "2026-07-08", "len": 5}


def test_get_practice_progress_legacy_doc_defaults_streak_fields() -> None:
    """A doc written before the streak feature existed has no streak_* fields;
    GET must degrade to None/0, not raise."""
    db = _make_db()
    _lang_ref(db).get().to_dict.return_value = {"badges": [3], "language": "en"}

    with patch.object(repo, "get_db", return_value=db):
        result = repo.get_practice_progress(user_id="u1", language="en")

    assert result.streak_last_day is None
    assert result.streak_len == 0


def test_get_practice_progress_returns_stored_streak() -> None:
    db = _make_db()
    _lang_ref(db).get().to_dict.return_value = {
        "badges": [3],
        "language": "en",
        "streak_last_day": "2026-07-08",
        "streak_len": 4,
    }

    with patch.object(repo, "get_db", return_value=db):
        result = repo.get_practice_progress(user_id="u1", language="en")

    assert result.streak_last_day == "2026-07-08"
    assert result.streak_len == 4


def test_get_practice_progress_garbage_streak_len_does_not_raise() -> None:
    db = _make_db()
    _lang_ref(db).get().to_dict.return_value = {
        "badges": [3],
        "language": "en",
        "streak_last_day": "2026-07-08",
        "streak_len": {"unexpected": "shape"},
    }

    with patch.object(repo, "get_db", return_value=db):
        result = repo.get_practice_progress(user_id="u1", language="en")

    assert result.streak_last_day is None
    assert result.streak_len == 0


def test_save_practice_progress_writes_streak_fields_to_doc() -> None:
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = False
    snapshot.to_dict.return_value = {}
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        repo.save_practice_progress(
            user_id="u1",
            language="en",
            badges=[3],
            streak_last_day="2026-07-08",
            streak_len=5,
        )

    args, kwargs = doc_ref.set.call_args
    payload = args[0]
    assert payload["streak_last_day"] == "2026-07-08"
    assert payload["streak_len"] == 5
    assert kwargs.get("merge") is True


def test_save_practice_progress_merges_against_existing_stored_streak() -> None:
    """An adjacent-day incoming streak must be merged with what's already
    stored (not simply overwritten with the incoming value)."""
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "badges": [3],
        "language": "en",
        "streak_last_day": "2026-07-07",
        "streak_len": 5,
    }
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        result = repo.save_practice_progress(
            user_id="u1",
            language="en",
            badges=[3],
            streak_last_day="2026-07-08",
            streak_len=1,
        )

    # Adjacent day: merged length is max(incoming.len, stored.len + 1) = max(1, 6) = 6.
    assert result == {"last_day": "2026-07-08", "len": 6}

    args, _ = doc_ref.set.call_args
    payload = args[0]
    assert payload["streak_last_day"] == "2026-07-08"
    assert payload["streak_len"] == 6


def test_save_practice_progress_stale_incoming_does_not_shrink_stored_streak() -> None:
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "badges": [3],
        "language": "en",
        "streak_last_day": "2026-07-08",
        "streak_len": 50,
    }
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        result = repo.save_practice_progress(
            user_id="u1",
            language="en",
            badges=[3],
            streak_last_day="2026-01-01",
            streak_len=1,
        )

    assert result == {"last_day": "2026-07-08", "len": 50}

    args, _ = doc_ref.set.call_args
    payload = args[0]
    assert payload["streak_last_day"] == "2026-07-08"
    assert payload["streak_len"] == 50


def test_save_practice_progress_without_streak_args_returns_existing_streak_unchanged() -> None:
    """Calling save_practice_progress with no streak_last_day/streak_len must
    leave the stored streak untouched and return it as-is (badge-only save)."""
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {
        "badges": [3],
        "language": "en",
        "streak_last_day": "2026-07-08",
        "streak_len": 7,
    }
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        result = repo.save_practice_progress(user_id="u1", language="en", badges=[3, 6])

    assert result == {"last_day": "2026-07-08", "len": 7}

    args, _ = doc_ref.set.call_args
    payload = args[0]
    assert "streak_last_day" not in payload
    assert "streak_len" not in payload


def test_save_practice_progress_no_streak_args_and_no_existing_streak_returns_none() -> None:
    db = _make_db()
    doc_ref = _lang_ref(db)

    snapshot = MagicMock()
    snapshot.exists = True
    snapshot.to_dict.return_value = {"badges": [3], "language": "en"}
    doc_ref.get.return_value = snapshot

    with patch.object(repo, "get_db", return_value=db):
        result = repo.save_practice_progress(user_id="u1", language="en", badges=[3])

    assert result is None
