"""Regression: mobile /verbs sort <select> must not be capped at 130px.

Bug: `.vb-controls-row .vb-sort-select { max-width: 130px; }` (unconditional)
and the `@media (max-width: 480px)` override that lifts the cap
(`max-width: none; flex: 1 1 100%`) have identical specificity (0,2,0), so
CSS source order -- not the media query -- decides the winner at mobile
widths. The override used to sit *before* the unconditional rule in
verbs.css, so the unconditional 130px cap always won even at <=480px,
silently shrinking the sort dropdown to 130px on every mobile viewport
instead of letting it go full-width. Fixed by moving the media-query block
after the unconditional rule. Caught only by an ad-hoc Playwright check
during this session (not a committed test) -- this locks it in.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_MOBILE_VIEWPORT = {"width": 375, "height": 700}
# Comfortably above the old 130px-bug width, comfortably below what a
# full-width select would measure on a 375px viewport (~285px observed).
_MIN_EXPECTED_WIDTH = 200


def test_mobile_sort_select_is_not_capped_at_130px(page, live_server_url):
    page.set_viewport_size(_MOBILE_VIEWPORT)
    page.goto(f"{live_server_url}/verbs?language=es&ui_language=en")
    page.wait_for_load_state("domcontentloaded")

    sort_select = page.locator("#vb-sort")
    sort_select.wait_for(state="visible")
    box = sort_select.bounding_box()
    assert box is not None, "#vb-sort has no bounding box (not rendered?)"

    assert box["width"] > _MIN_EXPECTED_WIDTH, (
        f"#vb-sort width is {box['width']!r}px at 375px viewport; expected > "
        f"{_MIN_EXPECTED_WIDTH}px (full-width). Regression: the mobile "
        "max-width:none override lost to the unconditional 130px cap due to "
        "CSS source order (same specificity, later rule wins)."
    )
