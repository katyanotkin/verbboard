"""
Practice skip button and audio min_plays preference e2e tests.

Covers new behaviour introduced alongside the Skip button in learn.js and
the audio min_plays preference (`practice_min_plays` localStorage key).

TC-SK1  Skip (middle verb) navigates to next and removes from session
TC-SK2  Skip (sole verb) clears session and returns to /verbs
TC-SK3  Skip marks verb as known
TC-A1   practice_min_plays=1: Next enabled after 1 injected play
TC-A4   Audio counter always visible; warn shown when Next clicked without plays

Note: Skip has no audio gate -- users may skip freely. The audio gate (Next
button) and badge protection (accomplished check in _finishPractice) are
tested separately.
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


def _read_session(page, language: str):
    """Read the practice session from localStorage; returns None if absent."""
    raw = page.evaluate(
        "([k]) => localStorage.getItem(k)",
        [f"practice_session:{language}"],
    )
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def _read_known(page, language: str) -> list[str]:
    """Read the known set from localStorage; returns an empty list if absent."""
    raw = page.evaluate(
        "([k]) => localStorage.getItem(k)",
        [f"known:{language}"],
    )
    if raw is None:
        return []
    try:
        val = json.loads(raw)
        # VerbBoardStorage stores sets as arrays
        return list(val) if isinstance(val, list) else []
    except Exception:
        return []


# ---------------------------------------------------------------------------
# TC-SK1  Skip (middle verb) navigates to next and removes from session
# ---------------------------------------------------------------------------


def test_skip_middle_navigates_to_next(page, live_server_url):
    """Clicking Skip on a non-last verb navigates to the next verb in the session
    and removes the skipped verb from the session ids."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    _seed_practice_session(page, "ru", ids, lemmas)

    # Navigate to the first verb (index 0, not the last)
    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    skip_btn = page.locator(".practice-skip-btn").first
    skip_btn.wait_for(state="visible")
    with page.expect_navigation():
        skip_btn.click()
    page.wait_for_load_state("networkidle")

    assert ids[1] in page.url, f"TC-SK1: Expected navigation to {ids[1]} after Skip. Got: {page.url!r}"

    session = _read_session(page, "ru")
    assert session is not None, "TC-SK1: Session must still exist after skipping a non-sole verb"
    assert ids[0] not in session["ids"], (
        f"TC-SK1: Skipped verb {ids[0]} must be removed from session.ids. Got: {session['ids']!r}"
    )


# ---------------------------------------------------------------------------
# TC-SK2  Skip (sole verb) clears session and returns to /verbs
# ---------------------------------------------------------------------------


def test_skip_sole_verb_clears_session(page, live_server_url):
    """Clicking Skip when there is only one verb in the session clears the
    practice session and navigates back to /verbs."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=1)
    single_id = ids[:1]
    single_lemmas = {ids[0]: lemmas[ids[0]]}

    _seed_practice_session(page, "ru", single_id, single_lemmas)

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    skip_btn = page.locator(".practice-skip-btn").first
    skip_btn.wait_for(state="visible")
    with page.expect_navigation():
        skip_btn.click()
    page.wait_for_load_state("networkidle")

    assert "/verbs" in page.url, f"TC-SK2: Expected redirect to /verbs after skipping sole verb. Got: {page.url!r}"

    raw_session = page.evaluate(
        "([k]) => localStorage.getItem(k)",
        ["practice_session:ru"],
    )
    assert raw_session is None, f"TC-SK2: practice_session:ru must be null after sole-verb skip. Got: {raw_session!r}"


# ---------------------------------------------------------------------------
# TC-SK3  Skip marks verb as known
# ---------------------------------------------------------------------------


def test_skip_marks_verb_as_known(page, live_server_url):
    """After clicking Skip, the skipped verb id must appear in known:ru."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    # Navigate to the verbs page first so we have a storage origin to clear from
    page.goto(f"{live_server_url}/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    # Ensure known:ru does not contain ids[0] before the test
    page.evaluate("() => localStorage.removeItem('known:ru')")

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    skip_btn = page.locator(".practice-skip-btn").first
    skip_btn.wait_for(state="visible")
    with page.expect_navigation():
        skip_btn.click()
    page.wait_for_load_state("networkidle")

    known_list = _read_known(page, "ru")
    assert ids[0] in known_list, f"TC-SK3: Skipped verb {ids[0]} must appear in known:ru. Got: {known_list!r}"


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
