from __future__ import annotations

from fastapi.testclient import TestClient

from core.models import VerbEntry
from tests.conftest import noop_ensure_audio


def _stub_render(**kwargs) -> str:
    return "<html><body>board</body></html>"


def test_learn_default_verb_returns_200(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    monkeypatch.setattr(
        "app.routes.learn.load_entries_for_language",
        lambda **kw: [mock_verb],
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)
    monkeypatch.setattr("app.routes.learn.render_board_html", _stub_render)

    response = client.get("/learn?language=en")
    assert response.status_code == 200


def test_learn_valid_verb_id_returns_200(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    monkeypatch.setattr(
        "app.routes.learn.load_entries_for_language",
        lambda **kw: [mock_verb],
    )
    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: mock_verb,
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)
    monkeypatch.setattr("app.routes.learn.render_board_html", _stub_render)

    response = client.get("/learn?language=en&verb_id=en_go")
    assert response.status_code == 200


def test_learn_unknown_verb_id_returns_404(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    monkeypatch.setattr(
        "app.routes.learn.load_entries_for_language",
        lambda **kw: [mock_verb],
    )
    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: None,
    )

    response = client.get("/learn?language=en&verb_id=en_nosuchverb")
    assert response.status_code == 404


def test_learn_no_verbs_available_returns_400(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.learn.load_entries_for_language",
        lambda **kw: [],
    )

    response = client.get("/learn?language=en")
    assert response.status_code == 400


def test_learn_candidate_preview_returns_200(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    monkeypatch.setattr("app.routes.learn.read_session_claims", lambda request: {"role": "admin"})
    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: mock_verb,
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)
    monkeypatch.setattr("app.routes.learn.render_board_html", _stub_render)

    response = client.get("/learn?language=en&verb_id=en_go&source=candidate")
    assert response.status_code == 200


def test_learn_candidate_not_found_returns_404(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.learn.read_session_claims", lambda request: {"role": "admin"})
    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: None,
    )

    response = client.get("/learn?language=en&verb_id=missing&source=candidate")
    assert response.status_code == 404


def test_learn_candidate_missing_verb_id_returns_400(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.routes.learn.read_session_claims", lambda request: {"role": "admin"})
    response = client.get("/learn?language=en&source=candidate")
    assert response.status_code == 400


def test_learn_candidate_is_hidden_from_anonymous_visitors(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
    """Unpublished candidates are an admin preview (issue #85)."""
    monkeypatch.setattr("app.routes.learn.load_entry_by_id", lambda **kw: mock_verb)
    response = client.get("/learn?language=en&verb_id=en_go&source=candidate")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/learn/form_signal hardening (issue #77)
# ---------------------------------------------------------------------------


def _form_signal_calls(monkeypatch) -> list[dict]:
    calls: list[dict] = []
    monkeypatch.setattr("app.routes.learn.log_missing_verb_search", lambda **kw: calls.append(kw))
    return calls


def test_form_signal_valid_call_logs(client, monkeypatch) -> None:
    calls = _form_signal_calls(monkeypatch)
    response = client.post(
        "/api/learn/form_signal", json={"language": "es", "verb_id": "es_correr", "form_text": "corro"}
    )
    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["language"] == "es"
    assert calls[0]["query"] == "corro"


def test_form_signal_unknown_language_400(client, monkeypatch) -> None:
    calls = _form_signal_calls(monkeypatch)
    response = client.post("/api/learn/form_signal", json={"language": "xx", "form_text": "corro"})
    assert response.status_code == 400
    assert calls == []


def test_form_signal_oversize_form_text_422(client, monkeypatch) -> None:
    calls = _form_signal_calls(monkeypatch)
    response = client.post("/api/learn/form_signal", json={"language": "es", "form_text": "x" * 101})
    assert response.status_code == 422
    assert calls == []


def test_form_signal_rate_limited_after_30(client, monkeypatch) -> None:
    calls = _form_signal_calls(monkeypatch)
    body = {"language": "es", "form_text": "corro"}
    statuses = [client.post("/api/learn/form_signal", json=body).status_code for _ in range(31)]
    assert statuses[:30] == [200] * 30
    assert statuses[30] == 429
    assert len(calls) == 30
