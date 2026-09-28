"""Opt-in signInWithRedirect path on the mobile-browser branch (issue #55).

The Firebase SDK is blocked in the e2e harness (see conftest.py), so a stub
`window.firebase` records which auth methods auth.js calls.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
)

_ANDROID_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36"
)
_ANDROID_WEBVIEW_UA = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36"
)

_FIREBASE_STUB = """
window.__fbCalls = { redirect: 0, popup: 0, getRedirectResult: 0 };
window.__windowOpenCalls = [];
window.open = function (url) { window.__windowOpenCalls.push(url); return null; };
window.firebase = {
  initializeApp: function () {},
  auth: function () {
    return {
      onAuthStateChanged: function (cb) { cb(null); },
      getRedirectResult: function () { window.__fbCalls.getRedirectResult++; return Promise.resolve({ user: null }); },
      signInWithRedirect: function () { window.__fbCalls.redirect++; return Promise.resolve(); },
      signInWithPopup: function () { window.__fbCalls.popup++; return Promise.resolve(); },
    };
  },
};
window.firebase.auth.GoogleAuthProvider = function () {
  this.setCustomParameters = function () {};
};
"""

# Simulates a standalone display-mode (installed PWA / TWA) by stubbing
# matchMedia's '(display-mode: standalone)' query to match. Playwright's
# default context otherwise always reports browser-tab display mode.
_STANDALONE_STUB = """
window.matchMedia = function (query) {
  return {
    matches: query === '(display-mode: standalone)',
    media: query,
    addListener: function () {},
    removeListener: function () {},
    addEventListener: function () {},
    removeEventListener: function () {},
  };
};
"""


def _page_for(browser, user_agent, standalone=False):
    ctx = browser.new_context(user_agent=user_agent)
    ctx.route("**/api/analytics/**", lambda route: route.fulfill(status=204))
    page = ctx.new_page()
    page.set_default_timeout(60_000)
    page.route("https://www.gstatic.com/firebasejs/**", lambda route: route.abort())
    page.add_init_script(_FIREBASE_STUB)
    if standalone:
        page.add_init_script(_STANDALONE_STUB)
    return ctx, page


@pytest.fixture
def mobile_page(browser, live_server_url):
    """iPhone Safari: the redirect flow is NOT the default here (not yet verified on a device)."""
    ctx, page = _page_for(browser, _MOBILE_UA)
    yield page
    ctx.close()


@pytest.fixture
def android_page(browser, live_server_url):
    ctx, page = _page_for(browser, _ANDROID_UA)
    yield page
    ctx.close()


@pytest.fixture
def twa_page(browser, live_server_url):
    """Android Chrome Custom Tab (TWA) reporting display-mode: standalone."""
    ctx, page = _page_for(browser, _ANDROID_UA, standalone=True)
    yield page
    ctx.close()


@pytest.fixture
def ios_standalone_page(browser, live_server_url):
    """iOS 'Add to Home Screen' -- standalone but not Android; must be unaffected."""
    ctx, page = _page_for(browser, _MOBILE_UA, standalone=True)
    yield page
    ctx.close()


@pytest.fixture
def desktop_standalone_page(browser, live_server_url):
    """Desktop-installed PWA -- standalone, non-mobile UA; must be unaffected."""
    ctx, page = _page_for(browser, None, standalone=True)
    yield page
    ctx.close()


def _flag(page):
    return page.evaluate("localStorage.getItem('vb_signin_redirect')")


def test_flag_on_mobile_uses_redirect_not_signin_page(mobile_page, live_server_url):
    mobile_page.goto(f"{live_server_url}/feedback?signin=redirect")
    assert _flag(mobile_page) == "1"
    mobile_page.evaluate("window.VerbBoardAuth.signIn()")
    calls = mobile_page.evaluate("window.__fbCalls")
    assert calls["redirect"] == 1 and calls["popup"] == 0
    assert "/auth/signin" not in mobile_page.url


def test_iphone_default_still_navigates_to_signin_page(mobile_page, live_server_url):
    mobile_page.goto(f"{live_server_url}/feedback")
    assert _flag(mobile_page) is None
    with mobile_page.expect_navigation(url="**/auth/signin?return_to=*"):
        mobile_page.evaluate("window.VerbBoardAuth.signIn()")
    assert "return_to=%2Ffeedback" in mobile_page.url


def test_signin_param_sets_and_clears_flag(mobile_page, live_server_url):
    mobile_page.goto(f"{live_server_url}/feedback?signin=redirect")
    assert _flag(mobile_page) == "1"
    mobile_page.goto(f"{live_server_url}/feedback")
    assert _flag(mobile_page) == "1"  # persists without the param
    mobile_page.goto(f"{live_server_url}/feedback?signin=popup")
    assert _flag(mobile_page) == "0"  # explicit off, distinct from "unset"
    mobile_page.goto(f"{live_server_url}/feedback?signin=default")
    assert _flag(mobile_page) is None


def test_desktop_ignores_flag_and_uses_popup(browser, live_server_url):
    ctx = browser.new_context()
    ctx.route("**/api/analytics/**", lambda route: route.fulfill(status=204))
    page = ctx.new_page()
    page.route("https://www.gstatic.com/firebasejs/**", lambda route: route.abort())
    page.add_init_script(_FIREBASE_STUB)
    page.goto(f"{live_server_url}/feedback?signin=redirect")
    page.evaluate("window.VerbBoardAuth.signIn()")
    calls = page.evaluate("window.__fbCalls")
    assert calls["popup"] == 1 and calls["redirect"] == 0
    ctx.close()


def test_get_redirect_result_called_once_at_init(mobile_page, live_server_url):
    mobile_page.goto(f"{live_server_url}/feedback")
    assert mobile_page.evaluate("window.__fbCalls.getRedirectResult") == 1


def test_android_browser_defaults_to_redirect(android_page, live_server_url):
    android_page.goto(f"{live_server_url}/feedback")
    assert _flag(android_page) is None  # no override needed
    android_page.evaluate("window.VerbBoardAuth.signIn()")
    calls = android_page.evaluate("window.__fbCalls")
    assert calls["redirect"] == 1 and calls["popup"] == 0
    assert "/auth/signin" not in android_page.url


def test_android_can_opt_out_with_signin_popup(android_page, live_server_url):
    android_page.goto(f"{live_server_url}/feedback?signin=popup")
    with android_page.expect_navigation(url="**/auth/signin?return_to=*"):
        android_page.evaluate("window.VerbBoardAuth.signIn()")
    assert android_page.evaluate("window.__fbCalls.redirect") == 0


def test_android_webview_keeps_the_legacy_flow(browser, live_server_url):
    ctx, page = _page_for(browser, _ANDROID_WEBVIEW_UA)
    page.goto(f"{live_server_url}/feedback")
    with page.expect_navigation(url="**/auth/signin?return_to=*"):
        page.evaluate("window.VerbBoardAuth.signIn()")
    ctx.close()


def test_twa_uses_redirect_in_place_not_window_open(twa_page, live_server_url):
    """TWA install (Android UA + display-mode: standalone) must not hit the
    window.open('/auth/signin') popup flow, which reproduces Google's
    "missing initial state" error on real devices."""
    twa_page.goto(f"{live_server_url}/feedback")
    twa_page.evaluate("window.VerbBoardAuth.signIn()")
    calls = twa_page.evaluate("window.__fbCalls")
    opens = twa_page.evaluate("window.__windowOpenCalls")
    assert calls["redirect"] == 1
    assert calls["popup"] == 0
    assert opens == []


def test_ios_standalone_keeps_window_open(ios_standalone_page, live_server_url):
    """iOS 'Add to Home Screen' is standalone but not Android -- must keep the
    existing window.open('/auth/signin') path unchanged."""
    ios_standalone_page.goto(f"{live_server_url}/feedback")
    ios_standalone_page.evaluate("window.VerbBoardAuth.signIn()")
    calls = ios_standalone_page.evaluate("window.__fbCalls")
    opens = ios_standalone_page.evaluate("window.__windowOpenCalls")
    assert calls["redirect"] == 0
    assert calls["popup"] == 0
    assert opens == ["/auth/signin"]


def test_desktop_standalone_keeps_window_open(desktop_standalone_page, live_server_url):
    """Desktop-installed PWA is standalone but not mobile -- must keep the
    existing window.open('/auth/signin') path unchanged."""
    desktop_standalone_page.goto(f"{live_server_url}/feedback")
    desktop_standalone_page.evaluate("window.VerbBoardAuth.signIn()")
    calls = desktop_standalone_page.evaluate("window.__fbCalls")
    opens = desktop_standalone_page.evaluate("window.__windowOpenCalls")
    assert calls["redirect"] == 0
    assert calls["popup"] == 0
    assert opens == ["/auth/signin"]
