"""Regression: /feedback topbar (`.card-nav`) must not overflow or overlap at
narrow viewports.

Bug (fixed in 10f18fa): at 375px the "Feedback" h1 crowded the Back/Login
controls in `.topbar-nav`, and in the Spanish locale it pushed the login
button off-screen entirely (real overflow, not just visual crowding -- the
control was unreachable). Fix added flex-wrap/gap/min-width:0/flex-shrink:0
rules scoped to `.card-nav` in feedback.css.

The login button (`#auth-btn`) is mounted client-side by auth.js only after
`firebase.auth().onAuthStateChanged` fires, which never happens in this
harness by default -- gstatic.com is aborted in tests/e2e/conftest.py to
keep networkidle from stalling, so `window.firebase` is undefined and
`initializeFirebase()` throws before mounting anything. Without a login
button in the topbar-nav-right, this test would not reproduce the reported
bug (confirmed empirically: reverting the CSS fix and running against the
Back link alone still passed -- not enough content in the row to overflow).

So each test injects a minimal `window.firebase` stub via
`page.add_init_script` before navigation, standing in for the real Firebase
SDK just enough to make auth.js call `onAuthStateChanged(null)` --> mounts
the real "Login" button with its real localized label/width. This was
verified to reproduce the exact regression: with the CSS fix reverted, the
Spanish "Iniciar sesión" button rendered with its right edge past x=375;
with the fix restored, it stays within bounds.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_VIEWPORT = {"width": 375, "height": 812}

# EN/RU crowded visually; ES was the confirmed real overflow; HE exercises
# the RTL-mirrored layout (flex-direction: row-reverse).
_UI_LANGUAGES = ["en", "ru", "es", "he"]

# Stands in for the real Firebase compat SDK (blocked by conftest.py's
# gstatic.com abort route) just enough that auth.js's initializeFirebase()
# calls onAuthStateChanged(null) synchronously and mounts the real,
# localized "Login" button via mountAuthButton() -- see module docstring.
_FIREBASE_STUB = """
window.firebase = {
  initializeApp: function () {},
  auth: function () {
    return {
      onAuthStateChanged: function (cb) { cb(null); },
    };
  },
};
window.firebase.auth.GoogleAuthProvider = function () {
  this.setCustomParameters = function () {};
};
"""


def _goto_feedback_with_auth_button(page, live_server_url, ui_language):
    page.add_init_script(_FIREBASE_STUB)
    page.set_viewport_size(_VIEWPORT)
    page.goto(f"{live_server_url}/feedback?ui_language={ui_language}")
    page.wait_for_load_state("networkidle")
    auth_btn = page.locator("#auth-btn")
    auth_btn.wait_for(state="visible")
    return auth_btn


@pytest.mark.parametrize("ui_language", _UI_LANGUAGES)
def test_feedback_login_button_stays_within_viewport(page, live_server_url, ui_language):
    """Login button must be fully within the viewport bounds at 375px -- no
    horizontal overflow, in any locale. Direct regression test for the ES
    bug: the login control was pushed entirely off-screen and unreachable."""
    auth_btn = _goto_feedback_with_auth_button(page, live_server_url, ui_language)
    box = auth_btn.bounding_box()
    assert box is not None, "Login button has no bounding box (not rendered?)"

    viewport_width = _VIEWPORT["width"]
    assert box["x"] >= 0, (
        f"[{ui_language}] Login button left edge is off-screen (x={box['x']!r}); "
        "regression: heading pushed the nav-right controls out of the viewport"
    )
    assert box["x"] + box["width"] <= viewport_width, (
        f"[{ui_language}] Login button right edge ({box['x'] + box['width']!r}) exceeds "
        f"viewport width ({viewport_width}); regression: heading pushed the "
        "nav-right controls out of the viewport"
    )


@pytest.mark.parametrize("ui_language", _UI_LANGUAGES)
def test_feedback_back_link_stays_within_viewport(page, live_server_url, ui_language):
    """Back link (server-rendered, always present) must also stay fully
    within the viewport -- a cheaper always-available proxy for the same
    flex-item-squeeze failure mode, independent of the Firebase stub."""
    page.set_viewport_size(_VIEWPORT)
    page.goto(f"{live_server_url}/feedback?ui_language={ui_language}")
    page.wait_for_load_state("networkidle")

    back_link = page.locator(".card-nav .topbar-nav-right a.feedback-link").first
    back_link.wait_for(state="visible")
    box = back_link.bounding_box()
    assert box is not None, "Back link has no bounding box (not rendered?)"

    viewport_width = _VIEWPORT["width"]
    assert box["x"] >= 0, f"[{ui_language}] Back link left edge is off-screen (x={box['x']!r})"
    assert box["x"] + box["width"] <= viewport_width, (
        f"[{ui_language}] Back link right edge ({box['x'] + box['width']!r}) exceeds viewport width ({viewport_width})"
    )


@pytest.mark.parametrize("ui_language", _UI_LANGUAGES)
def test_feedback_heading_does_not_overlap_topbar_controls(page, live_server_url, ui_language):
    """When the heading and nav-right controls (incl. the real login button)
    share a line, they must not overlap horizontally -- the "crowding" half
    of the regression, distinct from the ES off-screen overflow."""
    auth_btn = _goto_feedback_with_auth_button(page, live_server_url, ui_language)

    heading = page.locator(".card-nav h1").first
    nav_right = page.locator(".card-nav .topbar-nav-right").first
    heading.wait_for(state="visible")
    nav_right.wait_for(state="visible")
    assert auth_btn.is_visible()  # login button contributes to nav_right's box

    h_box = heading.bounding_box()
    n_box = nav_right.bounding_box()
    assert h_box is not None and n_box is not None

    # Only meaningful if the two elements share a horizontal line (i.e. did
    # not wrap onto separate rows) -- compare vertical ranges for overlap.
    same_line = h_box["y"] < n_box["y"] + n_box["height"] and n_box["y"] < h_box["y"] + h_box["height"]
    if not same_line:
        pytest.skip(f"[{ui_language}] heading and nav-right wrapped onto separate lines; no overlap possible")

    h_left, h_right = h_box["x"], h_box["x"] + h_box["width"]
    n_left, n_right = n_box["x"], n_box["x"] + n_box["width"]
    overlap = h_left < n_right and n_left < h_right
    assert not overlap, (
        f"[{ui_language}] heading ({h_left:.0f}-{h_right:.0f}) overlaps "
        f"nav-right controls ({n_left:.0f}-{n_right:.0f}) at 375px"
    )
