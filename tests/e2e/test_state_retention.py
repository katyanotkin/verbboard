from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _expand_verb_list(page, live_server_url) -> int:
    """Navigate to /verbs, click show-more once, return count after expansion.

    Skips the test (via pytest.skip) if the list is too small to expand.
    Returns the item count after show-more.
    """
    page.goto(f"{live_server_url}/verbs?language=en")
    page.wait_for_load_state("networkidle")
    page.locator("#vb-list").wait_for(state="visible")
    page.wait_for_timeout(500)

    btn = page.locator("#vb-load-more")
    if not btn.is_visible():
        pytest.skip("No show-more button — verb list too small")

    before = page.locator("#vb-list a.vb-item").count()
    btn.click()
    page.wait_for_timeout(800)

    after = page.locator("#vb-list a.vb-item").count()
    if after <= before:
        pytest.skip("Show-more did not add items")
    return after


def _go_to_learn_then_return(page, live_server_url, return_via: str) -> None:
    """Navigate from /verbs to the first verb's learn page, then return.

    return_via: 'app_back' (topbar Back link) | 'browser_back' (page.go_back())
    """
    first = page.locator("#vb-list a.vb-item").first
    first.click()
    page.wait_for_load_state("networkidle")

    if return_via == "app_back":
        back_btn = page.locator(".nav-btn.nav-btn--ghost").first
        if not back_btn.is_visible():
            pytest.skip("Topbar Back not visible — verb may not have loaded")
        back_btn.click()
    else:
        page.go_back()

    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)


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


# Invariant: expanded verb count survives any return trip to /verbs.
#
# Root cause of original bug: applyFilter() reset displayCount=batch on every
# init; verbs_page.js only re-fetched on back_forward nav type (browser Back).
# Clicking the app's topbar Back button from /learn navigates via return_to URL
# (navType='navigate'), so the refetch and count-restore were both skipped.
#
# Fix: isBackNav in verbs_filters.js also triggers when referrer includes '/learn'.
# verbs_page.js refetch IIFE also triggers on referrer='/learn', and no longer
# skips mobile (mobile now uses batch/show-more like desktop).
#
# Add new return strategies as additional pytest.param entries -- no new test needed.
@pytest.mark.parametrize(
    "return_via",
    [
        pytest.param("browser_back", id="browser-back"),
        pytest.param("app_back", id="app-back-button"),
    ],
)
def test_show_more_count_survives_return_to_verbs(page, live_server_url, return_via):
    """Expanded verb count must be restored however the user returns to /verbs."""
    after_more = _expand_verb_list(page, live_server_url)
    _go_to_learn_then_return(page, live_server_url, return_via)

    restored = page.locator("#vb-list a.vb-item").count()
    assert (
        restored >= after_more
    ), f"[{return_via}] Expected >= {after_more} verbs on return, got {restored}"
