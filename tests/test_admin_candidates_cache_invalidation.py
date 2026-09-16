"""Tests that invalidate_entries_cache(language) is called from the 4 admin
verb-mutation endpoints in app/routes/admin_candidates.py:

- POST /admin/api/candidates/{verb_id}/promote   (promote_candidate)
- POST /admin/api/verbs/{verb_id}/regenerate      (regenerate_verb)
- POST /admin/api/verbs/{verb_id}/regen_examples  (regen_verb_examples)
- POST /admin/api/verbs/{verb_id}/regen_forms     (regen_verb_forms)

load_entries_for_language caches verb entries for 5 minutes (core/verb_loader.py);
without this call an admin edit wouldn't be visible on /verbs or /learn until the
cache naturally expired.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token
from core.settings import verb_candidates_collection_name, verbs_collection_name


def _admin_cookies() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


def _mock_live_verb_db(verb_id: str, data: dict | None) -> MagicMock:
    mock_doc = MagicMock()
    mock_doc.exists = data is not None
    mock_doc.to_dict.return_value = data or {}

    mock_ref = MagicMock()
    mock_ref.get.return_value = mock_doc
    mock_ref.update = MagicMock()
    mock_ref.set = MagicMock()

    mock_col = MagicMock()
    mock_col.document.return_value = mock_ref

    mock_db = MagicMock()
    mock_db.collection.return_value = mock_col
    return mock_db


def _mock_promote_db(candidate_data: dict, *, live_exists: bool = False) -> MagicMock:
    """A db mock that distinguishes the candidates collection from the verbs
    collection -- promote_candidate reads/writes both."""
    candidate_doc = MagicMock()
    candidate_doc.exists = True
    candidate_doc.to_dict.return_value = candidate_data

    candidate_ref = MagicMock()
    candidate_ref.get.return_value = candidate_doc
    candidate_ref.update = MagicMock()

    live_doc = MagicMock()
    live_doc.exists = live_exists
    live_ref = MagicMock()
    live_ref.get.return_value = live_doc
    live_ref.set = MagicMock()

    def _collection(name: str) -> MagicMock:
        col = MagicMock()
        if name == verb_candidates_collection_name():
            col.document.return_value = candidate_ref
        elif name == verbs_collection_name():
            col.document.return_value = live_ref
        else:
            col.document.return_value = MagicMock()
        return col

    db = MagicMock()
    db.collection.side_effect = _collection
    return db


# ---------------------------------------------------------------------------
# promote_candidate
# ---------------------------------------------------------------------------


def test_promote_candidate_invalidates_entries_cache(client: TestClient) -> None:
    candidate_data = {
        "verb_id": "en_go",
        "language": "en",
        "lemma": "go",
        "status": "pending",
        "query": "go",
        "examples": [{"dst": "I go."}],
        "rank": 5,
    }
    db = _mock_promote_db(candidate_data, live_exists=False)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates.translate_examples", side_effect=lambda **kw: kw["examples"]),
        patch("app.routes.admin_candidates.translate_lemma", return_value={}),
        patch("app.routes.admin_candidates.resolve_signal_label"),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/candidates/en_go/promote", cookies=_admin_cookies())

    assert resp.status_code == 200
    mock_invalidate.assert_called_once_with("en")


def test_promote_candidate_does_not_invalidate_cache_on_duplicate(client: TestClient) -> None:
    """If promotion fails (409, already live), the cache must not be touched."""
    candidate_data = {
        "verb_id": "en_go",
        "language": "en",
        "lemma": "go",
        "status": "pending",
        "query": "go",
        "examples": [],
    }
    db = _mock_promote_db(candidate_data, live_exists=True)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/candidates/en_go/promote", cookies=_admin_cookies())

    assert resp.status_code == 409
    mock_invalidate.assert_not_called()


# ---------------------------------------------------------------------------
# regenerate_verb
# ---------------------------------------------------------------------------


def test_regenerate_verb_invalidates_entries_cache(client: TestClient) -> None:
    live_verb = {
        "verb_id": "en_go",
        "language": "en",
        "lemma": "go",
        "rank": 3,
        "forms": {"base": "go"},
        "examples": [{"dst": "I go."}],
    }
    db = _mock_live_verb_db("en_go", live_verb)
    generated = {"lemma": "go", "forms": {"base": "go"}, "examples": [{"dst": "I go."}]}

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates._call_claude", new=AsyncMock(return_value=generated)),
        patch("app.routes.admin_candidates.translate_examples", side_effect=lambda **kw: kw["examples"]),
        patch("app.routes.admin_candidates.translate_lemma", return_value={}),
        patch("app.routes.admin_candidates._warm_verb_audio", new=AsyncMock()),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/verbs/en_go/regenerate", cookies=_admin_cookies())

    assert resp.status_code == 200
    mock_invalidate.assert_called_once_with("en")


def test_regenerate_verb_not_found_does_not_invalidate_cache(client: TestClient) -> None:
    db = _mock_live_verb_db("en_missing", None)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/verbs/en_missing/regenerate", cookies=_admin_cookies())

    assert resp.status_code == 404
    mock_invalidate.assert_not_called()


# ---------------------------------------------------------------------------
# regen_verb_examples
# ---------------------------------------------------------------------------


def test_regen_verb_examples_invalidates_entries_cache(client: TestClient) -> None:
    live_verb = {"verb_id": "en_go", "language": "en", "lemma": "go", "examples": [{"dst": "old"}]}
    db = _mock_live_verb_db("en_go", live_verb)
    generated = {"lemma": "go", "examples": [{"dst": "new"}]}

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates._call_claude", new=AsyncMock(return_value=generated)),
        patch("app.routes.admin_candidates.translate_examples", side_effect=lambda **kw: kw["examples"]),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/verbs/en_go/regen_examples", cookies=_admin_cookies())

    assert resp.status_code == 200
    mock_invalidate.assert_called_once_with("en")


def test_regen_verb_examples_not_found_does_not_invalidate_cache(client: TestClient) -> None:
    db = _mock_live_verb_db("en_missing", None)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/verbs/en_missing/regen_examples", cookies=_admin_cookies())

    assert resp.status_code == 404
    mock_invalidate.assert_not_called()


# ---------------------------------------------------------------------------
# regen_verb_forms
# ---------------------------------------------------------------------------


def test_regen_verb_forms_invalidates_entries_cache(client: TestClient) -> None:
    live_verb = {"verb_id": "en_go", "language": "en", "lemma": "go", "forms": {"base": "go"}}
    db = _mock_live_verb_db("en_go", live_verb)
    generated = {"lemma": "go", "forms": {"base": "goes"}, "examples": []}

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates._call_claude", new=AsyncMock(return_value=generated)),
        patch("app.routes.admin_candidates._warm_verb_audio", new=AsyncMock()),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/verbs/en_go/regen_forms", cookies=_admin_cookies())

    assert resp.status_code == 200
    mock_invalidate.assert_called_once_with("en")


def test_regen_verb_forms_not_found_does_not_invalidate_cache(client: TestClient) -> None:
    db = _mock_live_verb_db("en_missing", None)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch("app.routes.admin_candidates.invalidate_entries_cache") as mock_invalidate,
    ):
        resp = client.post("/admin/api/verbs/en_missing/regen_forms", cookies=_admin_cookies())

    assert resp.status_code == 404
    mock_invalidate.assert_not_called()
