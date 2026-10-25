"""Regression guards for the auth.js signIn() branches not covered in
test_signin_redirect.py: the exact provider parameters each branch sends, the
analytics branch tag, the GIS opt-in gating and its remaining fallbacks.

Same stubbed-Firebase harness as test_signin_redirect.py (the SDK is blocked
in e2e, so a recording stub stands in for window.firebase).
"""

from __future__ import annotations

import json

import pytest

from tests.e2e.test_signin_redirect import (
    _ANDROID_UA,
    _GIS_STUB,
    _MOBILE_UA,
    _page_for,
)

pytestmark = pytest.mark.e2e

# Wraps the stub provider so every signIn() records the custom parameters it set.
_PARAM_RECORDER = """
window.__providerParams = [];
(function () {
  const Base = window.firebase.auth.GoogleAuthProvider;
  const Wrapped = function () {
    const p = this;
    p.setCustomParameters = function (params) { window.__providerParams.push(params); };
  };
  Wrapped.credential = Base.credential;
  const origAuth = window.firebase.auth;
  window.firebase.auth = origAuth;
  window.firebase.auth.GoogleAuthProvider = Wrapped;
})();
"""


def _recorded_page(browser, user_agent, standalone=False):
    ctx, page = _page_for(browser, user_agent, standalone=standalone)
    page.add_init_script(_PARAM_RECORDER)
    return ctx, page


def _last_params(page):
    return page.evaluate("window.__providerParams[window.__providerParams.length - 1]")


def test_desktop_popup_sends_select_account_and_ui_language_hl(browser, live_server_url):
    ctx, page = _recorded_page(browser, None)
    page.goto(f"{live_server_url}/verbs?language=es&ui_language=ru")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.popup") == 1
    assert _last_params(page) == {"prompt": "select_account", "hl": "ru"}
    ctx.close()


@pytest.mark.parametrize("standalone", [False, True], ids=["android-browser", "twa"])
def test_android_redirect_branches_send_only_select_account(browser, live_server_url, standalone):
    """The 'missing initial state' report: redirect flows must send exactly the
    historical parameter set, no hl."""
    ctx, page = _recorded_page(browser, _ANDROID_UA, standalone=standalone)
    page.goto(f"{live_server_url}/verbs?language=es&ui_language=ru")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    assert _last_params(page) == {"prompt": "select_account"}
    ctx.close()


def _beacon_branch(browser, live_server_url, user_agent, standalone):
    ctx = browser.new_context(user_agent=user_agent)
    bodies: list[str] = []

    def capture(route):
        if route.request.url.endswith("/api/analytics/sign_in_tapped"):
            bodies.append(route.request.post_data or "")
        route.fulfill(status=204)

    ctx.route("**/api/analytics/**", capture)
    page = ctx.new_page()
    page.route("https://www.gstatic.com/firebasejs/**", lambda route: route.abort())
    from tests.e2e.test_signin_redirect import _FIREBASE_STUB, _STANDALONE_STUB

    page.add_init_script(_FIREBASE_STUB)
    if standalone:
        page.add_init_script(_STANDALONE_STUB)
    page.goto(f"{live_server_url}/feedback")
    page.evaluate("window.VerbBoardAuth.signIn()")
    page.wait_for_timeout(300)
    ctx.close()
    assert len(bodies) == 1
    return json.loads(bodies[0])["branch"]


@pytest.mark.parametrize(
    "ua,standalone,expected",
    [
        (None, False, "desktop"),
        (_MOBILE_UA, False, "mobile"),
        (_MOBILE_UA, True, "standalone"),
        (None, True, "standalone"),
        (_ANDROID_UA, True, "twa"),
    ],
    ids=["desktop", "ios-browser", "ios-standalone", "desktop-standalone", "twa"],
)
def test_sign_in_tapped_beacon_reports_branch(browser, live_server_url, ua, standalone, expected):
    assert _beacon_branch(browser, live_server_url, ua, standalone) == expected


