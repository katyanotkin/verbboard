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
# Collection / subcollection name constants
# ---------------------------------------------------------------------------


def test_collection_names_are_correct() -> None:
    assert repo.USER_PROGRESS_COLLECTION == "user_progress"
    assert repo.LANGUAGES_SUBCOLLECTION == "languages"
    assert repo.VERBS_SUBCOLLECTION == "verbs"
    assert repo.USER_PRACTICE_COLLECTION == "user_practice"


# ---------------------------------------------------------------------------
# _progress_language_ref  ->  user_progress/{uid}/languages/{lang}
# ---------------------------------------------------------------------------


def test_progress_language_ref_path() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo._progress_language_ref("u1", "en")

    db.collection.assert_called_with("user_progress")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("languages")
    db.collection().document().collection().document.assert_called_with("en")


# ---------------------------------------------------------------------------
# _progress_verb_ref  ->  user_progress/{uid}/languages/{lang}/verbs/{verb_id}
# ---------------------------------------------------------------------------


def test_progress_verb_ref_path() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo._progress_verb_ref("u1", "en", "en_go")

    db.collection.assert_called_with("user_progress")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("languages")
    db.collection().document().collection().document.assert_called_with("en")
    db.collection().document().collection().document().collection.assert_called_with(
        "verbs"
    )
    db.collection().document().collection().document().collection().document.assert_called_with(
        "en_go"
    )


# ---------------------------------------------------------------------------
# _practice_doc_ref path:  user_practice/{uid}/languages/{lang}
# ---------------------------------------------------------------------------


def test_practice_doc_ref_targets_subcollection() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo._practice_doc_ref("u1", "en")

    db.collection.assert_called_with("user_practice")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("languages")
    db.collection().document().collection().document.assert_called_with("en")


def test_practice_doc_ref_different_languages_use_same_user_doc() -> None:
    """Both 'en' and 'he' are nested under the same user document."""
    db_en = _make_db()
    db_he = _make_db()

    with patch.object(repo, "get_db", return_value=db_en):
        repo._practice_doc_ref("u1", "en")
    with patch.object(repo, "get_db", return_value=db_he):
        repo._practice_doc_ref("u1", "he")

    db_en.collection().document.assert_called_with("u1")
    db_he.collection().document.assert_called_with("u1")
    db_en.collection().document().collection().document.assert_called_with("en")
    db_he.collection().document().collection().document.assert_called_with("he")


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
    db.collection().document().collection().document().collection.assert_called_with(
        "verbs"
    )
    db.collection().document().collection().document().collection().document.assert_called_with(
        "en_go"
    )


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
    db.collection().document().collection().document().collection.assert_called_with(
        "verbs"
    )
    db.collection().document().collection().document().collection().document.assert_called_with(
        "en_go"
    )


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
    db.collection().document().collection().document().collection.assert_called_with(
        "verbs"
    )


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
