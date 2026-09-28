"""Regression: /learn `.topbar-nav`/`.topbar-body` must not overflow their
own box at narrow-but-common widths (issue #62, fixed in 64b139f).

Bug: `.topbar-nav`/`.topbar-body` only wrapped below 374px (a hardcoded
media-query breakpoint). Long RU/ES language-pair labels plus the login
button overflowed horizontally at widths *above* that breakpoint (375,
390, 396, and 409px were all observed overflowing), so real devices at
those widths were never covered. The fix (64b139f) made the flex-wrap
unconditional (a content-fit rule) instead of gated behind
`@media (max-width: 374px)`; this test checks two of those widths (390,
409) as a representative sample -- the fix is width-independent (a
content-fit rule, not another breakpoint), so it isn't sensitive to which
above-374px widths are checked.

Reproducing this needs the real, localized "Login" button mounted in
`.topbar-nav-right` -- without it there isn't enough content to overflow
(confirmed empirically, same finding as
`tests/e2e/test_feedback_mobile_layout.py`, a *different* page's topbar
variant, `.card-nav`, which this test does not cover). auth.js only mounts
that button after Firebase's `onAuthStateChanged` fires, which never
happens in this harness by default (gstatic.com is aborted in
tests/e2e/conftest.py), so each test injects the same minimal
`window.firebase` stub used there.

Verified to actually catch the regression: reverting the CSS fix (restoring
the `@media (max-width: 374px)`-gated wrap) makes `.topbar-nav`'s or
`.topbar-body`'s `scrollWidth` exceed its own `clientWidth` at 375/390/409px
for these combos; with the fix restored, `scrollWidth == clientWidth` at
all three widths.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_VIEWPORT_WIDTHS = [390, 409]

_LEARN_URLS = [
    ("es_ru", "/learn?language=es&verb_id=es_hablar&ui_language=ru"),
    ("ru_en", "/learn?language=ru&verb_id=ru_govorit&ui_language=en"),
]

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


def _box_widths(page, selector: str) -> tuple[int, int] | None:
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            return el ? [el.scrollWidth, el.clientWidth] : null;
        }""",
        selector,
    )


@pytest.mark.parametrize("width", _VIEWPORT_WIDTHS)
@pytest.mark.parametrize("combo_name,path", _LEARN_URLS)
def test_topbar_does_not_overflow_its_own_box(page, live_server_url, combo_name, path, width):
    page.add_init_script(_FIREBASE_STUB)
    page.set_viewport_size({"width": width, "height": 812})
    page.goto(f"{live_server_url}{path}")
    page.wait_for_load_state("domcontentloaded")

    auth_btn = page.locator("#auth-btn")
    auth_btn.wait_for(state="visible")

    for selector in (".topbar-nav", ".topbar-body"):
        locator = page.locator(selector).first
        locator.wait_for(state="attached")
        widths = _box_widths(page, selector)
        assert widths is not None, f"[{combo_name}@{width}px] {selector} not found"
        scroll_width, client_width = widths
        assert scroll_width <= client_width, (
            f"[{combo_name}@{width}px] {selector}.scrollWidth={scroll_width!r} "
            f"exceeds its own clientWidth={client_width!r} -- regression: "
            "content overflowed instead of wrapping (issue #62)."
        )