def test_concurrent_sign_in_taps_are_ignored(browser, live_server_url):
    ctx, page = _page_for(browser, _ANDROID_UA)
    # A redirect that never settles keeps the first call in flight.
    page.add_init_script(
        "const __a = window.firebase.auth; window.firebase.auth = function () { const x = __a();"
        " x.signInWithRedirect = function () { window.__fbCalls.redirect++; return new Promise(function () {}); };"
        " return x; };"
        "window.firebase.auth.GoogleAuthProvider = __a.GoogleAuthProvider;"
    )
    page.goto(f"{live_server_url}/feedback")
    page.evaluate("window.VerbBoardAuth.signIn(); window.VerbBoardAuth.signIn();")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()


# --- GIS opt-in gating and remaining fallbacks --------------------------------


def _gis_page(browser, user_agent, standalone, mode="credential"):
    ctx, page = _page_for(browser, user_agent, standalone=standalone)
    page.add_init_script(_GIS_STUB)
    page.add_init_script(f"window.__gisMode = '{mode}';")
    return ctx, page


@pytest.mark.parametrize(
    "ua,standalone,expected_redirect",
    [
        (_ANDROID_UA, False, 1),  # Android browser tab: redirect flow, GIS never
        (_MOBILE_UA, True, 0),  # iOS standalone: window.open flow
        (None, False, 0),  # desktop: popup
    ],
    ids=["android-browser", "ios-standalone", "desktop"],
)
def test_gis_flag_only_affects_the_twa_branch(browser, live_server_url, ua, standalone, expected_redirect):
    ctx, page = _gis_page(browser, ua, standalone)
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__gis.prompts") == 0
    assert page.evaluate("window.__fbCalls.redirect") == expected_redirect
    ctx.close()


def test_gis_flag_does_not_touch_redirect_flag_and_vice_versa(browser, live_server_url):
    ctx, page = _page_for(browser, _ANDROID_UA)
    page.goto(f"{live_server_url}/feedback?signin=gis")
    assert page.evaluate("localStorage.getItem('vb_signin_gis')") == "1"
    assert page.evaluate("localStorage.getItem('vb_signin_redirect')") is None
    page.goto(f"{live_server_url}/feedback?signin=popup")
    assert page.evaluate("localStorage.getItem('vb_signin_redirect')") == "0"
    assert page.evaluate("localStorage.getItem('vb_signin_gis')") == "1"  # popup leaves GIS alone
    ctx.close()


def test_gis_credential_rejected_by_firebase_falls_back_to_redirect(browser, live_server_url):
    ctx, page = _gis_page(browser, _ANDROID_UA, True)
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate(
        "const a = firebase.auth; window.firebase.auth = function(){ const x = a();"
        " x.signInWithCredential = function(){ return Promise.reject({code: 'auth/invalid-credential'}); };"
        " return x; };"
        "window.firebase.auth.GoogleAuthProvider = a.GoogleAuthProvider;"
    )
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()


def test_gis_missing_client_id_falls_back_without_prompt(browser, live_server_url):
    ctx, page = _gis_page(browser, _ANDROID_UA, True)
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.FIREBASE_WEB_CONFIG.gisClientId = ''")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__gis.prompts") == 0
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()


def test_gis_script_load_timeout_falls_back(browser, live_server_url):
    ctx, page = _page_for(browser, _ANDROID_UA, standalone=True)
    page.add_init_script("window.__vbGisScriptTimeoutMs = 150;")
    # Never answer: the script request hangs until the timer gives up.
    page.route("https://accounts.google.com/gsi/client", lambda route: None)
    page.goto(f"{live_server_url}/feedback?signin=gis")
    page.evaluate("window.VerbBoardAuth.signIn()")
    assert page.evaluate("window.__fbCalls.redirect") == 1
    ctx.close()
