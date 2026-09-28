"""Regression: /verbs must render the search row before the heading+filter/
sort row, in DOM order.

This relative order was reshuffled three times in one session
(d24e474 "Rename 'Browse verbs' to 'Filter verbs' and move filter/sort below
search", b210503 "Revert /verbs heading and tab title to plain 'Verbs'
(drop the Filter framing)", 7630e6d "Recombine the Verbs heading with
filter/sort, keep search first") with no test guarding it, so a future edit
could silently flip the order again. `.vb-heading-search-row` (the search
box + search-mode pills) must precede `.vb-controls-row` (the "Verbs"
heading + filter/sort selects) in the DOM -- asserted both via
`compareDocumentPosition` and via a y-coordinate comparison, since the two
rows stack vertically.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def test_search_row_precedes_heading_controls_row_in_dom(page, live_server_url):
    page.goto(f"{live_server_url}/verbs?language=en&ui_language=en")
    page.wait_for_load_state("domcontentloaded")

    search_row = page.locator(".vb-heading-search-row")
    controls_row = page.locator(".vb-controls-row")
    search_row.wait_for(state="attached")
    controls_row.wait_for(state="attached")

    # DOCUMENT_POSITION_FOLLOWING (4) means the controls-row node comes
    # after the search-row node in the DOM.
    follows = page.evaluate(
        """() => {
            const a = document.querySelector('.vb-heading-search-row');
            const b = document.querySelector('.vb-controls-row');
            const rel = a.compareDocumentPosition(b);
            return !!(rel & Node.DOCUMENT_POSITION_FOLLOWING);
        }"""
    )
    assert follows, (
        ".vb-controls-row (heading + filter/sort) must come after "
        ".vb-heading-search-row (search box) in the DOM -- regression: "
        "search must render first."
    )

    search_box = search_row.bounding_box()
    controls_box = controls_row.bounding_box()
    assert search_box is not None and controls_box is not None
    assert search_box["y"] < controls_box["y"], (
        f"search row y={search_box['y']!r} must be above controls row y={controls_box['y']!r} on screen"
    )
