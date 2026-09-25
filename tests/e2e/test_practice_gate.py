"""Sign-in gate on starting a practice session (owner decision 2026-09-25).

The Firebase SDK is blocked in the e2e harness, so each test stubs
`window.firebase` and a `FIREBASE_WEB_CONFIG` (the server renders none locally).
Anonymous -> gate; signed in -> practice starts; no SDK -> fails open.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_CONFIG_STUB = """
Object.defineProperty(window, 'FIREBASE_WEB_CONFIG', {
  get: function () { return { apiKey: 'test', projectId: 'test' }; },
  set: function () {},
});
"""

_FIREBASE_STUB = """
window.__fbCalls = { redirect: 0, popup: 0 };
window.firebase = {
  initializeApp: function () {},
  auth: function () {
    return {
      onAuthStateChanged: function (cb) { setTimeout(function () { cb(__USER__); }, 0); },
      getRedirectResult: function () { return Promise.resolve({ user: null }); },
      signInWithRedirect: function () { window.__fbCalls.redirect++; return Promise.resolve(); },
      signInWithPopup: function () { window.__fbCalls.popup++; return Promise.resolve(); },
    };
  },
};
window.firebase.auth.GoogleAuthProvider = function () { this.setCustomParameters = function () {}; };
"""

_FAKE_USER = "{ uid: 'u1', getIdToken: function () { return Promise.resolve('t'); } }"


def _open(
    browser,
    live_server_url,
    *,
    user=None,
    sdk=True,
    url="/verbs?language=en&ui_language=en",
    viewport=None,
    user_agent=None,
):
    options = {k: v for k, v in {"viewport": viewport, "user_agent": user_agent}.items() if v}
    ctx = browser.new_context(**options)
    beacons: list[str] = []

    def _analytics(route):
        if "practice_event" in route.request.url:
            beacons.append(route.request.post_data or "")
        route.fulfill(status=204)

    ctx.route("**/api/analytics/**", _analytics)
    # Progress/preferences calls made by a signed-in stub must not hit the server.
    ctx.route("**/api/progress/**", lambda route: route.fulfill(status=200, content_type="application/json", body="{}"))
    ctx.route(
        "**/api/preferences**", lambda route: route.fulfill(status=200, content_type="application/json", body="{}")
    )
    page = ctx.new_page()
    page.set_default_timeout(60_000)
    page.route("https://www.gstatic.com/firebasejs/**", lambda route: route.abort())
    if sdk:
        page.add_init_script(_CONFIG_STUB)
        page.add_init_script(_FIREBASE_STUB.replace("__USER__", user or "null"))
    page.goto(f"{live_server_url}{url}")
    page.wait_for_selector("#practice-start")
    return ctx, page, beacons


def _session_keys(page):
    return page.evaluate("Object.keys(localStorage).filter(k => k.startsWith('practice_session:'))")


def test_anonymous_start_shows_gate_and_starts_nothing(browser, live_server_url):
    ctx, page, beacons = _open(browser, live_server_url)
    # Two taps in the same tick must not stack a second modal.
    page.evaluate("const b = document.getElementById('practice-start'); b.click(); b.click();")
    page.wait_for_selector("[role=dialog]")
    assert page.locator("[role=dialog]").count() == 1
    assert page.locator("[role=dialog]").get_attribute("aria-modal") == "true"
    assert "/learn" not in page.url
    assert _session_keys(page) == []
    assert any("gate_shown" in b for b in beacons)
    assert not any('"started"' in b for b in beacons)
    ctx.close()


def test_gate_cta_calls_sign_in(browser, live_server_url):
    ctx, page, _ = _open(browser, live_server_url)
    page.click("#practice-start")
    page.click(".practice-gate-cta")
    page.wait_for_function("window.__fbCalls.popup + window.__fbCalls.redirect >= 1")
    assert _session_keys(page) == []
    ctx.close()


def test_gate_closes_via_escape_and_dismiss_and_reopens(browser, live_server_url):
    ctx, page, _ = _open(browser, live_server_url)
    page.click("#practice-start")
    page.wait_for_selector("[role=dialog]")
    assert page.evaluate("document.activeElement.classList.contains('practice-gate-cta')")
    page.keyboard.press("Escape")
    page.wait_for_selector("[role=dialog]", state="detached")
    assert page.evaluate("document.activeElement.id") == "practice-start"

    page.click("#practice-start")
    page.wait_for_selector("[role=dialog]")
    page.click(".practice-gate-dismiss")
    page.wait_for_selector("[role=dialog]", state="detached")

    page.click("#practice-start")
    page.wait_for_selector("[role=dialog]")
    ctx.close()


def test_signed_in_start_begins_practice(browser, live_server_url):
    ctx, page, _ = _open(browser, live_server_url, user=_FAKE_USER)
    with page.expect_navigation(url="**/learn?*"):
        page.click("#practice-start")
    assert page.locator("[role=dialog]").count() == 0
    ctx.close()


def test_missing_sdk_fails_open(browser, live_server_url):
    ctx, page, _ = _open(browser, live_server_url, sdk=False)
    with page.expect_navigation(url="**/learn?*"):
        page.click("#practice-start")
    ctx.close()


def test_gate_is_rtl_and_fits_375px_in_hebrew(browser, live_server_url):
    ctx, page, _ = _open(
        browser,
        live_server_url,
        url="/verbs?language=es&ui_language=he",
        viewport={"width": 375, "height": 700},
    )
    page.click("#practice-start")
    page.wait_for_selector("[role=dialog]")
    assert page.evaluate("getComputedStyle(document.querySelector('[role=dialog]')).direction") == "rtl"
    box = page.locator("[role=dialog]").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 375
    assert page.locator(".practice-gate-cta").bounding_box()["height"] >= 48
    ctx.close()


def test_gate_closes_and_practice_starts_when_popup_sign_in_completes(browser, live_server_url):
    """Desktop popup sign-in finishes without a page load: auth hydration must
    close the open gate and start the practice the visitor asked for."""
    ctx, page, _ = _open(browser, live_server_url)
    page.click("#practice-start")
    page.wait_for_selector("[role=dialog]")
    with page.expect_navigation(url="**/learn?*"):
        page.evaluate("window.dispatchEvent(new CustomEvent('vb:progress-hydrated'))")  # auth.js dispatches on window
    assert page.locator("[role=dialog]").count() == 0
    ctx.close()


@pytest.mark.parametrize(
    "user_agent",
    [
        "Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 Chrome/126.0 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Instagram 300.0",
        "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/126.0 Mobile Safari/537.36 [FB_IAB/FB4A;FBAV/450.0]",
    ],
)
def test_embedded_in_app_browsers_fail_open(browser, live_server_url, user_agent):
    """Google blocks OAuth in embedded browsers, so a gate there would be a dead end."""
    ctx, page, _ = _open(browser, live_server_url, user_agent=user_agent)
    with page.expect_navigation(url="**/learn?*"):
        page.click("#practice-start")
    ctx.close()
