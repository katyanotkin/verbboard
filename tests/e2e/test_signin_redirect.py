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
    assert len(opens) == 1 and opens[0].startswith("/auth/signin")


def test_desktop_standalone_keeps_window_open(desktop_standalone_page, live_server_url):
    """Desktop-installed PWA is standalone but not mobile -- must keep the
    existing window.open('/auth/signin') path unchanged."""
    desktop_standalone_page.goto(f"{live_server_url}/feedback")
    desktop_standalone_page.evaluate("window.VerbBoardAuth.signIn()")
    calls = desktop_standalone_page.evaluate("window.__fbCalls")
    opens = desktop_standalone_page.evaluate("window.__windowOpenCalls")
    assert calls["redirect"] == 0
    assert calls["popup"] == 0
    assert len(opens) == 1 and opens[0].startswith("/auth/signin")


# --- Opt-in Google Identity Services path on the TWA branch (issue #88) -------

_GIS_STUB = """
window.__gis = { initOpts: null, prompts: 0, credentialCalls: [], signInWithCredential: 0 };
window.google = { accounts: { id: {
  initialize: function (opts) { window.__gis.initOpts = opts; window.__gis.inits = (window.__gis.inits || 0) + 1; },
  cancel: function () { window.__gis.cancels = (window.__gis.cancels || 0) + 1; },
  prompt: function (cb) {
    window.__gis.prompts++;
    if (window.__gisMode === 'credential') {
      window.__gis.initOpts.callback({ credential: 'fake-id-token' });
    } else if (window.__gisMode === 'skipped') {
      cb({ isNotDisplayed: function () { return false; }, isSkippedMoment: function () { return true; },
           getSkippedReason: function () { return 'user_cancel'; }, isDismissedMoment: function () { return false; } });
    } else if (window.__gisMode === 'dismissed') {
      cb({ isNotDisplayed: function () { return false; }, isSkippedMoment: function () { return false; },
           isDismissedMoment: function () { return true; }, getDismissedReason: function () { return 'cancel_called'; } });
    } else if (window.__gisMode === 'not_displayed') {
      cb({ isNotDisplayed: function () { return true; }, getNotDisplayedReason: function () { return 'browser_not_supported'; },
           isSkippedMoment: function () { return false; }, isDismissedMoment: function () { return false; } });
    }
  },
} } };
const __origAuth = window.firebase.auth;
window.firebase.auth = function () {
  const a = __origAuth();
  a.signInWithCredential = function (c) { window.__gis.signInWithCredential++; window.__gis.credentialCalls.push(c); return Promise.resolve(); };
  return a;
};
window.firebase.auth.GoogleAuthProvider = __origAuth.GoogleAuthProvider;
window.firebase.auth.GoogleAuthProvider.credential = function (t) { return { token: t }; };
"""


def _gis_twa_page(browser, mode):
    ctx, page = _page_for(browser, _ANDROID_UA, standalone=True)
    page.add_init_script(_GIS_STUB)
    page.add_init_script(f"window.__gisMode = '{mode}';")
    return ctx, page


def test_gis_flag_param_sets_and_clears(twa_page, live_server_url):
    twa_page.goto(f"{live_server_url}/feedback?signin=gis")
    assert twa_page.evaluate("localStorage.getItem('vb_signin_gis')") == "1"
    twa_page.goto(f"{live_server_url}/feedback?signin=redirect")
    assert twa_page.evaluate("localStorage.getItem('vb_signin_gis')") is None
    twa_page.goto(f"{live_server_url}/feedback?signin=gis")
    twa_page.goto(f"{live_server_url}/feedback?signin=default")
    assert twa_page.evaluate("localStorage.getItem('vb_signin_gis')") is None


def test_gis_flag_on_twa_credential_signs_in_without_redirect(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "credential")
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    gis = page.evaluate("window.__gis")
    assert gis["signInWithCredential"] == 1
    assert gis["credentialCalls"] == [{"token": "fake-id-token"}]
    assert gis["initOpts"]["use_fedcm_for_prompt"] is True
    assert gis["initOpts"]["client_id"].endswith(".apps.googleusercontent.com")
    assert page.evaluate("window.__fbCalls.redirect") == 0
    ctx.close()


def test_gis_not_displayed_falls_back_to_redirect(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "not_displayed")
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__gis.prompts") == 1
    assert page.evaluate("window.__gis.signInWithCredential") == 0
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()


def test_gis_flag_off_twa_keeps_redirect(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "credential")
    page.goto(f"{live_server_url}/feedback")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__gis.prompts") == 0
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()


def test_gis_late_credential_after_fallback_is_ignored(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "not_displayed")
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    page.evaluate("window.__gis.initOpts.callback({ credential: 'late' })")
    assert page.evaluate("window.__gis.signInWithCredential") == 0
    assert page.evaluate("window.__gis.cancels") == 1
    ctx.close()


def test_gis_prompt_timeout_falls_back(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "silent")
    page.add_init_script("window.__vbGisTimeoutMs = 150;")
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()


def test_gis_script_load_failure_falls_back(browser, live_server_url):
    ctx, page = _page_for(browser, _ANDROID_UA, standalone=True)
    page.route("https://accounts.google.com/gsi/client", lambda route: route.abort())
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    assert page.evaluate("document.querySelectorAll('script[src*=\"gsi/client\"]').length") == 0
    ctx.close()


def test_gis_skipped_falls_back(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "skipped")
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()


def test_gis_user_dismissal_does_not_redirect(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "dismissed")
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 0
    assert page.evaluate("window.__gis.signInWithCredential") == 0
    ctx.close()


def test_gis_initialize_once_and_credential_once(browser, live_server_url):
    ctx, page = _gis_twa_page(browser, "credential")
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__gis.inits") == 1
    assert page.evaluate("window.__gis.signInWithCredential") == 2  # one per tap
    ctx.close()
