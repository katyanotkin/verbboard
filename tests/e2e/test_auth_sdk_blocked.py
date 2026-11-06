"""Auth degrades gracefully when the Firebase SDK is blocked (issue #94).

The SDK script is aborted at the network level, as an ad blocker or a flaky connection would. Nothing is stubbed on
the server, so this also runs against a deployed URL.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def _open_blocked(browser, base_url):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(60_000)
    page.route("https://www.gstatic.com/firebasejs/**", lambda route: route.abort())
    errors: list[str] = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(f"{base_url}/verbs?language=en&ui_language=en", wait_until="domcontentloaded")
    page.wait_for_function("window.VerbBoardAuth && window.VerbBoardAuth.ready")
    return ctx, page, errors


def test_ready_resolves_and_sign_in_out_do_not_reject(browser, live_server_url):
    ctx, page, errors = _open_blocked(browser, live_server_url)
    result = page.evaluate(
        """async () => {
          await window.VerbBoardAuth.ready();
          const out = { user: window.VerbBoardAuth.currentUser() };
          try { await window.VerbBoardAuth.signIn(); out.signIn = 'resolved'; } catch (e) { out.signIn = String(e); }
          try { await window.VerbBoardAuth.signOut(); out.signOut = 'resolved'; } catch (e) { out.signOut = String(e); }
          out.nudgeCanSignIn = window.VerbBoardLoginNudge ? window.VerbBoardLoginNudge.canSignIn() : null;
          return out;
        }"""
    )
    assert result["user"] is None
    assert result["signIn"] == "resolved"
    assert result["signOut"] == "resolved"
    assert result["nudgeCanSignIn"] is False
    assert not any("firebase is not defined" in e for e in errors)
    ctx.close()


def test_login_nudge_never_offers_sign_in_without_sdk(browser, live_server_url):
    ctx, page, _ = _open_blocked(browser, live_server_url)
    page.evaluate("localStorage.setItem('login_nudge_score', '500')")
    shown = page.evaluate("window.VerbBoardLoginNudge.shouldShowThresholdCard()")
    assert shown is False
    ctx.close()
