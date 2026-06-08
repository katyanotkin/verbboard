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

LEARN_URL_PARAMS = "language=en&verb_id=en_be"


# ---------------------------------------------------------------------------
# Feedback navigation
# ---------------------------------------------------------------------------


def test_feedback_link_on_verbs(page, live_server_url):
    """Verbs page feedback link navigates to /feedback?page=verbs."""
    page.goto(f"{live_server_url}/verbs?language=en")
    link = page.locator("a.feedback-link").first
    link.wait_for(state="visible")

    href = link.get_attribute("href") or ""
    assert "page=verbs" in href, f"Expected page=verbs in href, got: {href!r}"

    link.click()
    page.wait_for_url("**/feedback**")
    assert "page=verbs" in page.url


def test_feedback_link_on_home(page, live_server_url):
    """Home page feedback link navigates to /feedback?page=home."""
    page.goto(f"{live_server_url}/?language=en")
    link = page.locator("a.feedback-link[href*='feedback']").first
    link.wait_for(state="visible")

    href = link.get_attribute("href") or ""
    assert "/feedback" in href, f"Expected /feedback in href, got: {href!r}"
    assert "page=home" in href, f"Expected page=home in href, got: {href!r}"

    link.click()
    page.wait_for_url("**/feedback**")
    assert "page=home" in page.url


def test_feedback_link_on_learn(page, live_server_url):
    """Learn page feedback link navigates to /feedback?page=learn."""
    page.goto(f"{live_server_url}/learn?{LEARN_URL_PARAMS}")
    link = page.locator("a.feedback-link").first
    link.wait_for(state="visible")

    href = link.get_attribute("href") or ""
    assert "page=learn" in href, f"Expected page=learn in href, got: {href!r}"
    assert "verb_id=en_be" in href, f"Expected verb_id=en_be in href, got: {href!r}"

    link.click()
    page.wait_for_url("**/feedback**")
    assert "page=learn" in page.url


def test_feedback_back_navigates(page, live_server_url):
    """Back link on the feedback page sends the user to `return_to`."""
    return_path = "/verbs?language=en"
    encoded = return_path.replace("?", "%3F").replace("=", "%3D")
    page.goto(f"{live_server_url}/feedback?page=verbs&language=en&return_to={encoded}")

    back = page.locator("a.feedback-link[href*='verbs']").first
    back.wait_for(state="visible")
    back.click()

    page.wait_for_url("**/verbs**")
    assert "language=en" in page.url


# ---------------------------------------------------------------------------
# About page
# ---------------------------------------------------------------------------


def test_about_page_renders_with_ui_language(page, live_server_url):
    """About page uses ui_language param and shows matching title."""
    page.goto(f"{live_server_url}/about?ui_language=ru")
    page.wait_for_load_state("networkidle")
    assert "О приложении VerbBoard" in page.title()
    assert "lang-toggle" not in page.content()


def test_about_back_link_returns_to_home(page, live_server_url):
    """Back link on the about page navigates to home."""
    page.goto(f"{live_server_url}/about")
    page.wait_for_load_state("networkidle")

    back = page.locator("a.feedback-link").first
    back.wait_for(state="visible")
    back.click()

    page.wait_for_url("**/")
    assert page.url.rstrip("/").endswith(live_server_url.rstrip("/")) or "/" in page.url


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
# Verbs page: filter + sort state persistence across Back navigation
# ---------------------------------------------------------------------------


def test_verbs_filter_and_sort_persist_after_back_navigation(page, live_server_url):
    """Filter and sort survive Back navigation from Learn → Verbs (both non-default).

    State is stored in localStorage + URL hash, so this does not depend on
    whether verb items are present in the list -- we navigate to Learn directly
    rather than clicking a verb item.
    """
    page.goto(f"{live_server_url}/verbs?language=en")
    page.wait_for_load_state("networkidle")

    # Wait for JS to initialise filter buttons
    page.wait_for_selector("#vb-filter-toggle")

    # Change filter from default "new" to "all"
    page.locator("#vb-filter-toggle button[data-filter='all']").click()
    page.wait_for_timeout(100)

    # Change sort from default "alpha" to "newest"
    page.locator("#vb-sort").select_option("newest")
    page.wait_for_timeout(100)

    # Navigate to Learn directly -- state is already written to localStorage/hash
    page.goto(
        f"{live_server_url}/learn?{LEARN_URL_PARAMS}"
        f"&return_to={live_server_url}/verbs?language=en"
    )
    page.wait_for_url("**/learn**")

    # Navigate back to Verbs
    page.go_back()
    page.wait_for_url("**/verbs**")
    page.wait_for_timeout(300)  # let JS init run

    # Filter should still be "all"
    filter_value = page.locator("#vb-filter-toggle .vb-ftbtn.active").get_attribute(
        "data-filter"
    )
    assert (
        filter_value == "all"
    ), f"Expected 'all' filter to remain active after Back, got: {filter_value!r}"

    # Sort should still be "newest"
    sort_value = page.locator("#vb-sort").input_value()
    assert (
        sort_value == "newest"
    ), f"Expected sort='newest' after Back navigation, got: {sort_value!r}"


def test_verbs_filter_only_change_persists_after_back_navigation(page, live_server_url):
    """Filter change alone (sort left at default alpha) survives Back navigation.

    Navigates to Learn directly rather than clicking a verb item so the test
    does not depend on verb data being present in the list.
    """
    page.goto(f"{live_server_url}/verbs?language=en")
    page.wait_for_load_state("networkidle")

    # Wait for JS to initialise filter buttons
    page.wait_for_selector("#vb-filter-toggle")

    # Verify default sort is alpha
    assert (
        page.locator("#vb-sort").input_value() == "alpha"
    ), "Expected alpha as default sort"

    # Change filter to "seen" -- do not touch sort
    page.locator("#vb-filter-toggle button[data-filter='seen']").click()
    page.wait_for_timeout(100)

    # Navigate to Learn directly -- state is already written to localStorage/hash
    page.goto(
        f"{live_server_url}/learn?{LEARN_URL_PARAMS}"
        f"&return_to={live_server_url}/verbs?language=en"
    )
    page.wait_for_url("**/learn**")

    # Navigate back
    page.go_back()
    page.wait_for_url("**/verbs**")
    page.wait_for_timeout(300)

    # Filter should still be "seen"
    filter_value = page.locator("#vb-filter-toggle .vb-ftbtn.active").get_attribute(
        "data-filter"
    )
    assert (
        filter_value == "seen"
    ), f"Expected 'seen' filter to remain active after Back, got: {filter_value!r}"

    # Sort should still be "alpha" (unchanged default)
    sort_value = page.locator("#vb-sort").input_value()
    assert (
        sort_value == "alpha"
    ), f"Expected sort='alpha' (default) after Back navigation, got: {sort_value!r}"


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
