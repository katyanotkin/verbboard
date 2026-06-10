"""Navigation link presence and return_to roundtrip tests.

Covers every user-facing page: feedback links carry the right context,
back links point to the right destinations, and the feedback -> back-to-origin
flow (the "Back to Learn" regression) is explicitly regression-tested.
"""

from __future__ import annotations

from urllib.parse import quote

from fastapi.testclient import TestClient

from core.models import Board, VerbEntry

# ── helpers ────────────────────────────────────────────────────────────────


def _make_board(verb: VerbEntry) -> Board:
    return Board(
        language="en",
        verb=verb,
        voice_key="female",
        voice_label="Female",
        sections=[
            {
                "title": "Present",
                "rows": [
                    {
                        "key": "base",
                        "label": "Base",
                        "text": verb.forms.get("base", ""),
                        "href": "",
                    },
                ],
            }
        ],
    )


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
    html = client.get("/verbs?language=en").text
    assert 'href="/?language=en"' in html


def test_verbs_feedback_link_carries_page_context(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    html = client.get("/verbs?language=en").text
    assert "page=verbs" in html


# ── about ──────────────────────────────────────────────────────────────────


def test_about_has_back_to_home_link(client: TestClient) -> None:
    assert 'href="/"' in client.get("/about").text


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


# ── learn page board (render unit tests) ───────────────────────────────────


def test_learn_board_has_feedback_link(mock_verb: VerbEntry) -> None:
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en")
    assert "/feedback?" in html
    assert "page=learn" in html
    assert "en_go" in html


def test_learn_board_feedback_link_url_encodes_learn_href(mock_verb: VerbEntry) -> None:
    """Feedback href must encode the learn page URL (not the back-button destination).

    The feedback link's return_to is always the learn page itself, so it always
    contains both ? (%3F) and & (%26) regardless of what return_to is passed.
    """
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/?language=en")
    assert "%3F" in html  # ? in /learn?language=en is encoded
    assert "%26" in html  # & in &verb_id=en_go is encoded


def test_learn_board_feedback_return_to_is_learn_page_not_back_destination(
    mock_verb: VerbEntry,
) -> None:
    """Feedback return_to must point to learn page, independent of back-button destination."""
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), return_to="/verbs?language=en")
    assert "/learn" in html
    assert "%3F" in html
    assert "%26" in html


# ── ui_language propagation regression (Firebase Hosting cookie stripping) ─
#
# Firebase Hosting strips all cookies except __session before forwarding to
# Cloud Run. ui_language was only in the cookie, so it was silently lost on
# every navigation that did not go through the globe dropdown. The fix embeds
# ui_language as a URL query parameter in every nav link so it survives the
# forward without relying on cookies.


def test_home_browse_link_includes_ui_language(client: TestClient) -> None:
    """Browse Verbs link on home page must carry ui_language so it survives
    Firebase Hosting's cookie stripping (Bug 1 regression).
    """
    html = client.get("/?ui_language=ru&language=en").text
    # The browse-row link is a Jinja2 href expression; Jinja2 does not escape
    # bare & inside attribute values, so it appears as literal &.
    assert "/verbs?language=en&ui_language=ru" in html


def test_home_practice_shortcut_includes_ui_language(client: TestClient) -> None:
    """Practice shortcut link on home page must carry ui_language (Bug 1 regression)."""
    html = client.get("/?ui_language=ru&language=en").text
    assert "/verbs?language=en&ui_language=ru#practice-panel" in html


def test_verbs_bottom_nav_search_tab_includes_ui_language(
    client: TestClient, monkeypatch
) -> None:
    """Bottom-nav Search tab on verbs page must carry ui_language (Bug 1 regression).

    Jinja2 autoescape is active for HTML templates, so & is rendered as &amp;
    inside href attributes generated by the template include.
    """
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    html = client.get("/verbs?language=en&ui_language=ru").text
    assert "/?language=en&amp;ui_language=ru" in html


def test_verbs_bottom_nav_list_tab_includes_ui_language(
    client: TestClient, monkeypatch
) -> None:
    """Bottom-nav List tab on verbs page must carry ui_language (Bug 1 regression)."""
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    html = client.get("/verbs?language=en&ui_language=ru").text
    assert "/verbs?language=en&amp;ui_language=ru" in html


def test_verbs_page_exposes_vb_ui_lang_global(client: TestClient, monkeypatch) -> None:
    """verbs.html must embed window.VB_UI_LANG so JS can build learn links with
    the correct ui_language parameter (Bug 1 regression).
    """
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    html = client.get("/verbs?language=en&ui_language=ru").text
    assert 'window.VB_UI_LANG = "ru"' in html


def test_board_bottom_nav_back_href_includes_ui_language(
    mock_verb: VerbEntry,
) -> None:
    """Board bottom-nav back link must include ui_language so navigating back to
    the verbs list preserves the UI locale (Bug 1 regression).

    render_board_html uses a Jinja2 environment with autoescape, so & in href
    attributes is rendered as &amp;.
    """
    from core.render import render_board_html

    html = render_board_html(_make_board(mock_verb), ui_lang="ru")
    assert "/verbs?language=en&amp;ui_language=ru" in html
