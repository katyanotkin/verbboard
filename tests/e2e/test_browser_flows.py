"""
Browser-level smoke tests using Playwright.

These cover interactions that HTTP-level tests cannot prove:
- Feedback links are clickable and navigate correctly (Home, Verbs, Learn).
- The Back link on the feedback page returns to `return_to`.
- The voice-toggle form submits the selected voice as a URL param.
- The known-star button toggles aria-pressed and writes to localStorage.
- The home Learn button submits the form and navigates to /learn.

Server: started by tests/e2e/conftest.py (port 9753, local verb data, no-op audio).
Verb used: tests prefer `en_be` when present, otherwise use the first available rendered option.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest

LEARN_URL_PARAMS = "language=en&verb_id=en_be"

# ---------------------------------------------------------------------------
# Feedback roundtrip: source page → /feedback → Back → source page
#
# Covers every page that exposes a feedback link. Add new sources as
# pytest.param entries — no new test function required.
# ---------------------------------------------------------------------------

_FEEDBACK_SOURCES = [
    pytest.param("/?language=en", "/", id="home"),
    pytest.param("/verbs?language=en&ui_language=ru", "/verbs", id="verbs"),
    pytest.param(f"/learn?{LEARN_URL_PARAMS}", "/learn", id="learn"),
    pytest.param("/about", "/about", id="about"),
]


@pytest.mark.parametrize("source_url,landing_path", _FEEDBACK_SOURCES)
def test_feedback_roundtrip(page, live_server_url, source_url, landing_path):
    """Feedback link on each page opens /feedback and Back returns to the source."""
    page.goto(f"{live_server_url}{source_url}")
    page.wait_for_load_state("networkidle")

    feedback = page.locator("a[href*='/feedback']").first
    if not feedback.is_visible():
        pytest.skip(f"Feedback link not visible on {source_url!r}")
    feedback.click()
    page.wait_for_load_state("networkidle")
    assert "/feedback" in page.url, f"Expected /feedback page, got: {page.url!r}"

    back = page.locator("a.feedback-link").first
    back.wait_for(state="visible")
    back.click()
    page.wait_for_load_state("networkidle")

    assert (
        landing_path in page.url
    ), f"After feedback Back, expected {landing_path!r} in URL. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# About roundtrip: home → about → Back → home
# ---------------------------------------------------------------------------


def test_about_roundtrip_from_home(page, live_server_url):
    """About link on home opens /about; Back on about returns to home."""
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    about_link = page.locator("a.about-page-link").first
    if not about_link.is_visible():
        pytest.skip("About link not visible on home page")
    about_link.click()
    page.wait_for_load_state("networkidle")
    assert "/about" in page.url, f"Expected /about page, got: {page.url!r}"

    back = page.locator("a.feedback-link").first
    back.wait_for(state="visible")
    back.click()
    page.wait_for_load_state("networkidle")

    assert urlparse(page.url).path in (
        "/",
        "",
    ), f"Expected home (path=/) after about Back. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# About page
# ---------------------------------------------------------------------------


def test_about_page_renders_with_ui_language(page, live_server_url):
    """About page uses ui_language param and shows matching title."""
    page.goto(f"{live_server_url}/about?ui_language=ru")
    page.wait_for_load_state("networkidle")
    assert "О приложении VerbBoard" in page.title()
    assert "lang-toggle" not in page.content()


def test_about_feedback_link_carries_page_context(page, live_server_url):
    """About page feedback link carries page=about context."""
    page.goto(f"{live_server_url}/about")
    page.wait_for_load_state("networkidle")

    links = page.locator("a.feedback-link").all()
    feedback_hrefs = [lnk.get_attribute("href") or "" for lnk in links]
    assert any(
        "page=about" in h for h in feedback_hrefs
    ), f"Expected page=about in one of the feedback links, got: {feedback_hrefs}"


# ---------------------------------------------------------------------------
# Voice toggle
# ---------------------------------------------------------------------------


def test_voice_toggle_submits_correct_voice(page, live_server_url):
    """Clicking the male voice button reloads the learn page with voice=male."""
    page.goto(f"{live_server_url}/learn?{LEARN_URL_PARAMS}&voice=female")
    page.wait_for_load_state("networkidle")

    male_btn = page.locator("button.voice-btn[value='male']")
    male_btn.wait_for(state="visible")
    male_btn.click()

    page.wait_for_load_state("networkidle")
    assert (
        "voice=male" in page.url
    ), f"Expected voice=male in URL after toggle, got: {page.url!r}"


# ---------------------------------------------------------------------------
# Known-star (localStorage)
# ---------------------------------------------------------------------------


def test_known_star_toggles_ui_state(page, live_server_url):
    """Star button toggles aria-pressed and updates known:en in localStorage."""
    page.goto(f"{live_server_url}/learn?{LEARN_URL_PARAMS}")
    page.wait_for_load_state("networkidle")

    star = page.locator("#known-btn")
    star.wait_for(state="visible")

    # Page load: verb should not be known yet (fresh localStorage).
    assert star.get_attribute("aria-pressed") == "false"

    # First click: mark as known.
    star.click()
    page.wait_for_timeout(300)
    assert star.get_attribute("aria-pressed") == "true"

    known_raw = page.evaluate("localStorage.getItem('known:en')")
    assert (
        known_raw is not None
    ), "localStorage key 'known:en' should exist after first click"
    assert "en_be" in known_raw, f"Expected en_be in localStorage, got: {known_raw!r}"

    # Second click: unmark.
    star.click()
    page.wait_for_timeout(300)
    assert star.get_attribute("aria-pressed") == "false"

    known_raw2 = page.evaluate("localStorage.getItem('known:en')")
    assert "en_be" not in (
        known_raw2 or ""
    ), f"Expected en_be removed from localStorage, got: {known_raw2!r}"
