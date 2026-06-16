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
        raise HTTPException(status_code=502, detail="Example generation returned invalid JSON")

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
# translate_examples is called with regen-format example (src+dst)
# ---------------------------------------------------------------------------


def test_regen_endpoint_passes_native_sentence_to_translate_examples(
    client: TestClient,
) -> None:
    """translate_examples must receive {"dst": native_sentence}, not the raw
    regen-format example.  The native sentence is ex["src"] for regen-format examples.
    """
    db = _mock_db("en_go", _CANDIDATE)
    regen_example = {"src": "Мы идём вместе.", "dst": "We go together."}
    translate_calls: list[dict] = []

    def _capturing_translate(**kwargs):
        translate_calls.append({"examples": list(kwargs.get("examples", []))})
        return kwargs.get("examples", [])

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch(
            "app.routes.admin_candidates._call_claude_single_example",
            new=AsyncMock(return_value=regen_example),
        ),
        patch(
            "app.routes.admin_candidates.translate_examples",
            side_effect=_capturing_translate,
        ),
    ):
        resp = client.post(
            "/admin/api/candidates/en_go/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 200
    assert len(translate_calls) == 1
    passed_examples = translate_calls[0]["examples"]
    assert len(passed_examples) == 1
    # translate_examples must receive {"dst": native_sentence}, using src from regen example
    assert passed_examples[0] == {"dst": "Мы идём вместе."}
    assert passed_examples[0]["dst"] == "Мы идём вместе."  # native sentence, not English


# ---------------------------------------------------------------------------
# translate_examples result is merged into the returned example
# ---------------------------------------------------------------------------


def test_regen_endpoint_merges_translations_into_returned_example(
    client: TestClient,
) -> None:
    """When translate_examples returns an example enriched with a translations dict,
    the endpoint must return that enriched example (not the bare regen result).
    """
    db = _mock_db("en_go", _CANDIDATE)
    raw_example = {"src": "I go to the store.", "dst": "I go to the store."}
    translated_example = {
        "src": "I go to the store.",
        "dst": "I go to the store.",
        "translations": {"ru": "Я иду в магазин.", "es": "Voy a la tienda."},
    }

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch(
            "app.routes.admin_candidates._call_claude_single_example",
            new=AsyncMock(return_value=raw_example),
        ),
        patch(
            "app.routes.admin_candidates.translate_examples",
            return_value=[translated_example],
        ),
    ):
        resp = client.post(
            "/admin/api/candidates/en_go/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 200
    body = resp.json()
    returned = body["example"]
    assert "translations" in returned, (
        "translations dict from translate_examples must be present in the returned example"
    )
    assert returned["translations"]["ru"] == "Я иду в магазин."
    assert returned["translations"]["es"] == "Voy a la tienda."


def test_regen_endpoint_returns_raw_example_when_translate_returns_same_list(
    client: TestClient,
) -> None:
    """When translate_examples returns the identical list object (no translations
    added), the endpoint must still return the original example unchanged.
    """
    db = _mock_db("en_go", _CANDIDATE)
    raw_example = {"src": "I go to the store.", "dst": "I go to the store."}

    def _identity(**kwargs):
        # Simulate translate_examples returning the same list unchanged
        return kwargs["examples"]

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch(
            "app.routes.admin_candidates._call_claude_single_example",
            new=AsyncMock(return_value=raw_example),
        ),
        patch(
            "app.routes.admin_candidates.translate_examples",
            side_effect=_identity,
        ),
    ):
        resp = client.post(
            "/admin/api/candidates/en_go/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["example"]["src"] == raw_example["src"]
    assert body["example"]["dst"] == raw_example["dst"]


# ---------------------------------------------------------------------------
# Empty lemma in candidate (never generated)
# ---------------------------------------------------------------------------


def test_regen_example_rejects_empty_lemma_with_422(client: TestClient) -> None:
    """A candidate that was never generated has lemma=''.
    The endpoint must reject it with 422 rather than sending a malformed prompt to Claude.
    """
    candidate_no_lemma = {
        "verb_id": "ru_unknown",
        "language": "ru",
        "lemma": "",  # blank -- never generated
        "status": "needs_generation",
        "examples": [{"dst": "placeholder"}],
    }
    db = _mock_db("ru_unknown", candidate_no_lemma)

    with patch("app.routes.admin_candidates.get_db", return_value=db):
        resp = client.post(
            "/admin/api/candidates/ru_unknown/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 422
    assert "lemma" in resp.json()["detail"]


def test_regen_example_empty_examples_list_returns_400(client: TestClient) -> None:
    """A candidate with an empty examples list must cause a 400 for any index,
    since the range check fires (index 0 >= len([]) = 0).
    """
    candidate_empty_examples = {
        "verb_id": "en_empty",
        "language": "en",
        "lemma": "go",
        "status": "pending",
        "examples": [],
    }
    db = _mock_db("en_empty", candidate_empty_examples)

    with patch("app.routes.admin_candidates.get_db", return_value=db):
        resp = client.post(
            "/admin/api/candidates/en_empty/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 400
    assert "out of range" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# translate_examples is called with the correct verb_lang and lemma
# ---------------------------------------------------------------------------


def test_regen_endpoint_passes_correct_lang_and_lemma_to_translate_examples(
    client: TestClient,
) -> None:
    """translate_examples must receive verb_lang and lemma from the candidate doc,
    not hardcoded values.
    """
    candidate = {
        "verb_id": "ru_idti",
        "language": "ru",
        "lemma": "идти",
        "status": "pending",
        "examples": [{"dst": "Я иду домой."}],
    }
    db = _mock_db("ru_idti", candidate)
    new_ex = {"src": "Мы идём.", "dst": "We go."}
    translate_kwargs: list[dict] = []

    def _capture(**kwargs):
        translate_kwargs.append(kwargs)
        return [new_ex]

    with (
        patch("app.routes.admin_candidates.get_db", return_value=db),
        patch(
            "app.routes.admin_candidates._call_claude_single_example",
            new=AsyncMock(return_value=new_ex),
        ),
        patch(
            "app.routes.admin_candidates.translate_examples",
            side_effect=_capture,
        ),
    ):
        resp = client.post(
            "/admin/api/candidates/ru_idti/examples/0/regen",
            cookies=_admin_cookies(),
        )

    assert resp.status_code == 200
    assert len(translate_kwargs) == 1
    assert translate_kwargs[0]["verb_lang"] == "ru"
    assert translate_kwargs[0]["lemma"] == "идти"


# ---------------------------------------------------------------------------
# learn.py: return_to defaults to /admin#candidates when source=candidate
# ---------------------------------------------------------------------------


def _stub_render(**kwargs) -> str:
    return "<html><body>board</body></html>"


def test_learn_candidate_return_to_defaults_to_admin(client: TestClient, monkeypatch, mock_verb) -> None:
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


def test_learn_candidate_explicit_return_to_is_respected(client: TestClient, monkeypatch, mock_verb) -> None:
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

    resp = client.get("/learn?language=en&verb_id=en_go&source=candidate&return_to=/custom")

    assert resp.status_code == 200
    assert captured.get("return_to") == "/custom"
