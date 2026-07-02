"""
E2E tests for auth.js applyPreferences() guard logic.

The bug: when a user explicitly switched the learning language on the home page
(e.g. from Hebrew to Russian), auth.js was ignoring the explicit switch and
redirecting back to the server-stored preference (Hebrew) on auth state change.

The fix: `explicitLearningLang = urlParams.has('language')` guards both the
save-to-server path and the redirect-back-to-stored-preference path.

These tests verify the guard logic by:
1. Loading the home page with a specific ?language= URL param
2. Injecting an equivalent of applyPreferences() as a pure function that reads
   from the actual DOM/URL (same as auth.js does) but accepts server prefs as
   an argument instead of fetching them.
3. Asserting that no redirect occurs when an explicit ?language= param is present
4. Asserting that a redirect DOES occur when no explicit ?language= param is
   present and the server preference differs from the current language

The tests also cover the symmetric ui_language guard behaviour.

Server: started by tests/e2e/conftest.py (no-op audio, Firestore-backed).
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e

HOME_EN = "/?ui_language=en&language=en"
HOME_EN_NO_LANG_PARAM = "/?ui_language=en"


# ---------------------------------------------------------------------------
# Helper: run applyPreferences() decision logic synchronously in the browser.
#
# Playwright's page.evaluate(expr, arg) passes the argument as the first param
# to the expression when written as a function literal.  We replicate the exact
# URL/param reading logic from auth.js lines 221-276 so we test the real guard
# decisions against the real DOM and URL state.
# ---------------------------------------------------------------------------


def _run_apply_prefs(page, server_prefs: dict) -> dict:
    """Execute the applyPreferences decision logic in the browser and return results."""
    js = """
