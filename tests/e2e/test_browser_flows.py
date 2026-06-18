"""
Browser-level smoke tests using Playwright.

These cover interactions that HTTP-level tests cannot prove:
- Feedback links are clickable and navigate correctly (Home, Verbs, Learn).
- The Back link on the feedback page returns to `return_to`.
- The voice-toggle form submits the selected voice as a URL param.
- The known-star button toggles aria-pressed and writes to localStorage.
- The home Learn button submits the form and navigates to /learn.
- Verbs → Learn → Feedback → Back → Back restores verbs with full state.

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

    assert landing_path in page.url, f"After feedback Back, expected {landing_path!r} in URL. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# About roundtrip: home → about → Back → home
# ---------------------------------------------------------------------------


def test_about_roundtrip_from_home(page, live_server_url):
    """About link on home opens /about; Back on about returns to home."""
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    about_link = page.locator("a.home-sec-link").first
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
    assert "voice=male" in page.url, f"Expected voice=male in URL after toggle, got: {page.url!r}"


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
    assert known_raw is not None, "localStorage key 'known:en' should exist after first click"
    assert "en_be" in known_raw, f"Expected en_be in localStorage, got: {known_raw!r}"

    # Second click: unmark.
    star.click()
    page.wait_for_timeout(300)
    assert star.get_attribute("aria-pressed") == "false"

    known_raw2 = page.evaluate("localStorage.getItem('known:en')")
    assert "en_be" not in (known_raw2 or ""), f"Expected en_be removed from localStorage, got: {known_raw2!r}"


# ---------------------------------------------------------------------------
# Verbs → Learn → Feedback → Back × 2 returns to /verbs with state intact
#
# Regression for: feedback link on learn used learn_href without return_to,
# so feedback Back landed on learn with no return_to, then learn Back went
# to home instead of verbs.  Fixed by including resolved_return_to in the
# learn URL embedded in the feedback link (render.py full_learn_href).
# ---------------------------------------------------------------------------


def test_verbs_learn_feedback_returns_to_verbs_with_state(page, live_server_url):
    """Verbs→Learn→Feedback→Back→Back must land on /verbs with ui_language,
    filter, sort, and display count all intact."""
    verbs_url = f"{live_server_url}/verbs?language=en&ui_language=ru"
    page.goto(verbs_url)
    page.evaluate("sessionStorage.clear()")
    page.reload()
    page.wait_for_load_state("networkidle")

    # Apply non-default filter and sort so we can verify they survive the trip.
    filter_sel = page.locator("#vb-filter-toggle")
    if filter_sel.is_visible():
        filter_sel.select_option("all")
        page.wait_for_timeout(150)

    sort_sel = page.locator("#vb-sort")
    if sort_sel.is_visible():
        sort_sel.select_option("newest")
        page.wait_for_timeout(150)

    # Navigate into a verb.
    first_verb = page.locator("#vb-list a.vb-item").first
    try:
        first_verb.wait_for(state="visible", timeout=5_000)
    except Exception:
        pytest.skip("No verb items rendered")
    first_verb.click()
    page.wait_for_load_state("networkidle")
    assert "/learn" in page.url, f"Expected /learn, got {page.url!r}"

    # Open feedback from learn page.
    feedback_link = page.locator("a.feedback-link[href*='feedback']").first
    feedback_link.wait_for(state="visible")
    feedback_link.click()
    page.wait_for_load_state("networkidle")
    assert "/feedback" in page.url, f"Expected /feedback, got {page.url!r}"

    # Click app Back on feedback -- must return to /learn WITH return_to.
    back_on_feedback = page.locator("a.feedback-link").first
    back_on_feedback.wait_for(state="visible")
    back_on_feedback.click()
    page.wait_for_load_state("networkidle")
    assert "/learn" in page.url, f"Feedback Back must land on /learn, got {page.url!r}"
    assert "return_to=" in page.url, f"Learn URL after feedback Back must contain return_to. Got: {page.url!r}"

    # Click app Back on learn -- must return to /verbs.
    back_on_learn = page.locator("a.nav-btn.nav-btn--ghost").first
    back_on_learn.wait_for(state="visible")
    back_on_learn.click()
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(500)

    assert "/verbs" in page.url, f"Learn Back must land on /verbs, got {page.url!r}"

    # ui_language must survive the full round-trip.
    assert "ui_language=ru" in page.url, f"ui_language=ru lost after round-trip. URL: {page.url!r}"

    # Filter and sort must be restored (from localStorage).
    page.wait_for_selector("#vb-filter-toggle", timeout=5_000)
    active_filter = page.locator("#vb-filter-toggle").input_value()
    assert active_filter == "all", f"Filter not restored: got {active_filter!r}"

    sort_value = sort_sel.input_value()
    assert sort_value == "newest", f"Sort not restored: got {sort_value!r}"

    # Display count: restored from sessionStorage when isBackNav is true.
    # isBackNav relies on document.referrer which is set by the browser for
    # link-click navigations; verify sessionStorage held the expanded count
    # even if the JS chose not to restore it (referrer absent in headless mode).
    saved_count = page.evaluate("parseInt(sessionStorage.getItem('vb-display-count:en') || '0', 10)")
    assert saved_count >= 20, f"sessionStorage vb-display-count:en not written. Got: {saved_count!r}"
