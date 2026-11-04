"""Rendering of the "new version available" banner (pwa.js, common.css).

Uses window.VerbBoardUpdate.show(); the real SW update flow and the standalone
display-mode placement above the bottom nav cannot be automated (Playwright
cannot emulate display-mode for @media) and stay manual.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_EXPECTED = {
    "en": ("A new version is available", "Update", "Close"),
    "ru": ("Доступна новая версия", "Обновить", "Закрыть"),
    "he": ("גרסה חדשה זמינה", "עדכון", "סגירה"),
}


@pytest.fixture
def mobile_page(browser, live_server_url):
    ctx = browser.new_context(viewport={"width": 375, "height": 667})
    ctx.route("**/api/analytics/**", lambda route: route.fulfill(status=204))
    page = ctx.new_page()
    page.set_default_timeout(60_000)
    yield page
    ctx.close()


@pytest.mark.parametrize("lang", ["en", "ru", "he"])
def test_banner_renders_accessibly_at_375(mobile_page, live_server_url, lang):
    mobile_page.goto(f"{live_server_url}/about?ui_language={lang}")
    mobile_page.evaluate("window.VerbBoardUpdate.show(); window.VerbBoardUpdate.show()")
    banner = mobile_page.locator("#vb-update-banner")
    assert banner.count() == 1
    text, button, close = _EXPECTED[lang]
    assert banner.get_attribute("role") == "status"
    assert banner.get_attribute("aria-live") == "polite"
    assert banner.locator(".vb-update-text").inner_text() == text
    assert banner.locator("#vb-update-reload").inner_text() == button
    assert banner.locator("#vb-update-dismiss").get_attribute("aria-label") == close
    assert (banner.get_attribute("dir") == "rtl") == (lang == "he")
    for sel in ("#vb-update-reload", "#vb-update-dismiss"):
        box = banner.locator(sel).bounding_box()
        assert box["height"] >= 44 and box["width"] >= 44
    b = banner.bounding_box()
    assert b["x"] >= 0 and b["x"] + b["width"] <= 375
    assert mobile_page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_dismiss_removes_banner(mobile_page, live_server_url):
    mobile_page.goto(f"{live_server_url}/about?ui_language=en")
    mobile_page.evaluate("window.VerbBoardUpdate.show()")
    mobile_page.click("#vb-update-dismiss")
    assert mobile_page.locator("#vb-update-banner").count() == 0
