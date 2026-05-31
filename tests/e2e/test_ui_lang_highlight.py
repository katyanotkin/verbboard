"""
Tests for the UI language globe trigger: highlight logic and dropdown interaction.

Highlight logic (home.js) fires on:
  - First visit (no localStorage flag)
  - Browser locale / VerbBoard UI language mismatch not yet acknowledged

Dropdown interaction:
  - Opens on trigger click
  - Closes on outside click, Escape key
  - Contains all four languages; active one marked with aria-current
"""

from __future__ import annotations

SEEN_KEY = "vb_ui_lang_seen"
HOME_EN = "/?ui_language=en&language=en"


def _trigger_class(page) -> str:
    return page.locator("#ui-lang-trigger").get_attribute("class") or ""


def _wait_for_highlight(page) -> None:
    """Wait for the highlight class -- it may be applied in an async auth.ready() callback."""
    page.wait_for_function(
        "document.getElementById('ui-lang-trigger')?.className.includes('ui-lang-trigger--highlight')"
    )


def _dropdown_hidden(page) -> bool:
    return page.locator("#ui-lang-dropdown[hidden]").count() == 1


def _new_page(browser, locale: str, timeout: int = 8_000):
    ctx = browser.new_context(locale=locale)
    p = ctx.new_page()
    p.set_default_timeout(timeout)
    return ctx, p


# ---------------------------------------------------------------------------
# Highlight: first visit
# ---------------------------------------------------------------------------


def test_highlight_shown_for_new_user_even_when_browser_matches(
    browser, live_server_url
):
    """New user sees the hint once regardless of browser/UI locale match."""
    ctx, page = _new_page(browser, "en-US")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        _wait_for_highlight(page)
        assert "ui-lang-trigger--highlight" in _trigger_class(page)
    finally:
        ctx.close()


def test_highlight_shown_for_new_user_with_mismatch(browser, live_server_url):
    """New user whose browser locale differs from UI lang gets the highlight."""
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        _wait_for_highlight(page)
        assert "ui-lang-trigger--highlight" in _trigger_class(page)
        # Flag is set by animationend (after ~4s) or on explicit dismiss -- not checked here
    finally:
        ctx.close()


def test_hint_text_visible_during_highlight(browser, live_server_url):
    """The question callout is visible while the highlight class is active."""
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        _wait_for_highlight(page)
        assert "ui-lang-trigger--highlight" in _trigger_class(page)
        hint = page.locator(".ui-lang-hint")
        assert hint.is_visible(), "Hint callout should be visible during highlight"
        assert hint.inner_text().strip() != "", "Hint should contain question text"
    finally:
        ctx.close()


def test_hint_close_button_dismisses(browser, live_server_url):
    """× button hides the hint and flags it so it won't reappear."""
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        assert page.locator(".ui-lang-hint").is_visible()
        page.locator("#ui-lang-hint-close").click()
        assert not page.locator(".ui-lang-hint").is_visible()
        seen = page.evaluate(f"localStorage.getItem('{SEEN_KEY}')")
        assert seen == "en_m", f"Expected flag 'en_m' after dismiss, got {seen!r}"
    finally:
        ctx.close()


def test_hint_hidden_after_trigger_click(browser, live_server_url):
    """Clicking the trigger removes the highlight and hides the hint."""
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        assert page.locator(".ui-lang-hint").is_visible()
        page.locator("#ui-lang-trigger").click()
        assert not page.locator(".ui-lang-hint").is_visible()
    finally:
        ctx.close()


def test_highlight_is_visually_distinct(browser, live_server_url):
    """Highlight class must change the button's computed background, not just add a class.

    Guards against CSS ordering bugs where base styles override the modifier.
    """
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        _wait_for_highlight(page)
        assert "ui-lang-trigger--highlight" in _trigger_class(page)
        bg = page.evaluate(
            "getComputedStyle(document.getElementById('ui-lang-trigger')).backgroundColor"
        )
        # #eff6ff = rgb(239, 246, 255) -- must not be plain white rgb(255, 255, 255)
        assert bg != "rgb(255, 255, 255)", (
            f"Highlight class applied but background is still white ({bg!r}); "
            "check CSS rule ordering -- .ui-lang-trigger--highlight must come after "
            ".ui-lang-trigger in the stylesheet"
        )
    finally:
        ctx.close()


def test_no_highlight_for_returning_user_matching_locale(browser, live_server_url):
    """Returning user whose browser locale matches UI lang: no highlight."""
    ctx, page = _new_page(browser, "en-US")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        page.evaluate(f"localStorage.setItem('{SEEN_KEY}', 'en')")
        page.reload()
        assert "ui-lang-trigger--highlight" not in _trigger_class(page)
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# Highlight: browser / UI language mismatch
# ---------------------------------------------------------------------------


