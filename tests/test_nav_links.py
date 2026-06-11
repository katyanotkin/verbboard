"""Navigation smoke tests and feedback roundtrip tests.

Covers: home / verbs / about 200s, back links, feedback GET security,
feedback POST redirect-back flow.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi.testclient import TestClient

# ── home ───────────────────────────────────────────────────────────────────


def test_home_renders_200(client: TestClient) -> None:
    assert client.get("/").status_code == 200


def test_home_has_about_link(client: TestClient) -> None:
    assert "/about" in client.get("/").text


def test_home_has_verbs_browse_link(client: TestClient) -> None:
    assert "/verbs" in client.get("/?language=en").text


def test_home_feedback_link_carries_page_and_language(client: TestClient) -> None:
    html = client.get("/?language=en").text
    assert "page=home" in html
    assert "language=en" in html


# ── verbs ──────────────────────────────────────────────────────────────────


def test_verbs_renders_200(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    assert client.get("/verbs?language=en").status_code == 200


def test_verbs_has_back_to_home_link(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    html = client.get("/verbs?language=en&ui_language=en").text
    assert 'href="/?language=en&amp;ui_language=en"' in html


def test_verbs_feedback_link_carries_page_context(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    html = client.get("/verbs?language=en").text
    assert "page=verbs" in html


# ── about ──────────────────────────────────────────────────────────────────


def test_about_has_back_to_home_link(client: TestClient) -> None:
    assert 'href="/?ui_language=' in client.get("/about").text


def test_about_feedback_link_carries_page_context(client: TestClient) -> None:
    assert "page=about" in client.get("/about").text


# ── feedback GET ────────────────────────────────────────────────────────────


def test_feedback_renders_200(client: TestClient) -> None:
    assert client.get("/feedback").status_code == 200


def test_feedback_back_link_reflects_return_to(client: TestClient) -> None:
    """Back link on the feedback form must contain the decoded return_to path."""
    return_to = quote("/verbs?language=en", safe="/")
    html = client.get(f"/feedback?return_to={return_to}").text
    assert "/verbs" in html


def test_feedback_back_link_for_learn_return_to(client: TestClient) -> None:
    """URL-encoded learn page return_to must survive the roundtrip (regression)."""
    return_to = quote("/learn?language=en&verb_id=en_go", safe="/")
    html = client.get(
        f"/feedback?page=learn&language=en&verb_id=en_go&return_to={return_to}"
    ).text
    assert "feedback-link" in html
    assert "/learn" in html


def test_feedback_return_to_rejects_external_url(client: TestClient) -> None:
    html = client.get("/feedback?return_to=https://evil.com/path").text
    assert "evil.com" not in html
    assert 'href="/"' in html


def test_feedback_return_to_rejects_protocol_relative_url(client: TestClient) -> None:
    html = client.get("/feedback?return_to=//evil.com/path").text
    assert "evil.com" not in html


# ── feedback POST ───────────────────────────────────────────────────────────


def test_feedback_submit_returns_to_learn_page(client: TestClient, monkeypatch) -> None:
    """Successful submit from learn page must redirect back to learn (regression)."""
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "ok")
    response = client.post(
        "/feedback",
        data={"comment": "great", "return_to": "/learn?language=en&verb_id=en_go"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    assert "/learn" in location
    assert "en_go" in location


def test_feedback_submit_returns_to_verbs_page(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "ok")
    response = client.post(
        "/feedback",
        data={"comment": "note", "return_to": "/verbs?language=en"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/verbs" in response.headers["location"]


def test_feedback_submit_rejects_external_return_to(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "ok")
    response = client.post(
        "/feedback",
        data={"comment": "note", "return_to": "https://evil.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "evil.com" not in response.headers["location"]
