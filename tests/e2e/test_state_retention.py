from __future__ import annotations

from urllib.parse import urlparse

import pytest

# ---------------------------------------------------------------------------
# Parametrize axes -- add new entries here, no new test functions needed
# ---------------------------------------------------------------------------

_RETURN_STRATEGIES = [
    pytest.param("browser_back", id="browser-back"),
    pytest.param("app_back", id="app-back-button"),
]

_LEARN_ACTIONS = [
    pytest.param("none", id="no-action"),
    pytest.param("change_voice", id="change-voice"),
    pytest.param("visit_feedback", id="visit-feedback"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_verb_items(page, timeout: int = 5_000) -> None:
    """Skip the test if no verb items are rendered (e.g. empty Firestore)."""
    try:
        page.wait_for_selector("#vb-list a.vb-item", timeout=timeout)
    except Exception:
        pytest.skip("No verb items rendered — Firestore has no verbs for this language")


def _active_filter(page) -> str:
    """Return the data-filter value of the currently active filter button."""
    return page.locator(".vb-ftbtn.active").first.get_attribute("data-filter") or ""


def _active_sort(page) -> str:
    """Return the current value of the sort select."""
    return page.locator("#vb-sort").input_value()


def _maybe_expand_verb_list(page) -> int | None:
    """Try to expand the verb list via show-more. Returns post-expansion count or None."""
    btn = page.locator("#vb-load-more")
    if not btn.is_visible():
        return None
    before = page.locator("#vb-list a.vb-item").count()
    btn.click()
    page.wait_for_timeout(800)
    after = page.locator("#vb-list a.vb-item").count()
    return after if after > before else None


def _perform_learn_action(page, action: str) -> None:
    """Perform an optional action on the learn page before navigating back.

    Add new actions as pytest.param entries in _LEARN_ACTIONS above.
    """
    if action == "change_voice":
        male_btn = page.locator("button.voice-btn[value='male']")
        if male_btn.is_visible():
            male_btn.click()
            page.wait_for_load_state("networkidle")
    elif action == "visit_feedback":
        # Go to feedback from learn, then use the app Back link (which now carries
        # return_to thanks to full_learn_href in render.py), then go_back once more
        # to restore the original learn URL before _return_to_verbs runs.
        feedback = page.locator("a.feedback-link[href*='feedback']").first
        if feedback.is_visible():
            feedback.click()
            page.wait_for_load_state("networkidle")
            page.go_back()
            page.wait_for_load_state("networkidle")


def _return_to_verbs(page, return_via: str) -> None:
    """Navigate back to /verbs using the given strategy.

    browser_back loops go_back() until on /verbs because learn actions like
    voice-change add entries to the browser history stack.
    """
    if return_via == "app_back":
        back_btn = page.locator(".nav-btn.nav-btn--ghost").first
        if not back_btn.is_visible():
            pytest.skip("Topbar Back not visible — verb may not have loaded")
        back_btn.click()
        page.wait_for_load_state("networkidle")
    else:
        for _ in range(5):
            if urlparse(page.url).path.rstrip("/") == "/verbs":
                break
            page.go_back()
            page.wait_for_load_state("networkidle")
    page.wait_for_timeout(1500)


# ---------------------------------------------------------------------------
# Unrelated-to-back-nav smoke checks (keep here for context)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Holistic back-nav state invariant
#
# All user-visible state on /verbs must survive any round-trip to the learn
# page regardless of what the user did there or how they returned.
#
# Dimensions:
#   return_via  -- how the user gets back (browser Back button, app Back link)
#   learn_action -- what the user did on the learn page before returning
#
# State checked simultaneously:
#   - active filter (set to non-default "all")
#   - active sort   (set to non-default "newest")
#   - ui_language in URL (?ui_language=ru)
#   - display count (only when the list was expandable via show-more)
#
# To cover a new scenario add a pytest.param to _RETURN_STRATEGIES or
# _LEARN_ACTIONS above -- no new test function required.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("learn_action", _LEARN_ACTIONS)
@pytest.mark.parametrize("return_via", _RETURN_STRATEGIES)
def test_verbs_state_survives_learn_roundtrip(page, live_server_url, return_via, learn_action):
    """All /verbs state must survive any learn-page round-trip."""
    page.goto(f"{live_server_url}/verbs?language=en&ui_language=ru")
    page.wait_for_load_state("networkidle")
    _require_verb_items(page)

    # Filter and sort first -- applyFilter(non-init) resets displayCount to batch,
    # so expanding must happen AFTER to get the correct expanded count in sessionStorage.
    page.locator(".vb-ftbtn[data-filter='all']").click()
    page.wait_for_timeout(200)
    page.locator("#vb-sort").wait_for(state="visible")
    page.locator("#vb-sort").select_option("newest")
    page.wait_for_timeout(200)

    expanded_count = _maybe_expand_verb_list(page)

    page.locator("#vb-list a.vb-item").first.click()
    page.wait_for_load_state("networkidle")

    _perform_learn_action(page, learn_action)
    _return_to_verbs(page, return_via)

    tag = f"[{return_via}/{learn_action}]"
    assert _active_filter(page) == "all", f"{tag} filter reset to {_active_filter(page)!r}"
    assert _active_sort(page) == "newest", f"{tag} sort reset to {_active_sort(page)!r}"
    assert "ui_language=ru" in page.url, f"{tag} ui_language lost. URL: {page.url!r}"

    if expanded_count is not None:
        restored = page.locator("#vb-list a.vb-item").count()
        assert restored >= expanded_count, f"{tag} display count reset: expected >={expanded_count}, got {restored}"


# ---------------------------------------------------------------------------
# Direct verbs → feedback → verbs round-trip
#
# The feedback link on /verbs uses return_to so the back button on /feedback
# returns via navType='navigate' with referrer='/feedback' -- different from
# the '/learn' path covered above. The isBackNav check was extended to include
# '/feedback' in the referrer test.
#
# About page is not linked from /verbs and its Back link goes to Home, so
# browser_back (already covered by navType='back_forward') is the only relevant
# path and needs no separate test.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("return_via", _RETURN_STRATEGIES)
def test_verbs_state_survives_feedback_detour(page, live_server_url, return_via):
    """All /verbs state must survive a direct verbs→feedback→verbs round-trip."""
    page.goto(f"{live_server_url}/verbs?language=en&ui_language=ru")
    page.wait_for_load_state("networkidle")
    _require_verb_items(page)

    page.locator(".vb-ftbtn[data-filter='all']").click()
    page.wait_for_timeout(200)
    page.locator("#vb-sort").wait_for(state="visible")
    page.locator("#vb-sort").select_option("newest")
    page.wait_for_timeout(200)

    expanded_count = _maybe_expand_verb_list(page)

    # Navigate to feedback via the verbs-page feedback link
    feedback_link = page.locator("a.feedback-link[href*='feedback']").first
    if not feedback_link.is_visible():
        pytest.skip("Feedback link not visible on verbs page")
    feedback_link.click()
    page.wait_for_load_state("networkidle")

    if return_via == "app_back":
        back = page.locator("a.feedback-link[href*='verbs']").first
        if not back.is_visible():
            pytest.skip("Feedback back link to verbs not visible")
        back.click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1500)
    else:
        _return_to_verbs(page, "browser_back")

    tag = f"[feedback/{return_via}]"
    assert _active_filter(page) == "all", f"{tag} filter reset to {_active_filter(page)!r}"
    assert _active_sort(page) == "newest", f"{tag} sort reset to {_active_sort(page)!r}"
    assert "ui_language=ru" in page.url, f"{tag} ui_language lost. URL: {page.url!r}"

    if expanded_count is not None:
        restored = page.locator("#vb-list a.vb-item").count()
        assert restored >= expanded_count, f"{tag} display count reset: expected >={expanded_count}, got {restored}"
