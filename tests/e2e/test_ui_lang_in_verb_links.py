"""E2E tests: ui_language propagation through JS-rendered verb list links.

The server injects `window.VB_UI_LANG` into verbs.html; verbs_filters.js reads it
when building `<a class="vb-item">` hrefs. These tests confirm the full pipeline:
server embed -> JS rendering -> href attribute.

Regression class: VB_UI_LANG present in HTML but JS strips it from the link, or the
return_to encoded by JS drops ui_language, causing the back button on the learn page
to silently lose the locale preference.

All tests skip gracefully when Firestore returns no verb data (CI without credentials).
"""

from __future__ import annotations

from urllib.parse import parse_qs, unquote, urlparse

import pytest

_VERBS_RU_UI = "/verbs?language=en&ui_language=ru"
_VERBS_HE_UI = "/verbs?language=en&ui_language=he"


def _wait_for_verb_items(page, timeout: int = 5_000):
    """Wait for JS to render at least one verb item. Returns count (0 = skip)."""
    try:
        page.wait_for_selector("#vb-list a.vb-item", timeout=timeout)
    except Exception:
        return 0
    return page.locator("#vb-list a.vb-item").count()


# ── JS-built links carry ui_language ─────────────────────────────────────────


def test_js_verb_links_carry_ui_language(page, live_server_url):
    """After JS renders, each verb list item <a> href must include ui_language=ru.

    verbs_filters.js reads window.VB_UI_LANG and appends &ui_language=… to every
    learn href. This guards against VB_UI_LANG being dropped from the built URL.
    """
    page.goto(f"{live_server_url}{_VERBS_RU_UI}")
    page.wait_for_load_state("networkidle")

    count = _wait_for_verb_items(page)
    if count == 0:
        pytest.skip("No verb items rendered — Firestore has no verbs for language=en")

    first_href = page.locator("#vb-list a.vb-item").first.get_attribute("href") or ""
    assert "ui_language=ru" in first_href, f"JS-built verb link must contain ui_language=ru. Got href={first_href!r}"


def test_js_verb_links_carry_ui_language_he(page, live_server_url):
    """Hebrew ui_language=he survives into JS-built verb list hrefs (RTL locale)."""
    page.goto(f"{live_server_url}{_VERBS_HE_UI}")
    page.wait_for_load_state("networkidle")

    count = _wait_for_verb_items(page)
    if count == 0:
        pytest.skip("No verb items rendered — Firestore has no verbs for language=en")

    first_href = page.locator("#vb-list a.vb-item").first.get_attribute("href") or ""
    assert "ui_language=he" in first_href, f"JS-built verb link must contain ui_language=he. Got href={first_href!r}"


def test_js_verb_links_return_to_carries_ui_language(page, live_server_url):
    """The return_to query param inside each verb link href must also encode ui_language.

    When the user opens the learn page and clicks Back, the server uses return_to to
    redirect them. If ui_language is absent from return_to, the user is dropped back
    on the verbs page without their locale preference.
    """
    page.goto(f"{live_server_url}{_VERBS_RU_UI}")
    page.wait_for_load_state("networkidle")

    count = _wait_for_verb_items(page)
    if count == 0:
        pytest.skip("No verb items rendered — Firestore has no verbs for language=en")

    first_href = page.locator("#vb-list a.vb-item").first.get_attribute("href") or ""

    # Extract return_to param and decode it
    parsed = urlparse(first_href)
    qs = parse_qs(parsed.query)
    return_to_values = qs.get("return_to", [])

    assert return_to_values, f"No return_to param in href={first_href!r}"
    return_to = unquote(return_to_values[0])

    assert "ui_language=ru" in return_to, (
        f"return_to inside verb link must contain ui_language=ru. "
        f"Decoded return_to={return_to!r}, full href={first_href!r}"
    )


# ── Back-nav from learn preserves ui_language in URL ─────────────────────────


def test_back_link_on_learn_preserves_ui_language(page, live_server_url):
    """When the learn page is opened with return_to that includes ui_language, the
    topbar Back button must point to a URL containing ui_language.

    This verifies the server-side template passes return_to through to the back link
    without stripping the locale param.
    """
    from urllib.parse import quote

    return_to = quote("/verbs?language=en&ui_language=ru", safe="/")
    url = f"{live_server_url}/learn?language=en&verb_id=en_be&ui_language=ru&return_to={return_to}"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    back_btn = page.locator(".nav-btn.nav-btn--ghost").first
    if not back_btn.is_visible():
        pytest.skip("Back button not visible — en_be may not exist in Firestore")

    href = back_btn.get_attribute("href") or ""
    assert "ui_language=ru" in href, (
        f"Back button on learn page must carry ui_language=ru when return_to includes it. Got href={href!r}"
    )


def test_back_nav_from_learn_lands_on_verbs_with_ui_language(page, live_server_url):
    """Full navigation roundtrip: verbs (ui=ru) -> learn -> topbar Back -> verbs with ui=ru.

    Verifies the end-to-end path that was found to silently lose ui_language during
    manual testing: JS builds the href with return_to=/verbs?...&ui_language=ru, and
    the learn page back button must honour it.
    """
    page.goto(f"{live_server_url}{_VERBS_RU_UI}")
    page.wait_for_load_state("networkidle")

    count = _wait_for_verb_items(page)
    if count == 0:
        pytest.skip("No verb items — Firestore empty")

    first_item = page.locator("#vb-list a.vb-item").first
    first_href = first_item.get_attribute("href") or ""

    # Navigate directly via href (simulates user clicking the item)
    page.goto(f"{live_server_url}{first_href}")
    page.wait_for_load_state("networkidle")

    back_btn = page.locator(".nav-btn.nav-btn--ghost").first
    if not back_btn.is_visible():
        pytest.skip("Back button not visible — verb may not have loaded")

    # Click the explicit Back button (not browser back)
    back_btn.click()
    page.wait_for_load_state("networkidle")

    final_url = page.url
    assert "ui_language=ru" in final_url, (
        f"After Back from learn page, URL must contain ui_language=ru. Got: {final_url!r}"
    )


# ── Bottom-nav back tab also carries ui_language ──────────────────────────────


def test_bottom_nav_back_tab_carries_ui_language(page, live_server_url):
    """Bottom-nav Back tab href must carry ui_language=ru (checked in DOM, not by visibility).

    The bottom nav is hidden on desktop viewports via CSS; the href is set server-side
    so we validate the attribute directly without requiring the element to be visible.
    """
    page.goto(f"{live_server_url}{_VERBS_RU_UI}")
    page.wait_for_load_state("networkidle")

    back_tab = page.locator(".bottom-nav a[aria-label='Back']")
    back_tab.wait_for(state="attached", timeout=5000)

    href = back_tab.get_attribute("href") or ""
    assert "ui_language=ru" in href, f"Bottom-nav Back tab must carry ui_language=ru. Got href={href!r}"
