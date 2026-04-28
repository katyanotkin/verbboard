from __future__ import annotations

from fastapi.testclient import TestClient

from core.models import VerbEntry
from tests.conftest import noop_ensure_audio


def _stub_render(**kwargs) -> str:
    return "<html><body>board</body></html>"


def test_learn_default_verb_returns_200(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
    monkeypatch.setattr(
        "app.routes.learn.load_entries_for_language",
        lambda **kw: [mock_verb],
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)
    monkeypatch.setattr("app.routes.learn.render_board_html", _stub_render)

    response = client.get("/learn?language=en")
    assert response.status_code == 200


def test_learn_valid_verb_id_returns_200(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
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


def test_learn_unknown_verb_id_returns_404(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
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


def test_learn_candidate_preview_returns_200(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: mock_verb,
    )
    monkeypatch.setattr("app.routes.learn.ensure_audio", noop_ensure_audio)
    monkeypatch.setattr("app.routes.learn.render_board_html", _stub_render)

    response = client.get("/learn?language=en&verb_id=en_go&source=candidate")
    assert response.status_code == 200


def test_learn_candidate_not_found_returns_404(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.learn.load_entry_by_id",
        lambda **kw: None,
    )

    response = client.get("/learn?language=en&verb_id=missing&source=candidate")
    assert response.status_code == 404


def test_learn_candidate_missing_verb_id_returns_400(
    client: TestClient,
) -> None:
    response = client.get("/learn?language=en&source=candidate")
    assert response.status_code == 400
