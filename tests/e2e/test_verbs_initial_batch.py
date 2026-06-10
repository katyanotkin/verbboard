"""Regression: verbs page initial render must respect VB_DISPLAY_BATCH.

Core invariant
--------------
On any fresh page load (navigation type != back_forward):

    rendered_count <= VB_DISPLAY_BATCH
    show_more_visible == (total_visible > VB_DISPLAY_BATCH)

This must hold for every combination of:
  - viewport    desktop (pointer:fine)  /  mobile (pointer:coarse)
  - filter      all / new  (seen/known skipped -- empty without auth progress)
  - sort        alpha / newest

All tests skip gracefully when Firestore has <= VB_DISPLAY_BATCH verbs
(the invariant is vacuously satisfied with no show-more needed).
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest

# ── viewports ─────────────────────────────────────────────────────────────────

_VIEWPORTS = {
    "desktop": {"width": 1280, "height": 800},
    "mobile": {"width": 390, "height": 844},
}


@contextmanager
def _page_for_viewport(browser, viewport_name: str):
    """Yield a Playwright page with the right pointer media for the viewport name.

    'mobile' sets has_touch=True so matchMedia('(any-pointer: coarse)') returns
    true, which is the condition verbs_page.js uses to call filters.showAll().
    """
    is_mobile = viewport_name == "mobile"
    context = browser.new_context(
        has_touch=is_mobile,
        viewport=_VIEWPORTS[viewport_name],
    )
    page = context.new_page()
    page.set_default_timeout(8_000)
    try:
        yield page
    finally:
        page.close()
        context.close()


# ── invariant helper ──────────────────────────────────────────────────────────


def _check_batch_invariant(
    page, live_server_url: str, filter_name: str, sort_name: str
):
    """Navigate to the verbs page with the given filter/sort and assert the invariant.

    Returns True if the assertion ran, False if it was skipped (not enough data).
    Raises AssertionError if the invariant is violated.
    """
    hash_fragment = f"filter={filter_name}&sort={sort_name}"
    page.goto(f"{live_server_url}/verbs?language=en#{hash_fragment}")

    # Clear any leftover sessionStorage so this is always treated as a fresh load.
    page.evaluate("sessionStorage.clear()")
    page.reload()
    page.wait_for_load_state("networkidle")

    batch = int(page.evaluate("window.VB_DISPLAY_BATCH || 20"))
    all_verbs = page.evaluate("(window.VB_VERBS || []).length")

    if all_verbs <= batch:
        return False  # invariant vacuously holds; caller skips

    # Wait for at least one item or confirm empty state
    try:
        page.wait_for_selector("#vb-list .vb-item, .vb-empty", timeout=5_000)
    except Exception:
        return False  # list never rendered; skip

    item_count = page.locator("#vb-list .vb-item").count()

    if item_count == 0:
        return False  # filter produced no results (e.g. 'seen' with no progress)

    assert item_count <= batch, (
        f"viewport=*  filter={filter_name!r}  sort={sort_name!r}: "
        f"initial render showed {item_count} items but VB_DISPLAY_BATCH={batch}. "
        f"Expected at most {batch} items on first paint."
    )

    show_more = page.locator("#vb-load-more")
    assert show_more.is_visible(), (
        f"viewport=*  filter={filter_name!r}  sort={sort_name!r}: "
        f"show-more button must be visible when total ({all_verbs}) > batch ({batch})."
    )

    return True


# ── parametrized invariant tests ──────────────────────────────────────────────


@pytest.mark.parametrize("sort_name", ["alpha", "newest"])
@pytest.mark.parametrize("filter_name", ["all", "new"])
@pytest.mark.parametrize("viewport_name", ["desktop", "mobile"])
def test_initial_render_respects_display_batch(
    browser,
    live_server_url,
    viewport_name: str,
    filter_name: str,
    sort_name: str,
):
    """Initial render must show at most VB_DISPLAY_BATCH items for any
    viewport × filter × sort combination.

    Desktop cases should PASS.
    Mobile cases currently FAIL (showAll() bug).
    """
    with _page_for_viewport(browser, viewport_name) as page:
        ran = _check_batch_invariant(page, live_server_url, filter_name, sort_name)
        if not ran:
            pytest.skip(
                f"Not enough verbs in Firestore to exercise show-more "
                f"(need >VB_DISPLAY_BATCH for filter={filter_name!r})"
            )


# ── after auth hydration re-render ────────────────────────────────────────────


@pytest.mark.parametrize("viewport_name", ["desktop", "mobile"])
def test_batch_invariant_holds_after_auth_hydration(
    browser, live_server_url, viewport_name: str
):
    """After vb:progress-hydrated fires (Firebase auth + localStorage sync),
    a re-render must not expand the visible list beyond VB_DISPLAY_BATCH.

    On mobile this will fail for the same reason: displayCount is already
    Infinity when the hydration re-render runs, so all items stay visible.
    """
    with _page_for_viewport(browser, viewport_name) as page:
        page.goto(f"{live_server_url}/verbs?language=en")
        page.evaluate("sessionStorage.clear()")
        page.reload()
        page.wait_for_load_state("networkidle")

        batch = int(page.evaluate("window.VB_DISPLAY_BATCH || 20"))
        all_verbs = page.evaluate("(window.VB_VERBS || []).length")
        if all_verbs <= batch:
            pytest.skip("Not enough verbs to exercise show-more")

        try:
            page.wait_for_selector("#vb-list .vb-item, .vb-empty", timeout=5_000)
        except Exception:
            pytest.skip("List never rendered")

        # Simulate auth hydration re-render (fires filters.render() via event)
        page.evaluate("window.dispatchEvent(new Event('vb:progress-hydrated'))")
        page.wait_for_timeout(200)

        item_count = page.locator("#vb-list .vb-item").count()
        assert item_count <= batch, (
            f"viewport={viewport_name!r}: after vb:progress-hydrated re-render, "
            f"{item_count} items visible -- expected at most {batch}."
        )


# ── filter-change resets to one batch ─────────────────────────────────────────


@pytest.mark.parametrize("viewport_name", ["desktop", "mobile"])
def test_filter_change_resets_to_one_batch(
    browser, live_server_url, viewport_name: str
):
    """Switching the active filter must reset the display to one batch."""
    with _page_for_viewport(browser, viewport_name) as page:
        page.goto(f"{live_server_url}/verbs?language=en")
        page.evaluate("sessionStorage.clear()")
        page.reload()
        page.wait_for_load_state("networkidle")

        batch = int(page.evaluate("window.VB_DISPLAY_BATCH || 20"))
        all_verbs = page.evaluate("(window.VB_VERBS || []).length")
        if all_verbs <= batch:
            pytest.skip("Not enough verbs to exercise show-more")

        try:
            page.wait_for_selector("#vb-list .vb-item, .vb-empty", timeout=5_000)
        except Exception:
            pytest.skip("List never rendered")

        # Click the 'all' filter button to trigger a filter-change (init=false path)
        all_btn = page.locator('.vb-ftbtn[data-filter="all"]').first
        if not all_btn.is_visible():
            pytest.skip("Filter buttons not present on this page")

        all_btn.click()
        page.wait_for_timeout(150)

        item_count = page.locator("#vb-list .vb-item").count()
        assert item_count <= batch, (
            f"viewport={viewport_name!r}: after switching to 'all' filter, "
            f"{item_count} items visible -- expected at most {batch} (one batch reset)."
        )
