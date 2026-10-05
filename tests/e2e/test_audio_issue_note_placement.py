"""The known-audio-issue note is a shared body-level popover, so no table's overflow:hidden clips it.

Flagging needs a confirmed live report, so the test swaps the last form row's report flag for the same
trigger markup core/render.py emits, then checks the real CSS/JS place the note inside the viewport.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

_TRIGGER = (
    "<span class='audio-issue'><button type='button' class='audio-issue-btn' aria-expanded='false' "
    "aria-controls='audio-issue-note' aria-label='Known audio issue' "
    "data-note='Audio is not accurate for this form. Read it instead of listening.'>!</button></span>"
)


@pytest.mark.parametrize("ui_language", ["es", "he"])
@pytest.mark.parametrize("row", ["last_form", "last_example"])
def test_note_box_lies_inside_viewport(page, live_server_url, ui_language, row):
    page.set_viewport_size({"width": 375, "height": 700})
    page.goto(f"{live_server_url}/learn?language=es&verb_id=es_hablar&ui_language={ui_language}")
    page.wait_for_load_state("domcontentloaded")
    selector = ".conj-form .audio-report-btn" if row == "last_form" else ".examples-table .audio-report-btn"
    swapped = page.evaluate(
        """([sel, html]) => {
            const buttons = document.querySelectorAll(sel);
            const btn = buttons[buttons.length - 1];
            if (!btn) return false;
            btn.outerHTML = html;
            return true;
        }""",
        [selector, _TRIGGER],
    )
    assert swapped
    trigger = page.locator(".audio-issue-btn")
    trigger.scroll_into_view_if_needed()
    trigger.click()
    note = page.locator("#audio-issue-note")
    note.wait_for(state="visible")
    box = note.bounding_box()
    vw, vh = 375, 700
    assert box["x"] >= 0 and box["x"] + box["width"] <= vw
    scroll_y = page.evaluate("window.pageYOffset")
    assert box["y"] >= 0 and box["y"] + box["height"] <= vh, scroll_y
    page.keyboard.press("Escape")
    assert note.is_hidden()
