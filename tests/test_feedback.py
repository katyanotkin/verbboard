from __future__ import annotations

from fastapi.testclient import TestClient


def test_feedback_get_returns_form(client: TestClient) -> None:
    response = client.get("/feedback")
    assert response.status_code == 200
    assert "<form" in response.text
    assert "Feedback" in response.text


def test_feedback_get_shows_poll_question(client: TestClient) -> None:
    response = client.get("/feedback?language=en")
    assert response.status_code == 200
    # ACTIVE_POLL_ID is set, so a poll block should appear
    assert "poll_answer" in response.text


def test_feedback_get_success_flag_shows_confirmation(client: TestClient) -> None:
    response = client.get("/feedback?success=1")
    assert "Thanks" in response.text


def test_feedback_get_error_flag_shows_error(client: TestClient) -> None:
    response = client.get("/feedback?error=empty")
    assert "comment" in response.text.lower() or "Yes/No" in response.text


def test_feedback_submit_comment_calls_save_and_redirects(
    client: TestClient, monkeypatch
) -> None:
    saved: list[dict] = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return "doc-123"

    monkeypatch.setattr("app.routes.feedback.save_feedback", fake_save)

    response = client.post(
        "/feedback",
        data={"comment": "Really useful app!", "return_to": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert len(saved) == 1
    assert saved[0]["comment"] == "Really useful app!"


def test_feedback_submit_poll_answer_saved(client: TestClient, monkeypatch) -> None:
    saved: list[dict] = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return "doc-456"

    monkeypatch.setattr("app.routes.feedback.save_feedback", fake_save)

    response = client.post(
        "/feedback",
        data={"poll_answer": "yes", "return_to": "/"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert saved[0]["poll_answer"] == "yes"


def test_feedback_submit_empty_redirects_with_error(client: TestClient) -> None:
    # save_feedback raises ValueError before any Firestore call when both fields empty
    response = client.post(
        "/feedback",
        data={"comment": "", "poll_answer": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=empty" in response.headers["location"]


def test_feedback_submit_invalid_poll_answer_treated_as_empty(
    client: TestClient, monkeypatch
) -> None:
    """An unrecognized poll_answer value is discarded; without a comment it errors."""
    response = client.post(
        "/feedback",
        data={"comment": "", "poll_answer": "maybe"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=empty" in response.headers["location"]


def test_feedback_submit_detects_mobile_device(client: TestClient, monkeypatch) -> None:
    saved: list[dict] = []

    def fake_save(**kwargs):
        saved.append(kwargs)
        return "doc-789"

    monkeypatch.setattr("app.routes.feedback.save_feedback", fake_save)

    mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148"
    response = client.post(
        "/feedback",
        data={"comment": "sent from phone", "return_to": "/"},
        headers={"User-Agent": mobile_ua},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert saved[0]["device_type"] == "mobile"


def test_feedback_submit_redirects_to_return_to(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.routes.feedback.save_feedback",
        lambda **kw: "doc-000",
    )

    response = client.post(
        "/feedback",
        data={"comment": "good", "return_to": "/learn?language=en&verb_id=en_go"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/learn" in response.headers["location"]
