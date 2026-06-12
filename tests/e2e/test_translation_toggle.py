"""E2E tests: inline translation toggle on the learn (board) page.

The toggle button (#toggle-translations) appears when:
  - the verb's language differs from the UI language, AND
  - at least one example sentence has a translation for the current ui_language.

When clicked:
  - `.examples-table` receives the `translations-visible` CSS class
  - the button text switches to the "hide" label
  - a second click removes the class and restores the "show" label

These tests rely on Firestore having a verb with translations.  They skip
gracefully when the toggle button is absent (no translations in this
environment), so they are safe to run locally and in CI without credentials.
"""

from __future__ import annotations

import pytest

# ── helpers ───────────────────────────────────────────────────────────────────

# Try a Russian verb with English UI -- the most likely combination to have
# server-stored translations, since ru+en is the primary translation pair.
_CANDIDATE_URLS = [
    "/learn?language=ru&verb_id=ru_govorit&ui_language=en",
    "/learn?language=ru&verb_id=ru_byt&ui_language=en",
    "/learn?language=he&verb_id=he_lomar&ui_language=en",
]


def _find_learn_page_with_toggle(page, live_server_url: str) -> bool:
    """Navigate through candidate URLs until one shows a toggle button.
    Returns True if a page with a toggle was found, False otherwise.
    """
    for path in _CANDIDATE_URLS:
        page.goto(f"{live_server_url}{path}")
        page.wait_for_load_state("networkidle")
        if page.locator("#toggle-translations").is_visible():
            return True
    return False


# ── toggle interaction ────────────────────────────────────────────────────────


def test_translation_toggle_adds_visible_class_on_first_click(page, live_server_url):
    """Clicking the toggle once must add `translations-visible` to .examples-table.

    This is the class learn.css uses to reveal .example-translation spans.
    Without it, translated example sentences are hidden even though the data
    is present in the DOM.
    """
    if not _find_learn_page_with_toggle(page, live_server_url):
        pytest.skip("No verb with translations found in Firestore — skipping toggle test")

    table = page.locator(".examples-table")
    toggle = page.locator("#toggle-translations")

    # Before click: class must be absent
    has_class_before = table.evaluate("el => el.classList.contains('translations-visible')")
    assert not has_class_before, "translations-visible must be absent before any click"

    toggle.click()
    page.wait_for_timeout(100)

    has_class_after = table.evaluate("el => el.classList.contains('translations-visible')")
    assert has_class_after, "translations-visible must be present after first click"


def test_translation_toggle_removes_visible_class_on_second_click(page, live_server_url):
    """A second click must remove `translations-visible`, hiding translations again."""
    if not _find_learn_page_with_toggle(page, live_server_url):
        pytest.skip("No verb with translations found in Firestore — skipping toggle test")

    table = page.locator(".examples-table")
    toggle = page.locator("#toggle-translations")

    toggle.click()
    page.wait_for_timeout(100)
    assert table.evaluate("el => el.classList.contains('translations-visible')")

    toggle.click()
    page.wait_for_timeout(100)
    assert not table.evaluate(
        "el => el.classList.contains('translations-visible')"
    ), "translations-visible must be removed after second click"


def test_translation_toggle_button_text_updates_on_click(page, live_server_url):
    """Toggle button text must switch between the show/hide labels on each click.

    The button carries data-label-show and data-label-hide attributes; learn.js
    swaps the text content.  If this breaks, the button appears stuck on one label.
    """
    if not _find_learn_page_with_toggle(page, live_server_url):
        pytest.skip("No verb with translations found in Firestore — skipping toggle test")

    toggle = page.locator("#toggle-translations")
    label_show = toggle.get_attribute("data-label-show") or ""
    label_hide = toggle.get_attribute("data-label-hide") or ""

    assert label_show, "data-label-show must be set on the toggle button"
    assert label_hide, "data-label-hide must be set on the toggle button"
    assert label_show != label_hide, "show and hide labels must differ"

    initial_text = toggle.inner_text().strip()
    assert initial_text == label_show, f"Initial button text must be label_show={label_show!r}, got {initial_text!r}"

    toggle.click()
    page.wait_for_timeout(100)
    after_first = toggle.inner_text().strip()
    assert after_first == label_hide, f"After first click text must be label_hide={label_hide!r}, got {after_first!r}"

    toggle.click()
    page.wait_for_timeout(100)
    after_second = toggle.inner_text().strip()
    assert (
        after_second == label_show
    ), f"After second click text must return to label_show={label_show!r}, got {after_second!r}"


def test_toggle_absent_when_ui_language_matches_verb_language(page, live_server_url):
    """When ui_language equals the verb's language, no toggle button should appear.

    Translations are only meaningful when the UI language differs from the verb
    language.  render.py guards this with `board.language != ui_lang`.
    """
    # Study Russian with Russian UI -- no translations needed
    page.goto(f"{live_server_url}/learn?language=ru&verb_id=ru_govorit&ui_language=ru")
    page.wait_for_load_state("networkidle")

    if not page.locator(".conj-table").first.is_visible():
        pytest.skip("ru_govorit not in Firestore — cannot verify toggle absence")

    assert (
        page.locator("#toggle-translations").count() == 0
    ), "Toggle button must be absent when ui_language == verb language"