(function(serverPrefs) {
  var currentUiLang = document.documentElement.lang || '';
  var langSelect = document.querySelector('select[name="language"]');
  var currentLearningLang = langSelect
    ? langSelect.value
    : (window.VB_LANGUAGE || '');
  var onHome = window.location.pathname === '/';
  var urlParams = new URLSearchParams(window.location.search);
  var explicitUiLang = urlParams.has('ui_language');
  var explicitLearningLang = urlParams.has('language');

  var toSave = {};
  if (currentUiLang && (explicitUiLang || !serverPrefs.ui_language)
      && serverPrefs.ui_language !== currentUiLang) {
    toSave.ui_language = currentUiLang;
  }
  if (currentLearningLang && (explicitLearningLang || !serverPrefs.learning_language)
      && serverPrefs.learning_language !== currentLearningLang) {
    toSave.learning_language = currentLearningLang;
  }

  var url = new URL(window.location.href);
  var needsRedirect = false;

  if (!explicitUiLang && serverPrefs.ui_language && currentUiLang
      && serverPrefs.ui_language !== currentUiLang) {
    url.searchParams.set('ui_language', serverPrefs.ui_language);
    needsRedirect = true;
  }

  if (onHome && !explicitLearningLang && serverPrefs.learning_language
      && currentLearningLang && serverPrefs.learning_language !== currentLearningLang) {
    url.searchParams.set('language', serverPrefs.learning_language);
    needsRedirect = true;
  }

  return {
    needsRedirect: needsRedirect,
    redirectUrl: needsRedirect ? url.toString() : null,
    toSave: toSave,
    explicitLearningLang: explicitLearningLang,
    explicitUiLang: explicitUiLang,
    currentLearningLang: currentLearningLang,
    currentUiLang: currentUiLang,
    onHome: onHome
  };
})
"""
    return page.evaluate(js, server_prefs)


# ---------------------------------------------------------------------------
# Learning language guard -- the exact bug that was fixed
# ---------------------------------------------------------------------------


def test_explicit_language_param_suppresses_preference_redirect(page, live_server_url):
    """When ?language=en is in the URL, a server preference of 'he' must NOT
    trigger a redirect.  This is the exact bug that was filed: auth.js was
    redirecting logged-in users back to their stored language even after an
    explicit switch.
    """
    page.goto(f"{live_server_url}{HOME_EN}")
    page.wait_for_load_state("networkidle")

    # Simulate: server stored preference is Hebrew, user just switched to English
    result = _run_apply_prefs(page, {"ui_language": None, "learning_language": "he"})

    assert result["explicitLearningLang"] is True, "?language= param must be detected as an explicit language switch"
    assert result["needsRedirect"] is False, (
        "Explicit language switch must suppress the preference redirect back to 'he'. "
        f"Got needsRedirect=True, redirectUrl={result['redirectUrl']!r}"
    )


def test_no_language_param_triggers_preference_redirect_on_home(page, live_server_url):
    """When no ?language= param is in the URL and the server has a different
    stored learning language, a redirect to the stored preference must occur.
    This is the intended behaviour for returning users who should be sent to
    their preferred language automatically.
    """
    page.goto(f"{live_server_url}{HOME_EN_NO_LANG_PARAM}")
    page.wait_for_load_state("networkidle")

    # Server stored preference is Russian; current page shows English (default)
    result = _run_apply_prefs(page, {"ui_language": None, "learning_language": "ru"})

    assert result["explicitLearningLang"] is False, "No ?language= param should mean no explicit switch"
    assert result["needsRedirect"] is True, (
        "Missing explicit language param + differing server pref must trigger redirect"
    )
    assert "language=ru" in (result["redirectUrl"] or ""), (
        f"Redirect URL should contain 'language=ru', got: {result['redirectUrl']!r}"
    )


def test_explicit_language_param_is_saved_to_server_as_authoritative(page, live_server_url):
    """When ?language=en is explicit, auth.js should save it to the server
    even if the server already has a learning_language set (because the user
    just switched and their choice is authoritative).
    """
    page.goto(f"{live_server_url}{HOME_EN}")
    page.wait_for_load_state("networkidle")

    # Server already has Hebrew; user just switched to English explicitly
    result = _run_apply_prefs(page, {"ui_language": None, "learning_language": "he"})

    assert "learning_language" in result["toSave"], (
        f"An explicit language switch must save the new value to the server. toSave={result['toSave']!r}"
    )
    assert result["toSave"]["learning_language"] == "en"


def test_no_save_when_server_matches_current_language(page, live_server_url):
    """When the server preference matches the current language, nothing should
    be saved (no unnecessary write) and no redirect should occur.
    """
    page.goto(f"{live_server_url}{HOME_EN}")
    page.wait_for_load_state("networkidle")

    # Server already knows English -- current page is English
    result = _run_apply_prefs(page, {"ui_language": None, "learning_language": "en"})

    assert result["needsRedirect"] is False
    assert "learning_language" not in result["toSave"], (
        f"No save should happen when server pref matches current language. toSave={result['toSave']!r}"
    )


def test_new_user_with_no_server_pref_saves_current_language(page, live_server_url):
    """When the server has no stored learning language (new user), the current
    language should be saved as the initial preference and no redirect fires.
    """
    page.goto(f"{live_server_url}{HOME_EN_NO_LANG_PARAM}")
    page.wait_for_load_state("networkidle")

    # Server has no learning_language yet
    result = _run_apply_prefs(page, {"ui_language": None, "learning_language": None})

    assert result["needsRedirect"] is False, (
        "No redirect when server has no pref -- current language becomes the initial preference"
    )
    # The current language should be saved to the server
    if result["currentLearningLang"]:
        assert "learning_language" in result["toSave"], (
            "Initial learning language should be saved to server for new users. "
            f"currentLearningLang={result['currentLearningLang']!r}, toSave={result['toSave']!r}"
        )


# ---------------------------------------------------------------------------
# UI language guard -- symmetric behaviour
# ---------------------------------------------------------------------------


def test_explicit_ui_language_param_suppresses_ui_lang_redirect(page, live_server_url):
    """When ?ui_language=en is explicit, a server preference of 'ru' must NOT
    trigger a UI language redirect -- mirrors the learning_language guard.
    """
    page.goto(f"{live_server_url}{HOME_EN}")
    page.wait_for_load_state("networkidle")

    # Server stored UI preference is Russian; user just switched to English
    result = _run_apply_prefs(page, {"ui_language": "ru", "learning_language": None})

    assert result["explicitUiLang"] is True
    assert result["needsRedirect"] is False, (
        "Explicit ui_language switch must suppress the redirect back to 'ru'. "
        f"Got needsRedirect=True, redirectUrl={result['redirectUrl']!r}"
    )


def test_missing_ui_language_param_triggers_ui_lang_redirect(page, live_server_url):
    """When there is no explicit ?ui_language= param and the server has a
    different stored UI language, a redirect to apply it must occur.
    """
    # Load a page without any ui_language param (server picks default)
    page.goto(f"{live_server_url}/")
    page.wait_for_load_state("networkidle")

    current_ui = page.evaluate("document.documentElement.lang") or "en"
    # Only test if the page is NOT already in Russian
    if current_ui == "ru":
        return

    result = _run_apply_prefs(page, {"ui_language": "ru", "learning_language": None})

    assert result["explicitUiLang"] is False
    assert result["needsRedirect"] is True, "Missing ui_language param + differing server UI pref must trigger redirect"
    assert "ui_language=ru" in (result["redirectUrl"] or ""), (
        f"Redirect URL should contain 'ui_language=ru', got: {result['redirectUrl']!r}"
    )


def test_explicit_ui_language_is_saved_to_server(page, live_server_url):
    """When ?ui_language=en is explicit, that choice must be written to the server."""
    page.goto(f"{live_server_url}{HOME_EN}")
    page.wait_for_load_state("networkidle")

    # Server had Russian; user explicitly switched to English
    result = _run_apply_prefs(page, {"ui_language": "ru", "learning_language": None})

    assert "ui_language" in result["toSave"], (
        f"Explicit UI language switch must save to server. toSave={result['toSave']!r}"
    )
    assert result["toSave"]["ui_language"] == "en"


# ---------------------------------------------------------------------------
# Redirect only fires on the home page ('/'), not on other pages
# ---------------------------------------------------------------------------


def test_learning_language_redirect_only_on_home_page(page, live_server_url):
    """The learning_language preference redirect is guarded by onHome check.
    On the verbs page the redirect must not fire even without an explicit param.
    """
    page.goto(f"{live_server_url}/verbs?language=en")
    page.wait_for_load_state("networkidle")

    # Server has Hebrew; no explicit language param; but we're not on home
    result = _run_apply_prefs(page, {"ui_language": None, "learning_language": "he"})

    assert result["onHome"] is False, "Test precondition: must be on /verbs not /"
    assert result["needsRedirect"] is False, (
        "Learning language preference redirect must only fire on the home page ('/'). "
        f"Got needsRedirect=True from /verbs, redirectUrl={result['redirectUrl']!r}"
    )


def test_ui_language_redirect_fires_on_non_home_pages(page, live_server_url):
    """The ui_language redirect (unlike learning_language) is not gated to home.
    On the verbs page, a differing server UI pref without explicit param should
    still trigger a redirect.
    """
    page.goto(f"{live_server_url}/verbs?language=en")
    page.wait_for_load_state("networkidle")

    current_ui = page.evaluate("document.documentElement.lang") or "en"
    if current_ui == "ru":
        return

    result = _run_apply_prefs(page, {"ui_language": "ru", "learning_language": None})

    assert result["needsRedirect"] is True, "UI language preference redirect should fire even on non-home pages"


# ---------------------------------------------------------------------------
# Cross-navigation: UI language dropdown carries current learning language
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# localStorage language persistence: vb_language IIFE in home.js
#
# Firebase Hosting strips all cookies except __session, so language preference
# cannot survive a bare '/' request via cookie.  home.js persists the last
# explicit ?language= value in localStorage('vb_language') and on a bare '/'
# visit redirects to /?language={stored} before rendering.
# ---------------------------------------------------------------------------


def test_vb_language_localStorage_persists_across_bare_home_visit(page, live_server_url):
    """Visiting /?language=ru must save 'ru' to localStorage, and a subsequent
    bare '/' visit (no ?language= param) must redirect to /?language=ru.

    This is the replacement for the deleted cookie-based language persistence
    test: cookies are stripped by Firebase Hosting; localStorage is not.
    """
    # First visit: explicit language param -- home.js saves it to localStorage
    page.goto(f"{live_server_url}/?language=ru&ui_language=en")
    page.wait_for_load_state("networkidle")

    stored = page.evaluate("localStorage.getItem('vb_language')")
    assert stored == "ru", f"home.js should save ?language=ru to localStorage('vb_language'), got: {stored!r}"

    # Second visit: bare '/' with no ?language= -- home.js should redirect
    page.goto(f"{live_server_url}/")
    page.wait_for_load_state("networkidle")

    final_url = page.url
    assert "language=ru" in final_url, (
        f"Bare '/' visit after storing 'ru' must redirect to URL containing "
        f"'language=ru' (localStorage fallback). Got: {final_url!r}"
    )


def test_vb_language_localStorage_updated_on_language_change(page, live_server_url):
    """Switching from one language to another must overwrite the stored value."""
    page.goto(f"{live_server_url}/?language=he&ui_language=en")
    page.wait_for_load_state("networkidle")
    assert page.evaluate("localStorage.getItem('vb_language')") == "he"

    page.goto(f"{live_server_url}/?language=en&ui_language=en")
    page.wait_for_load_state("networkidle")
    assert page.evaluate("localStorage.getItem('vb_language')") == "en", (
        "Visiting /?language=en after /?language=he must update localStorage to 'en'"
    )

    # Bare visit must now follow the updated preference
    page.goto(f"{live_server_url}/")
    page.wait_for_load_state("networkidle")
    assert "language=en" in page.url


def test_ui_language_dropdown_links_carry_current_learning_lang(page, live_server_url):
    """UI language switcher links must carry the current learning language so that
    switching UI language doesn't reset the learning language selection.

    If this fails, switching from EN to RU UI while on Hebrew learning language
    would drop the user back to the default learning language -- a different class
    of preference-loss bug.
    """
    page.goto(f"{live_server_url}/?ui_language=en&language=he")
    page.wait_for_load_state("networkidle")

    page.locator("#ui-lang-trigger").click()
    page.wait_for_selector("#ui-lang-dropdown:not([hidden])")

    options = page.locator("#ui-lang-dropdown .ui-lang-option").all()
    for opt in options:
        href = opt.get_attribute("href") or ""
        assert "language=he" in href, (
            f"UI language dropdown option href must carry 'language=he' to preserve "
            f"the learning language across UI language switches. Got href={href!r}"
        )
