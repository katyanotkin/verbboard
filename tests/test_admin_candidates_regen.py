"""
Tests for POST /admin/api/candidates/{verb_id}/examples/{index}/regen
and the learn.py return_to default for source=candidate.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _admin_cookies() -> dict[str, str]:
    return {ADMIN_SESSION_COOKIE: create_admin_session_token()}


def _mock_db(verb_id: str, data: dict | None) -> MagicMock:
    """Return a mock Firestore db whose candidate document resolves to data."""
    mock_doc = MagicMock()
    mock_doc.exists = data is not None
    mock_doc.to_dict.return_value = data or {}

    mock_ref = MagicMock()
    mock_ref.get.return_value = mock_doc
    mock_ref.update = MagicMock()

    mock_collection = MagicMock()
    mock_collection.document.return_value = mock_ref

    mock_db = MagicMock()
    mock_db.collection.return_value = mock_collection
    return mock_db


_CANDIDATE = {
    "verb_id": "en_go",
    "language": "en",
    "lemma": "go",
    "status": "pending",
    "examples": [
        {"src": "I go to school.", "dst": "I go to school."},
        {"src": "She goes home.", "dst": "She goes home."},
    ],
}

_NEW_EXAMPLE = {"src": "We go together.", "dst": "We go together."}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_regen_example_happy_path(client: TestClient) -> None:
    db = _mock_db("en_go", _CANDIDATE)

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch(
            "app.routes.admin_candidates._call_claude_single_example",
            new=AsyncMock(return_value=_NEW_EXAMPLE),
        ),
        patch(
            "app.routes.admin_candidates.translate_examples",
            return_value=[_NEW_EXAMPLE],
        ),
    ):
        resp = client.post(
            "/admin/api/candidates/en_go/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["index"] == 0
    assert body["example"] == _NEW_EXAMPLE
    assert "updated_at" in body
    db.collection.return_value.document.return_value.update.assert_called_once()


# ---------------------------------------------------------------------------
# Candidate not found -> 404
# ---------------------------------------------------------------------------


def test_regen_example_candidate_not_found(client: TestClient) -> None:
    db = _mock_db("en_missing", None)

    with patch("app.routes.admin_candidates.get_db", return_value=db):
        resp = client.post(
            "/admin/api/candidates/en_missing/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Index out of range -> 400
# ---------------------------------------------------------------------------


def test_regen_example_index_too_large(client: TestClient) -> None:
    db = _mock_db("en_go", _CANDIDATE)

    with patch("app.routes.admin_candidates.get_db", return_value=db):
        resp = client.post(
            "/admin/api/candidates/en_go/examples/99/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 400
    assert "out of range" in resp.json()["detail"]


def test_regen_example_negative_index_rejected(client: TestClient) -> None:
    # FastAPI path matching doesn't bind negative ints -- returns 404
    resp = client.post(
        "/admin/api/candidates/en_go/examples/-1/regen",
        cookies=_admin_cookies(),
    )
    assert resp.status_code in (400, 404, 422)


# ---------------------------------------------------------------------------
# Unauthenticated -> 401
# ---------------------------------------------------------------------------


def test_regen_example_requires_auth(client: TestClient) -> None:
    resp = client.post("/admin/api/candidates/en_go/examples/0/regen")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Claude failure propagates as 502
# ---------------------------------------------------------------------------


def test_regen_example_propagates_502_from_claude(client: TestClient) -> None:
    db = _mock_db("en_go", _CANDIDATE)

    async def _raise(*a, **kw):
        raise HTTPException(
            status_code=502, detail="Example generation returned invalid JSON"
        )

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch(
            "app.routes.admin_candidates._call_claude_single_example",
            new=_raise,
        ),
    ):
        resp = client.post(
            "/admin/api/candidates/en_go/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 502
    assert "invalid JSON" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# learn.py: return_to defaults to /admin#candidates when source=candidate
# ---------------------------------------------------------------------------


def _stub_render(**kwargs) -> str:
    return "<html><body>board</body></html>"


def test_learn_candidate_return_to_defaults_to_admin(
    client: TestClient, monkeypatch, mock_verb
) -> None:
    """When source=candidate and no return_to param is given, render_board_html
    must receive return_to='/admin#candidates'."""
    captured = {}

    def _capturing_render(**kwargs):
        captured["return_to"] = kwargs.get("return_to")
        return "<html><body>board</body></html>"

    monkeypatch.setattr("app.routes.learn.load_entry_by_id", lambda **kw: mock_verb)
    monkeypatch.setattr(
        "app.routes.learn.ensure_audio",
        __import__("tests.conftest", fromlist=["noop_ensure_audio"]).noop_ensure_audio,
    )
    monkeypatch.setattr("app.routes.learn.render_board_html", _capturing_render)

    resp = client.get("/learn?language=en&verb_id=en_go&source=candidate")

    assert resp.status_code == 200
    assert captured.get("return_to") == "/admin#candidates"


def test_learn_candidate_explicit_return_to_is_respected(
    client: TestClient, monkeypatch, mock_verb
) -> None:
    """An explicit return_to query param must override the default."""
    captured = {}

    def _capturing_render(**kwargs):
        captured["return_to"] = kwargs.get("return_to")
        return "<html><body>board</body></html>"

    monkeypatch.setattr("app.routes.learn.load_entry_by_id", lambda **kw: mock_verb)
    monkeypatch.setattr(
        "app.routes.learn.ensure_audio",
        __import__("tests.conftest", fromlist=["noop_ensure_audio"]).noop_ensure_audio,
    )
    monkeypatch.setattr("app.routes.learn.render_board_html", _capturing_render)

    resp = client.get(
        "/learn?language=en&verb_id=en_go&source=candidate&return_to=/custom"
    )

    assert resp.status_code == 200
    assert captured.get("return_to") == "/custom"
