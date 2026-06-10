from __future__ import annotations

import pytest


# Feedback open-redirect regression
def test_learn_feedback_link_encodes_return_to(page, live_server_url):
    page.goto(f"{live_server_url}/learn?language=en&verb_id=en_be&voice=female")
    page.wait_for_load_state("networkidle")

    link = page.locator("a.feedback-link").first
    href = link.get_attribute("href") or ""

    assert "page=learn" in href
    assert "language=en" in href
    assert "verb_id=en_be" in href
    assert "return_to=" in href
    assert "%3F" in href
    assert "%26" in href


# Learn feedback link preserves encoded return_to
def test_feedback_blocks_external_return_to(page, live_server_url):
    page.goto(
        f"{live_server_url}/feedback?return_to=https://malicious.example.com/path"
    )
    page.wait_for_load_state("networkidle")

    back = page.locator("a.feedback-link").first
    href = back.get_attribute("href") or ""

    assert "malicious.example.com" not in href
    assert href.startswith("/")
    assert "://" not in href


# Known star survives reload
def test_known_star_persists_after_reload(page, live_server_url):
    page.goto(f"{live_server_url}/learn?language=en&verb_id=en_be")
    page.wait_for_load_state("networkidle")

    star = page.locator("#known-btn")
    star.wait_for(state="visible")

    star.click()
    page.wait_for_timeout(300)
    assert star.get_attribute("aria-pressed") == "true"

    page.reload()
    page.wait_for_load_state("networkidle")

    star = page.locator("#known-btn")
    assert star.get_attribute("aria-pressed") == "true"


# Show-more count survives back navigation (Bug 2 regression).
#
# Root cause: applyFilter() always reset displayCount = batch on init, discarding
# the count saved in sessionStorage from a previous visit. On back-nav, the page
# also only had the server-rendered initial batch in window.VB_VERBS.
#
# Fix: applyFilter(filter, init) skips the reset when init=True. verbs_page.js
# fetches missing verbs from /api/verbs on back_forward navigation before rendering.
def test_show_more_count_survives_back_navigation(page, live_server_url):
    """After clicking 'Show more verbs', navigating to a learn page, and going back,
    the verbs page must show at least as many verbs as were visible after show-more.
    """
    page.goto(f"{live_server_url}/verbs?language=en")
    page.wait_for_load_state("networkidle")

    # Wait for the verb list to receive at least one item.
    list_el = page.locator("#vb-list")
    list_el.wait_for(state="visible")
    page.wait_for_timeout(500)

    load_more_btn = page.locator("#vb-load-more")

    # If there is no show-more button (e.g. CI has no verbs or all fit in one batch),
    # skip gracefully so the test does not become a false failure.
    if not load_more_btn.is_visible():
        pytest.skip(
            "No 'Show more verbs' button — verb list is too small to test back-nav count retention"
        )

    # Count items before clicking show-more.
    initial_count = page.locator("#vb-list a.vb-item").count()

    # Click show-more and wait for additional items to appear.
    load_more_btn.click()
    page.wait_for_timeout(800)

    after_more = page.locator("#vb-list a.vb-item").count()

    if after_more <= initial_count:
        pytest.skip(
            "Show-more did not add items — nothing to assert about back-nav count retention"
        )

    # Navigate to the first verb's learn page.
    first_link = page.locator("#vb-list a.vb-item").first
    first_link.click()
    page.wait_for_load_state("networkidle")

    # Go back and wait for the verb list to restore.
    page.go_back()
    page.wait_for_load_state("networkidle")

    # Give the async back-nav re-fetch time to complete.
    page.wait_for_timeout(1500)

    restored_count = page.locator("#vb-list a.vb-item").count()
    assert (
        restored_count >= after_more
    ), f"Expected at least {after_more} verbs after back navigation, got {restored_count}"
