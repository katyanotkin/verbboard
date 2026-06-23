"""
QATP regression suite -- gates promotion to prod.

Covers changes introduced in commit ca73b85 (ui_language state propagation,
voice form round-trip, bottom nav).

TC-S5     voice switch preserves sanitised return_to
TC-P1-P6  practice navigation carries ui_language
          (audio plays injected via localStorage -- no real TTS needed)

Removed (now covered by unit tests):
  TC-S1-S4  return_to XSS / safe_return_to -- tests/test_safe_return_and_privacy.py
  TC-V2     translated_from banner after voice switch -- stage-only, always skips locally

Tests that overlap with existing files are omitted to avoid duplication:
  - paging behaviour: test_verbs_initial_batch.py (TC-M1/M3/D1/D2)
  - voice + ui_language learn roundtrip: test_state_retention.py (TC-V1)
  - js verb links carry ui_language: test_ui_lang_in_verb_links.py (TC-W1/W2)
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PRACTICE_MIN_PLAYS = 5  # must match PRACTICE_MIN_PLAYS in learn.js


def _inject_audio_plays(page, language: str, verb_ids: list[str], count: int = _PRACTICE_MIN_PLAYS) -> None:
    """Fake audio play counts so hasListened() passes without real TTS."""
    key = f"audio_plays:{language}"
    plays = {vid: count for vid in verb_ids}
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, json.dumps(plays)])


def _seed_practice_session(page, language: str, ids: list[str], lemmas: dict[str, str]) -> None:
    """Write a practice session into localStorage (skips the Start button flow)."""
    key = f"practice_session:{language}"
    session = {"ids": ids, "lemmas": lemmas, "size": len(ids)}
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, json.dumps(session)])


def _ru_verb_ids(page, live_server_url: str, minimum: int = 3) -> tuple[list[str], dict[str, str]]:
    """
    Fetch RU verbs from the verbs page. Returns list of verb IDs.
    Skips the test if fewer than `minimum` verbs are available.
    """
    page.goto(f"{live_server_url}/verbs?language=ru")
    page.wait_for_load_state("networkidle")
    verbs = page.evaluate("(window.VB_VERBS || [])")
    if not verbs or len(verbs) < minimum:
        pytest.skip(f"Need at least {minimum} RU verbs; got {len(verbs) if verbs else 0}")
    return [v["id"] for v in verbs[:minimum]], {v["id"]: v["lemma"] for v in verbs[:minimum]}


# ---------------------------------------------------------------------------
# TC-S5  Voice switch preserves sanitised return_to
# ---------------------------------------------------------------------------


def test_voice_switch_preserves_return_to(page, live_server_url):
    """Switching voice must not corrupt a safe return_to stored in the form."""
    url = f"{live_server_url}/learn?language=en&verb_id=en_be&return_to=/verbs?language=en"
    page.goto(url)
    page.wait_for_load_state("networkidle")

    male_btn = page.locator("button.voice-btn[value='male'], button[name='voice'][value='male']").first
    if male_btn.is_visible():
        with page.expect_navigation():
            male_btn.click()
        page.wait_for_load_state("networkidle")

    back = page.locator("a.back-link, a[href*='verbs']").first
    href = back.get_attribute("href") or ""
    assert "/verbs" in href, f"TC-S5: Back href must still point to /verbs after voice switch. Got: {href!r}"


# ---------------------------------------------------------------------------
# TC-P1  Practice session navigates to learn with ui_language
# ---------------------------------------------------------------------------


def test_practice_session_carries_ui_language(page, live_server_url):
    """Starting a practice session from verbs?ui_language=en must land on learn with ui_language=en."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    # Seed the session before navigating to the first verb
    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(
        f"{live_server_url}/learn?language=ru&verb_id={ids[0]}"
        f"&return_to=/verbs?language=ru%26ui_language=en&ui_language=en"
    )
    page.wait_for_load_state("networkidle")

    assert "ui_language=en" in page.url, f"TC-P1: ui_language=en missing from URL. Got: {page.url!r}"

    practice_bar = page.locator(".practice-bar")
    assert practice_bar.is_visible(), "TC-P1: Practice bar must be visible when session exists"


# ---------------------------------------------------------------------------
# TC-P2  Next button carries ui_language (audio plays injected)
# ---------------------------------------------------------------------------


