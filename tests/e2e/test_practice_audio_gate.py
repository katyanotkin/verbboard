"""
Practice audio min_plays preference e2e tests.

Covers the audio min_plays preference (`practice_min_plays` localStorage key)
and the Next-button listen gate in learn_practice.js.

TC-A1   practice_min_plays=1: Next enabled after 1 injected play
TC-A4   Audio counter always visible; warn shown when Next clicked without plays

Note: the "Skip & mark as learned" button that used to sit next to Next was
removed entirely (owner decision 2026-09-28) -- its tests (TC-SK1/SK2/SK3)
were removed along with it. Next remains the only advance control for
new-mode verbs and always enforces the listen gate; there is no bypass.
"""

from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.e2e

# ---------------------------------------------------------------------------
# Helpers  (modelled on tests/e2e/test_qatp.py)
# ---------------------------------------------------------------------------


def _inject_audio_plays(page, language: str, verb_ids: list[str], count: int = 5) -> None:
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
    Fetch RU verbs from the verbs page.  Returns (ids, lemmas).
    Skips the test if fewer than `minimum` verbs are available.
    """
    page.goto(f"{live_server_url}/verbs?language=ru")
    page.wait_for_load_state("networkidle")
    verbs = page.evaluate("(window.VB_VERBS || [])")
    if not verbs or len(verbs) < minimum:
        pytest.skip(f"Need at least {minimum} RU verbs; got {len(verbs) if verbs else 0}")
    return [v["id"] for v in verbs[:minimum]], {v["id"]: v["lemma"] for v in verbs[:minimum]}


# ---------------------------------------------------------------------------
# TC-A1  practice_min_plays=1: Next enabled after 1 injected play
# ---------------------------------------------------------------------------


def test_audio_min_plays_1_enables_next(page, live_server_url):
    """With practice_min_plays=1 a single injected play count lets Next navigate."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    # Set practice_min_plays BEFORE navigating to the learn page (read at DOMContentLoaded)
    page.goto(f"{live_server_url}/verbs?language=ru")
    page.wait_for_load_state("networkidle")
    page.evaluate("() => localStorage.setItem('practice_min_plays', '1')")

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    # Inject exactly 1 play for ids[0] -- should satisfy min_plays=1
    _inject_audio_plays(page, "ru", [ids[0]], count=1)

    next_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').first
    next_btn.wait_for(state="visible")
    with page.expect_navigation():
        next_btn.click()
    page.wait_for_load_state("networkidle")

    assert ids[1] in page.url, f"TC-A1: Expected navigation to {ids[1]} after Next with min_plays=1. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-A4  Audio counter always visible; warn shown when Next clicked without plays
# ---------------------------------------------------------------------------


def test_audio_counter_visible_and_warn_on_next(page, live_server_url):
    """The .practice-audio-counter must always show '♪ X / Y'. Clicking Next
    without enough plays shows the listen-warn and stays on the same page."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=2)

    _seed_practice_session(page, "ru", ids[:2], {ids[0]: lemmas[ids[0]], ids[1]: lemmas[ids[1]]})
    page.evaluate("() => localStorage.setItem('practice_min_plays', '5')")

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    counter_el = page.locator(".practice-audio-counter").first
    counter_el.wait_for(state="visible")
    counter_text = counter_el.text_content() or ""
    assert "♪" in counter_text, f"TC-A4: counter must contain '♪'. Got: {counter_text!r}"
    assert "/" in counter_text, f"TC-A4: counter must contain '/'. Got: {counter_text!r}"

    next_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').first
    next_btn.click()

    warn_el = page.locator(".practice-listen-warn").first
    warn_el.wait_for(state="visible")
    assert ids[0] in page.url, f"TC-A4: URL must stay on {ids[0]} after blocked Next. Got: {page.url!r}"
