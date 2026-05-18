"""
Unit tests for core/progress/progress_repository.py

Verifies:
  - correct Firestore collection/subcollection names
  - user_progress/{uid}/verbs/{verb_id}  for seen/known
  - user_practice/{uid}/languages/{lang} for badges  (mirrors user_progress pattern)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from core.progress import progress_repository as repo
from core.progress.models import PracticeProgress, VerbProgress


def _make_db():
    return MagicMock()


# ---------------------------------------------------------------------------
# Collection / subcollection name constants
# ---------------------------------------------------------------------------


def test_collection_names_are_correct() -> None:
    assert repo.USER_PROGRESS_COLLECTION == "user_progress"
    assert repo.VERBS_SUBCOLLECTION == "verbs"
    assert repo.USER_PRACTICE_COLLECTION == "user_practice"
    assert repo.LANGUAGES_SUBCOLLECTION == "languages"


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

    # Both calls target document("u1") -- same user doc, different language docs
    db_en.collection().document.assert_called_with("u1")
    db_he.collection().document.assert_called_with("u1")
    db_en.collection().document().collection().document.assert_called_with("en")
    db_he.collection().document().collection().document.assert_called_with("he")


# ---------------------------------------------------------------------------
# mark_seen  ->  user_progress/{uid}/verbs/{verb_id}
# ---------------------------------------------------------------------------


def test_mark_seen_targets_correct_path() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo.mark_seen(user_id="u1", language="en", verb_id="en_go")

    db.collection.assert_called_with("user_progress")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("verbs")
    db.collection().document().collection().document.assert_called_with("en_go")


def test_mark_seen_payload() -> None:
    db = _make_db()
    doc_ref = db.collection().document().collection().document()

    with patch.object(repo, "get_db", return_value=db):
        repo.mark_seen(user_id="u1", language="en", verb_id="en_go")

    args, kwargs = doc_ref.set.call_args
    payload = args[0]
    assert payload["seen"] is True
    assert payload["language"] == "en"
    assert payload["verb_id"] == "en_go"
    assert kwargs.get("merge") is True


# ---------------------------------------------------------------------------
# set_known  ->  user_progress/{uid}/verbs/{verb_id}
# ---------------------------------------------------------------------------


def test_set_known_targets_correct_path() -> None:
    db = _make_db()

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=True)

    db.collection.assert_called_with("user_progress")
    db.collection().document().collection().document.assert_called_with("en_go")


def test_set_known_payload_reflects_value() -> None:
    db = _make_db()
    doc_ref = db.collection().document().collection().document()

    with patch.object(repo, "get_db", return_value=db):
        repo.set_known(user_id="u1", language="en", verb_id="en_go", known=False)

    args, _ = doc_ref.set.call_args
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
    doc_ref = db.collection().document().collection().document()

    with patch.object(repo, "get_db", return_value=db):
        repo.save_practice_progress(user_id="u1", language="en", badges=[3, 6, 9])

    args, kwargs = doc_ref.set.call_args
    payload = args[0]
    assert payload["badges"] == [3, 6, 9]
    assert payload["language"] == "en"
    assert kwargs.get("merge") is True


# ---------------------------------------------------------------------------
# get_practice_progress  ->  user_practice/{uid}/languages/{lang}
# ---------------------------------------------------------------------------


def test_get_practice_targets_correct_path() -> None:
    db = _make_db()
    db.collection().document().collection().document().get().to_dict.return_value = {}

    with patch.object(repo, "get_db", return_value=db):
        repo.get_practice_progress(user_id="u1", language="he")

    db.collection.assert_called_with("user_practice")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("languages")
    db.collection().document().collection().document.assert_called_with("he")


def test_get_practice_returns_model() -> None:
    db = _make_db()
    db.collection().document().collection().document().get().to_dict.return_value = {
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
    db.collection().document().collection().document().get().to_dict.return_value = {}

    with patch.object(repo, "get_db", return_value=db):
        result = repo.get_practice_progress(user_id="u1", language="en")

    assert result.badges == []


# ---------------------------------------------------------------------------
# list_progress_for_language  ->  user_progress/{uid}/verbs (language filter)
# ---------------------------------------------------------------------------


def test_list_progress_queries_correct_path() -> None:
    db = _make_db()
    db.collection().document().collection().where().stream.return_value = iter([])

    with patch.object(repo, "get_db", return_value=db):
        repo.list_progress_for_language(user_id="u1", language="en")

    db.collection.assert_called_with("user_progress")
    db.collection().document.assert_called_with("u1")
    db.collection().document().collection.assert_called_with("verbs")


def test_list_progress_returns_verb_progress_models() -> None:
    db = _make_db()
    fake_doc = MagicMock()
    fake_doc.to_dict.return_value = {
        "language": "en",
        "verb_id": "en_go",
        "seen": True,
        "known": False,
    }
    db.collection().document().collection().where().stream.return_value = iter(
        [fake_doc]
    )

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
    db.collection().document().collection().where().stream.return_value = iter(
        [bad_doc]
    )

    with patch.object(repo, "get_db", return_value=db):
        results = repo.list_progress_for_language(user_id="u1", language="en")

    assert results == []