def test_highlight_on_locale_mismatch(browser, live_server_url):
    """Browser says Spanish, VerbBoard UI is English: mismatch triggers highlight."""
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        # Simulate returning user who has seen the prompt before (no mismatch marker yet)
        page.evaluate(f"localStorage.setItem('{SEEN_KEY}', 'en')")
        page.reload()
        # Highlight may be applied after auth.ready() resolves -- wait for it
        page.wait_for_function(
            "document.getElementById('ui-lang-trigger')?.className.includes('ui-lang-trigger--highlight')"
        )
        assert "ui-lang-trigger--highlight" in _trigger_class(page)
        # Flag written by explicit dismiss (× button or language pick) -- not checked here
    finally:
        ctx.close()


def test_no_highlight_when_mismatch_already_flagged(browser, live_server_url):
    """Mismatch already acknowledged for this UI lang: no repeat highlight."""
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        page.evaluate(f"localStorage.setItem('{SEEN_KEY}', 'en_m')")
        page.reload()
        assert "ui-lang-trigger--highlight" not in _trigger_class(page)
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# Highlight: click clears it immediately
# ---------------------------------------------------------------------------


def test_clicking_trigger_removes_highlight(browser, live_server_url):
    """Clicking the trigger before animation ends clears the highlight class."""
    ctx, page = _new_page(browser, "es-ES")
    try:
        page.goto(f"{live_server_url}{HOME_EN}")
        _wait_for_highlight(page)
        assert "ui-lang-trigger--highlight" in _trigger_class(page)
        page.locator("#ui-lang-trigger").click()
        assert "ui-lang-trigger--highlight" not in _trigger_class(page)
    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# Dropdown: open / close
# ---------------------------------------------------------------------------


def test_dropdown_opens_on_trigger_click(page, live_server_url):
    """Clicking the globe trigger shows the dropdown."""
    page.goto(f"{live_server_url}{HOME_EN}")
    assert _dropdown_hidden(page), "Dropdown should start hidden"
    page.locator("#ui-lang-trigger").click()
    assert not _dropdown_hidden(page), "Dropdown should be visible after click"


def test_dropdown_closes_on_outside_click(page, live_server_url):
    """Clicking outside the menu closes the dropdown."""
    page.goto(f"{live_server_url}{HOME_EN}")
    page.locator("#ui-lang-trigger").click()
    assert not _dropdown_hidden(page)
    # Dispatch a click on body -- avoids the z-index overlay that covers the h1
    page.evaluate("document.body.click()")
    assert _dropdown_hidden(page), "Dropdown should close on outside click"


def test_dropdown_closes_on_escape(page, live_server_url):
    """Pressing Escape closes the dropdown and returns focus to the trigger."""
    page.goto(f"{live_server_url}{HOME_EN}")
    page.locator("#ui-lang-trigger").click()
    assert not _dropdown_hidden(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(50)
    assert _dropdown_hidden(page), "Dropdown should close on Escape"
    focused_id = page.evaluate("document.activeElement.id")
    assert (
        focused_id == "ui-lang-trigger"
    ), f"Focus should return to trigger, got {focused_id!r}"


def test_dropdown_second_click_closes(page, live_server_url):
    """Clicking the trigger again while open closes the dropdown."""
    page.goto(f"{live_server_url}{HOME_EN}")
    page.locator("#ui-lang-trigger").click()
    assert not _dropdown_hidden(page)
    page.locator("#ui-lang-trigger").click()
    assert _dropdown_hidden(page), "Second trigger click should close dropdown"


# ---------------------------------------------------------------------------
# Dropdown: content
# ---------------------------------------------------------------------------


def test_dropdown_contains_all_language_options(page, live_server_url):
    """Dropdown lists all four UI language options."""
    page.goto(f"{live_server_url}{HOME_EN}")
    page.locator("#ui-lang-trigger").click()
    options = page.locator("#ui-lang-dropdown .ui-lang-option").all()
    codes = {opt.locator(".ui-lang-option-code").inner_text() for opt in options}
    assert codes == {"EN", "RU", "HE", "ES"}, f"Unexpected option codes: {codes}"


def test_active_language_marked_in_dropdown(page, live_server_url):
    """Current UI language has aria-current='true' and a checkmark."""
    page.goto(f"{live_server_url}{HOME_EN}")
    page.locator("#ui-lang-trigger").click()
    active = page.locator("#ui-lang-dropdown .ui-lang-option[aria-current='true']")
    assert active.count() == 1, f"Expected 1 active option, got {active.count()}"
    code = active.locator(".ui-lang-option-code").inner_text()
    assert code == "EN", f"Expected active option to be EN, got {code!r}"
    assert (
        active.locator(".ui-lang-check").count() == 1
    ), "Active option should have checkmark"