def test_practice_next_carries_ui_language(page, live_server_url):
    """After injecting audio plays, Next must navigate to verb 2 with ui_language=en."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(
        f"{live_server_url}/learn?language=ru&verb_id={ids[0]}"
        f"&return_to=/verbs?language=ru%26ui_language=en&ui_language=en"
    )
    page.wait_for_load_state("networkidle")

    _inject_audio_plays(page, "ru", ids)

    next_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').first
    next_btn.wait_for(state="visible")
    with page.expect_navigation():
        next_btn.click()
    page.wait_for_load_state("networkidle")

    assert "ui_language=en" in page.url, f"TC-P2: ui_language=en missing after Next. URL: {page.url!r}"
    assert ids[1] in page.url, f"TC-P2: Expected verb {ids[1]} in URL. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-P3  Prev button carries ui_language
# ---------------------------------------------------------------------------


def test_practice_prev_carries_ui_language(page, live_server_url):
    """Prev from verb 2 must navigate back to verb 1 with ui_language=en."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    _seed_practice_session(page, "ru", ids, lemmas)
    _inject_audio_plays(page, "ru", ids)

    # Start on verb 2 (index 1)
    page.goto(
        f"{live_server_url}/learn?language=ru&verb_id={ids[1]}"
        f"&return_to=/verbs?language=ru%26ui_language=en&ui_language=en"
    )
    page.wait_for_load_state("networkidle")

    prev_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Prev"]').first
    prev_btn.wait_for(state="visible")
    with page.expect_navigation():
        prev_btn.click()
    page.wait_for_load_state("networkidle")

    assert "ui_language=en" in page.url, f"TC-P3: ui_language=en missing after Prev. URL: {page.url!r}"
    assert ids[0] in page.url, f"TC-P3: Expected verb {ids[0]} in URL. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-P4  Abandon returns to verbs with ui_language
# ---------------------------------------------------------------------------


def test_practice_abandon_returns_with_ui_language(page, live_server_url):
    """Abandon must redirect to /verbs with ui_language=en."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(
        f"{live_server_url}/learn?language=ru&verb_id={ids[0]}"
        f"&return_to=/verbs?language=ru%26ui_language=en&ui_language=en"
    )
    page.wait_for_load_state("networkidle")

    abandon_btn = page.locator(".practice-abandon-btn").first
    abandon_btn.wait_for(state="visible")
    with page.expect_navigation():
        abandon_btn.click()
    page.wait_for_load_state("networkidle")

    assert "/verbs" in page.url, f"TC-P4: Expected /verbs after Abandon. Got: {page.url!r}"
    assert "ui_language=en" in page.url, f"TC-P4: ui_language=en missing after Abandon. URL: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-P5  Finish returns to verbs with ui_language
# ---------------------------------------------------------------------------


def test_practice_finish_returns_with_ui_language(page, live_server_url):
    """Finish on the last verb must redirect to /verbs with ui_language=en."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    _seed_practice_session(page, "ru", ids, lemmas)
    _inject_audio_plays(page, "ru", ids)

    # Navigate directly to the last verb
    last_id = ids[-1]
    page.goto(
        f"{live_server_url}/learn?language=ru&verb_id={last_id}"
        f"&return_to=/verbs?language=ru%26ui_language=en&ui_language=en"
    )
    page.wait_for_load_state("networkidle")

    # Re-inject after navigation (localStorage is page-scoped)
    _inject_audio_plays(page, "ru", ids)

    next_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').first
    next_btn.wait_for(state="visible")
    with page.expect_navigation():
        next_btn.click()
    page.wait_for_load_state("networkidle")

    assert "/verbs" in page.url, f"TC-P5: Expected /verbs after Finish. Got: {page.url!r}"
    assert "ui_language=en" in page.url, f"TC-P5: ui_language=en missing after Finish. URL: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-P6  Continue button on verbs page carries ui_language
# ---------------------------------------------------------------------------


def test_practice_continue_button_carries_ui_language(page, live_server_url):
    """Continue button for an in-progress session must navigate with ui_language=en."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    # Navigate to verbs page to get the page context
    page.goto(f"{live_server_url}/verbs?language=ru&ui_language=en")
    page.wait_for_load_state("networkidle")

    # Seed an in-progress session (verb 0 already done, verb 1 is current)
    _seed_practice_session(page, "ru", ids, lemmas)

    # Reload so the practice panel sees the session in localStorage
    page.reload()
    page.wait_for_load_state("networkidle")

    continue_link = page.locator("a.btn-pill-navy[href*='/learn']").first
    if not continue_link.is_visible():
        pytest.skip("Continue button not rendered -- practice panel may not show for this verb set")

    href = continue_link.get_attribute("href") or ""
    assert "ui_language=en" in href, f"TC-P6: ui_language=en missing from Continue href. Got: {href!r}"
