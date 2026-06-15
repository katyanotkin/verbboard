"""
Practice skip button and audio min_plays preference e2e tests.

Covers new behaviour introduced alongside the Skip button in learn.js and
the audio min_plays preference (`practice_min_plays` localStorage key).

TC-SK1  Skip (middle verb) navigates to next and removes from session
TC-SK2  Skip (sole verb) clears session and returns to /verbs
TC-SK3  Skip marks verb as known
TC-SK4  Skip blocked when not listened (shows warn, stays on page)
TC-SK5  Skip unblocked after injecting enough plays
TC-A1   practice_min_plays=1: Next enabled after 1 injected play
TC-A2   practice_min_plays=all: Next blocked when no srcs heard
TC-A3   practice_min_plays=all: Next enabled when all srcs injected as heard
TC-A4   Audio progress indicator shows "♪ X / Y" on load
"""

from __future__ import annotations

import json

import pytest

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

    # Skip is now audio-gated; inject plays so hasListened() passes.
    _inject_audio_plays(page, "ru", [ids[0]])

    skip_btn = page.locator(".practice-skip-btn").first
    skip_btn.wait_for(state="visible")
    with page.expect_navigation():
        skip_btn.click()
    page.wait_for_load_state("networkidle")

    assert ids[1] in page.url, f"TC-SK1: Expected navigation to {ids[1]} after Skip. Got: {page.url!r}"

    session = _read_session(page, "ru")
    assert session is not None, "TC-SK1: Session must still exist after skipping a non-sole verb"
    assert (
        ids[0] not in session["ids"]
    ), f"TC-SK1: Skipped verb {ids[0]} must be removed from session.ids. Got: {session['ids']!r}"


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

    _inject_audio_plays(page, "ru", [ids[0]])

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

    _inject_audio_plays(page, "ru", [ids[0]])

    skip_btn = page.locator(".practice-skip-btn").first
    skip_btn.wait_for(state="visible")
    with page.expect_navigation():
        skip_btn.click()
    page.wait_for_load_state("networkidle")

    known_list = _read_known(page, "ru")
    assert ids[0] in known_list, f"TC-SK3: Skipped verb {ids[0]} must appear in known:ru. Got: {known_list!r}"


# ---------------------------------------------------------------------------
# TC-SK4  Skip blocked when not listened (shows warn, stays on page)
# ---------------------------------------------------------------------------


def test_skip_blocked_without_audio(page, live_server_url):
    """Clicking Skip without meeting the audio threshold must show the listen-warn
    element and keep the user on the same page."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)
    # _ru_verb_ids already landed on /verbs; set pref without an extra navigation.
    page.evaluate("() => localStorage.setItem('practice_min_plays', '5')")

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    # Do NOT inject audio plays -- hasListened() must return false.
    skip_btn = page.locator(".practice-skip-btn").first
    skip_btn.wait_for(state="visible")
    skip_btn.click()  # no expect_navigation -- should be blocked

    warn_el = page.locator(".practice-listen-warn").first
    warn_el.wait_for(state="visible", timeout=2000)

    assert ids[0] in page.url, f"TC-SK4: URL must still contain {ids[0]} after blocked Skip. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-SK5  Skip unblocked after injecting enough plays
# ---------------------------------------------------------------------------


def test_skip_unblocked_after_audio(page, live_server_url):
    """After injecting enough plays Skip must navigate to the next verb."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)
    page.evaluate("() => localStorage.setItem('practice_min_plays', '5')")

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    _inject_audio_plays(page, "ru", [ids[0]], count=5)

    skip_btn = page.locator(".practice-skip-btn").first
    skip_btn.wait_for(state="visible")
    with page.expect_navigation():
        skip_btn.click()
    page.wait_for_load_state("networkidle")

    assert ids[1] in page.url, f"TC-SK5: Expected navigation to {ids[1]} after Skip with audio. Got: {page.url!r}"


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
# TC-A2  practice_min_plays=all: Next blocked when no srcs heard
# ---------------------------------------------------------------------------


def test_audio_min_plays_all_blocks_next_without_srcs(page, live_server_url):
    """With practice_min_plays=all, clicking Next without any heard srcs must
    show the listen-warn element and stay on the same page."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    page.goto(f"{live_server_url}/verbs?language=ru")
    page.wait_for_load_state("networkidle")
    page.evaluate("() => localStorage.setItem('practice_min_plays', 'all')")

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    # Inject many plays but NO audio_heard_srcs entry
    _inject_audio_plays(page, "ru", [ids[0]], count=100)
    # Make sure audio_heard_srcs is absent for this verb
    page.evaluate("() => localStorage.removeItem('audio_heard_srcs:ru')")

    next_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').first
    next_btn.wait_for(state="visible")
    # Click without expecting navigation -- it should be blocked
    next_btn.click()

    warn_el = page.locator(".practice-listen-warn").first
    warn_el.wait_for(state="visible", timeout=2000)

    assert ids[0] in page.url, f"TC-A2: URL must still contain {ids[0]} after blocked Next. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-A3  practice_min_plays=all: Next enabled when all srcs injected as heard
# ---------------------------------------------------------------------------


def test_audio_min_plays_all_enables_next_with_all_srcs(page, live_server_url):
    """With practice_min_plays=all, injecting all audio srcs as heard allows Next."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=3)

    page.goto(f"{live_server_url}/verbs?language=ru")
    page.wait_for_load_state("networkidle")
    page.evaluate("() => localStorage.setItem('practice_min_plays', 'all')")

    _seed_practice_session(page, "ru", ids, lemmas)

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    # Collect actual audio src values from the rendered page
    audio_srcs = page.evaluate("() => Array.from(document.querySelectorAll('audio')).map(a => a.src).filter(Boolean)")

    if not audio_srcs:
        pytest.skip("TC-A3: No audio elements found on the learn page -- cannot test 'all' mode")

    # Inject heard srcs for ids[0]
    heard_key = "audio_heard_srcs:ru"
    heard_data = {ids[0]: audio_srcs}
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [heard_key, json.dumps(heard_data)])

    # Also inject the stored audio_total so the bar's hasListened() can compare
    total_key = f"audio_total:ru:{ids[0]}"
    page.evaluate(
        "([k, v]) => localStorage.setItem(k, v)",
        [total_key, str(len(audio_srcs))],
    )

    next_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').first
    next_btn.wait_for(state="visible")
    with page.expect_navigation():
        next_btn.click()
    page.wait_for_load_state("networkidle")

    assert (
        ids[1] in page.url
    ), f"TC-A3: Expected navigation to {ids[1]} after Next with all srcs heard. Got: {page.url!r}"


# ---------------------------------------------------------------------------
# TC-A4  Audio progress indicator shows "♪ X / Y" on load
# ---------------------------------------------------------------------------


def test_audio_progress_shown_in_warn(page, live_server_url):
    """Audio count must appear in the warning message when Next is clicked without listening."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=2)

    _seed_practice_session(page, "ru", ids[:2], {ids[0]: lemmas[ids[0]], ids[1]: lemmas[ids[1]]})
    page.evaluate("() => localStorage.setItem('practice_min_plays', '5')")

    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}&return_to=/verbs?language=ru")
    page.wait_for_load_state("networkidle")

    next_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').first
    next_btn.click()

    warn_el = page.locator(".practice-listen-warn").first
    warn_el.wait_for(state="visible")
    text = warn_el.text_content() or ""
    assert "♪" in text, f"TC-A4: warn must contain '♪'. Got: {text!r}"
    assert "/" in text, f"TC-A4: warn must contain '/'. Got: {text!r}"
