"""Visible, localized sign-in failure message with retry (issue #141).

The Firebase SDK is blocked in the e2e harness, so `window.firebase` is stubbed
with a configurable signInWithPopup rejection. Complements the Node unit tests in
tests/test_signin_error.py.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.e2e

_CONFIG_STUB = """
Object.defineProperty(window, 'FIREBASE_WEB_CONFIG', {
  get: function () { return { apiKey: 'test', projectId: 'test' }; },
  set: function () {},
});
"""

_FIREBASE_STUB = """
window.__popupCalls = 0;
window.__popupErrorCode = __CODE__;
window.__dialogs = [];
window.alert = function (m) { window.__dialogs.push(String(m)); };
window.firebase = {
  initializeApp: function () {},
  auth: function () {
    return {
      onAuthStateChanged: function (cb) { setTimeout(function () { cb(null); }, 0); },
      getRedirectResult: function () { return Promise.resolve({ user: null }); },
      signInWithRedirect: function () { return Promise.resolve(); },
      signInWithPopup: function () {
        window.__popupCalls++;
        var err = new Error('boom'); err.code = window.__popupErrorCode;
        return Promise.reject(err);
      },
    };
  },
};
window.firebase.auth.GoogleAuthProvider = function () { this.setCustomParameters = function () {}; };
"""


def _open(browser, live_server_url, code, url="/feedback?ui_language=en"):
    ctx = browser.new_context()
    failed: list[dict] = []

    def _analytics(route):
        if route.request.url.endswith("/api/analytics/sign_in_failed"):
            failed.append(json.loads(route.request.post_data or "{}"))
        route.fulfill(status=204)

    ctx.route("**/api/analytics/**", _analytics)
    ctx.route("**/api/progress/**", lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
    ctx.route("**/api/preferences**", lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
    page = ctx.new_page()
    page.set_default_timeout(60_000)
    dialogs: list[str] = []
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.route("https://www.gstatic.com/firebasejs/**", lambda r: r.abort())
    page.add_init_script(_CONFIG_STUB)
    page.add_init_script(_FIREBASE_STUB.replace("__CODE__", json.dumps(code)))
    page.goto(f"{live_server_url}{url}")
    page.wait_for_function("window.VerbBoardAuth && window.VerbBoardSignInError")
    return ctx, page, failed, dialogs


def _sign_in(page):
    page.evaluate("window.VerbBoardAuth.signIn().catch(function () {})")


def test_popup_closed_shows_message_with_retry_and_no_alert(browser, live_server_url):
    ctx, page, failed, dialogs = _open(browser, live_server_url, "auth/popup-closed-by-user")
    _sign_in(page)
    page.wait_for_selector("#vb-signin-error")
    assert page.locator("#vb-signin-error button", has_text="Try again").count() == 1
    assert page.locator("#vb-signin-error").get_attribute("role") == "alert"
    assert dialogs == []
    assert page.evaluate("window.__dialogs") == []
    ctx.close()


def test_retry_calls_sign_in_again(browser, live_server_url):
    ctx, page, _, _ = _open(browser, live_server_url, "auth/popup-closed-by-user")
    _sign_in(page)
    page.wait_for_selector("#vb-signin-error")
    assert page.evaluate("window.__popupCalls") == 1
    page.click("#vb-signin-error .vb-update-btn")
    page.wait_for_function("window.__popupCalls === 2")
    # The retry fails again: exactly one message is on screen.
    page.wait_for_selector("#vb-signin-error")
    assert page.locator("#vb-signin-error").count() == 1
    ctx.close()


def test_close_button_dismisses(browser, live_server_url):
    ctx, page, _, _ = _open(browser, live_server_url, "auth/popup-blocked")
    _sign_in(page)
    page.wait_for_selector("#vb-signin-error")
    page.click("#vb-signin-error .vb-update-dismiss")
    page.wait_for_selector("#vb-signin-error", state="detached")
    ctx.close()


def test_cancelled_popup_request_shows_nothing(browser, live_server_url):
    ctx, page, failed, dialogs = _open(browser, live_server_url, "auth/cancelled-popup-request")
    _sign_in(page)
    page.wait_for_function("window.__popupCalls === 1")
    page.wait_for_timeout(300)
    assert page.locator("#vb-signin-error").count() == 0
    assert failed == []
    assert dialogs == []
    ctx.close()


@pytest.mark.parametrize(
    "firebase_code,beacon_code",
    [
        ("auth/popup-closed-by-user", "popup_closed"),
        ("auth/popup-blocked", "popup_blocked"),
        ("auth/network-request-failed", "network"),
        ("auth/internal-error", "other"),
    ],
)
def test_failure_beacon_matches_code(browser, live_server_url, firebase_code, beacon_code):
    ctx, page, failed, _ = _open(browser, live_server_url, firebase_code)
    _sign_in(page)
    page.wait_for_selector("#vb-signin-error")
    page.wait_for_function("true")
    for _ in range(50):
        if failed:
            break
        page.wait_for_timeout(50)
    assert len(failed) == 1
    assert failed[0]["code"] == beacon_code
    assert failed[0]["branch"] == "desktop"
    ctx.close()


def test_message_sits_above_practice_gate_overlay(browser, live_server_url):
    ctx, page, _, _ = _open(
        browser, live_server_url, "auth/popup-closed-by-user", url="/verbs?language=en&ui_language=en"
    )
    page.wait_for_selector("#practice-start")
    page.click("#practice-start")
    page.wait_for_selector("[role=dialog]")
    # The gate CTA signs in; the stub rejects, so the message appears while the gate is open.
    page.click(".practice-gate-cta")
    page.wait_for_selector("#vb-signin-error")
    assert page.locator("[role=dialog]").count() == 1  # gate still open
    box = page.locator("#vb-signin-error").bounding_box()
    assert box is not None
    top_id = page.evaluate(
        "(p) => { const e = document.elementFromPoint(p.x, p.y); "
        "return e && e.closest('#vb-signin-error') ? 'banner' : (e && e.tagName); }",
        {"x": box["x"] + 12, "y": box["y"] + box["height"] / 2},
    )
    assert top_id == "banner"
    ctx.close()
