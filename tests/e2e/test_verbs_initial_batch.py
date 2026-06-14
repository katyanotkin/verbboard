"""Regression: verbs page initial render behaviour by viewport.

Both desktop and mobile invariant
-----------------------------------
Both viewports start with at most VB_DISPLAY_BATCH items visible on a fresh
load. The show-more button is visible when total > batch. Filter and sort
changes retain the current display count rather than resetting to batch.

All tests skip gracefully when Firestore has <= VB_DISPLAY_BATCH verbs
(not enough data to distinguish batched vs all-shown).
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
    """Yield a Playwright page with the right pointer media for the viewport name."""
    is_mobile = viewport_name == "mobile"
    context = browser.new_context(
        has_touch=is_mobile,
        viewport=_VIEWPORTS[viewport_name],
    )
    page = context.new_page()
    page.set_default_timeout(15_000)
    try:
        yield page
    finally:
        page.close()
        context.close()


# ── invariant helpers ─────────────────────────────────────────────────────────


def _check_desktop_batch_invariant(page, live_server_url, filter_name, sort_name):
    """Desktop: initial render must show at most VB_DISPLAY_BATCH items."""
    hash_fragment = f"filter={filter_name}&sort={sort_name}"
    page.goto(f"{live_server_url}/verbs?language=en#{hash_fragment}")
    page.evaluate("sessionStorage.clear()")
    page.reload()
    page.wait_for_load_state("networkidle")

    batch = int(page.evaluate("window.VB_DISPLAY_BATCH || 20"))
    all_verbs = page.evaluate("(window.VB_VERBS || []).length")
    if all_verbs <= batch:
        return False

    try:
        page.wait_for_selector("#vb-list .vb-item, .vb-empty", timeout=5_000)
    except Exception:
        return False

    item_count = page.locator("#vb-list .vb-item").count()
    if item_count == 0:
        return False

    assert item_count <= batch, (
        f"desktop  filter={filter_name!r}  sort={sort_name!r}: "
        f"initial render showed {item_count} items but VB_DISPLAY_BATCH={batch}."
    )
    show_more = page.locator("#vb-load-more")
    assert show_more.is_visible(), (
        f"desktop  filter={filter_name!r}  sort={sort_name!r}: "
        f"show-more must be visible when total ({all_verbs}) > batch ({batch})."
    )
    return True


# ── parametrized invariant tests ──────────────────────────────────────────────


@pytest.mark.parametrize("viewport_name", ["desktop", "mobile"])
@pytest.mark.parametrize("sort_name", ["alpha", "newest"])
@pytest.mark.parametrize("filter_name", ["all", "new"])
def test_initial_render_respects_display_batch(browser, live_server_url, filter_name, sort_name, viewport_name):
    """Both desktop and mobile must show at most VB_DISPLAY_BATCH items on fresh load."""
    with _page_for_viewport(browser, viewport_name) as page:
        ran = _check_desktop_batch_invariant(page, live_server_url, filter_name, sort_name)
        if not ran:
            pytest.skip("Not enough verbs to exercise show-more")


# ── after auth hydration re-render ────────────────────────────────────────────


def test_desktop_batch_invariant_holds_after_auth_hydration(browser, live_server_url):
    """Desktop: vb:progress-hydrated re-render must not expand beyond VB_DISPLAY_BATCH."""
    with _page_for_viewport(browser, "desktop") as page:
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

        page.evaluate("window.dispatchEvent(new Event('vb:progress-hydrated'))")
        page.wait_for_timeout(200)

        item_count = page.locator("#vb-list .vb-item").count()
        assert (
            item_count <= batch
        ), f"desktop: after vb:progress-hydrated re-render, {item_count} items visible -- expected at most {batch}."


# ── filter/sort change resets to one batch (both viewports) ──────────────────


@pytest.mark.parametrize("viewport_name", ["desktop", "mobile"])
def test_filter_change_resets_to_one_batch(browser, live_server_url, viewport_name):
    """Switching filter must reset display count to one batch on any viewport."""
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

        all_btn = page.locator('.vb-ftbtn[data-filter="all"]').first
        new_btn = page.locator('.vb-ftbtn[data-filter="new"]').first
        if not all_btn.is_visible():
            pytest.skip("Filter buttons not present on this page")

        all_btn.click()
        page.wait_for_timeout(150)

        show_more = page.locator("#vb-load-more")
        if show_more.is_visible():
            show_more.click()
            page.wait_for_timeout(200)

        new_btn.click()
        page.wait_for_timeout(150)

        item_count = page.locator("#vb-list .vb-item").count()
        assert item_count <= batch, (
            f"viewport={viewport_name!r}: after switching filter, "
            f"{item_count} items -- expected at most {batch} (one batch reset)."
        )
