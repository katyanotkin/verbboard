"""Navigation smoke tests and feedback roundtrip tests.

Covers: home / verbs / about 200s, back links, feedback GET security,
feedback POST redirect-back flow.
"""

from __future__ import annotations

import re
from urllib.parse import quote

from fastapi.testclient import TestClient

# ── home ───────────────────────────────────────────────────────────────────


def test_home_renders_200(client: TestClient) -> None:
    assert client.get("/").status_code == 200


def test_home_has_about_link(client: TestClient) -> None:
    assert "/about" in client.get("/").text


def test_home_has_verbs_browse_link(client: TestClient) -> None:
    assert "/verbs" in client.get("/?language=en").text


def test_home_verb_of_the_day_links_to_learn(client: TestClient) -> None:
    html = client.get("/?language=es&ui_language=en").text
    assert 'class="votd-hero"' in html
    match = re.search(r'href="(/learn\?language=es&verb_id=es_[^"&]+&ui_language=en)"', html)
    assert match, html

    learn_response = client.get(match.group(1))
    assert learn_response.status_code == 200


def test_home_verb_of_the_day_absent_renders_no_hero(client: TestClient, monkeypatch) -> None:
    """When pick_verb_of_the_day() finds nothing (e.g. an empty catalog), the
    home route's votd context var is None/falsy and the template must not
    render the hero markup at all -- not an empty/broken hero."""
    monkeypatch.setattr("app.routes.home.load_entries_for_language", lambda **kw: [])
    html = client.get("/?language=es&ui_language=en").text
    assert "votd-hero" not in html


def test_home_feedback_link_carries_page_and_language(client: TestClient) -> None:
    html = client.get("/?language=en").text
    assert "page=home" in html
    assert "language=en" in html


# ── edition config: home language picker ────────────────────────────────────


def _language_picker_options(html: str) -> list[str]:
    start = html.index('id="language-select"')
    end = html.index("</select>", start)
    return re.findall(r'<option value="(\w+)"', html[start:end])


def test_home_language_picker_free_edition_baseline(client: TestClient) -> None:
    """Order is registry (registration) order filtered to the free set, not
    alphabetical: core.languages.{en,es,fr,he,it,ru}.plugin registration
    order is (en, es, fr, he, it, ru); free edition excludes "fr" (the sole
    Plus-only language), leaving (en, es, he, it, ru)."""
    options = _language_picker_options(client.get("/?language=en").text)
    assert options == ["en", "es", "he", "it", "ru"]


def test_home_language_picker_edition_plus_adds_french(client: TestClient, monkeypatch) -> None:
    """French has a real registered plugin but remains Plus-only. Italian
    moved from Plus-only to free-tier 2026-09-07, so it's already in the
    free-edition baseline; EDITION=plus must add exactly "fr" on top."""
    baseline_options = _language_picker_options(client.get("/?language=en").text)
    assert "it" in baseline_options
    assert "fr" not in baseline_options

    monkeypatch.setenv("EDITION", "plus")
    plus_options = _language_picker_options(client.get("/?language=en").text)

    assert set(plus_options) - set(baseline_options) == {"fr"}


# ── verbs ──────────────────────────────────────────────────────────────────


def test_verbs_renders_200(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    assert client.get("/verbs?language=en").status_code == 200


def test_verbs_has_back_to_home_link(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.verbs.load_entries_for_language", lambda **kw: [])
    html = client.get("/verbs?language=en&ui_language=en").text
    assert 'href="/?language=en&amp;ui_language=en"' in html


def test_verbs_feedback_link_carries_page_context(client: TestClient, monkeypatch) -> None:
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
    html = client.get(f"/feedback?page=learn&language=en&verb_id=en_go&return_to={return_to}").text
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


def test_feedback_submit_rejects_external_return_to(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.feedback.save_feedback", lambda **kw: "ok")
    response = client.post(
        "/feedback",
        data={"comment": "note", "return_to": "https://evil.com"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "evil.com" not in response.headers["location"]
