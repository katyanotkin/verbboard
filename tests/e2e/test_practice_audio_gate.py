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


def _seed_practice_session(
    page, language: str, ids: list[str], lemmas: dict[str, str], modes: dict[str, str] | None = None
) -> None:
    """Write a practice session into localStorage (skips the Start button flow)."""
    key = f"practice_session:{language}"
    session = {"ids": ids, "lemmas": lemmas, "size": len(ids)}
    if modes:
        session["modes"] = modes
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


# ---------------------------------------------------------------------------
# Finish pill on the last verb of a session
# ---------------------------------------------------------------------------

_LEARN_QS = "&return_to=/verbs?language=ru%26ui_language=en&ui_language=en"


def _open_last_verb(page, live_server_url: str):
    """Seed a 2-verb session with min_plays=1 and open the LAST verb."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=2)
    ids = ids[:2]
    page.evaluate("() => localStorage.setItem('practice_min_plays', '1')")
    _seed_practice_session(page, "ru", ids, {i: lemmas[i] for i in ids})
    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[1]}{_LEARN_QS}")
    page.wait_for_load_state("networkidle")
    return ids


def test_finish_pill_enables_after_audio_goal(page, live_server_url):
    """Last verb shows Finish (aria-disabled until the audio goal is met);
    mid-session verbs still show Next."""
    ids = _open_last_verb(page, live_server_url)

    finish_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Finish"]').first
    finish_btn.wait_for(state="visible")
    assert finish_btn.get_attribute("aria-disabled") == "true"

    # Same trigger the real audio tracker uses: counts in storage + event
    _inject_audio_plays(page, "ru", [ids[1]], count=1)
    page.evaluate("() => window.dispatchEvent(new Event('vb:learn-audio-played'))")
    assert finish_btn.get_attribute("aria-disabled") == "false"

    # A non-last verb keeps the plain Next button and no Finish pill
    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}{_LEARN_QS}")
    page.wait_for_load_state("networkidle")
    assert page.locator('.practice-bar .practice-nav-btn[aria-label="Next"]').count() == 1
    assert page.locator(".practice-bar .practice-nav-btn--finish").count() == 0


def test_finish_without_session_awards_nothing(page, live_server_url):
    """If the session key vanished (e.g. another tab finished it), Finish must
    not write a wrap-up payload and just returns to /verbs."""
    ids = _open_last_verb(page, live_server_url)
    _inject_audio_plays(page, "ru", [ids[1]], count=1)
    # Playwright treats aria-disabled="true" as not clickable, so let the pill sync first
    page.evaluate("() => window.dispatchEvent(new Event('vb:learn-audio-played'))")
    page.evaluate("() => localStorage.removeItem('practice_session:ru')")

    finish_btn = page.locator('.practice-bar .practice-nav-btn[aria-label="Finish"]').first
    finish_btn.wait_for(state="visible")
    with page.expect_navigation(url=lambda u: "/verbs" in u, timeout=15000):
        finish_btn.click()
    page.wait_for_load_state("networkidle")

    assert "/verbs" in page.url
    assert page.evaluate("() => localStorage.getItem('practice_wrapup:ru')") is None


# ---------------------------------------------------------------------------
# Review-mode verbs: ungated recall button plus a listen-gated, SRS-free Next
# ---------------------------------------------------------------------------

_NEXT = '.practice-bar .practice-nav-btn[aria-label="Next"]'
_FINISH = '.practice-bar .practice-nav-btn[aria-label="Finish"]'
_RECALL = ".practice-bar .practice-recall-btn--yes"


def _open_review_verb(page, live_server_url: str, index: int, size: int = 2):
    """Seed a `size`-verb all-review session (min_plays=1) and open verb `index`."""
    ids, lemmas = _ru_verb_ids(page, live_server_url, minimum=size)
    ids = ids[:size]
    page.evaluate("() => localStorage.setItem('practice_min_plays', '1')")
    _seed_practice_session(page, "ru", ids, {i: lemmas[i] for i in ids}, modes={i: "review" for i in ids})
    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[index]}{_LEARN_QS}")
    page.wait_for_load_state("networkidle")
    return ids


def _srs_map(page) -> dict:
    return page.evaluate("() => JSON.parse(localStorage.getItem('srs:ru') || '{}')")


def test_review_verb_has_recall_and_gated_next(page, live_server_url):
    """Review verb shows recall AND Next; Next is listen-gated, recall is not."""
    ids = _open_review_verb(page, live_server_url, 0)
    assert page.locator(_RECALL).count() == 1
    next_btn = page.locator(_NEXT).first
    next_btn.wait_for(state="visible")

    # Before the audio goal: Next must not navigate
    next_btn.dispatch_event("click")
    page.locator(".practice-listen-warn").first.wait_for(state="visible")
    assert ids[0] in page.url

    # Recall navigates with zero listens
    with page.expect_navigation():
        page.locator(_RECALL).first.click()
    page.wait_for_load_state("networkidle")
    assert ids[1] in page.url


def test_review_next_after_goal_writes_no_srs_but_recall_does(page, live_server_url):
    """Next advances without touching SRS; recall writes a box locally."""
    ids = _open_review_verb(page, live_server_url, 0)
    _inject_audio_plays(page, "ru", [ids[0]], count=1)
    with page.expect_navigation():
        page.locator(_NEXT).first.click()
    page.wait_for_load_state("networkidle")
    assert ids[1] in page.url
    assert ids[0] not in _srs_map(page)

    # Recall on the first verb: local SRS write happens before navigation
    page.goto(f"{live_server_url}/learn?language=ru&verb_id={ids[0]}{_LEARN_QS}")
    page.wait_for_load_state("networkidle")
    with page.expect_navigation():
        page.locator(_RECALL).first.click()
    page.wait_for_load_state("networkidle")
    assert _srs_map(page).get(ids[0], {}).get("box", 0) >= 1


def test_last_review_verb_finish_gated_recall_ungated(page, live_server_url):
    """Last review verb: Finish pill disabled until the goal; recall always visible."""
    ids = _open_review_verb(page, live_server_url, 1)
    finish_btn = page.locator(_FINISH).first
    finish_btn.wait_for(state="visible")
    assert finish_btn.get_attribute("aria-disabled") == "true"
    assert page.locator(_RECALL).first.is_visible()
    assert page.locator(_RECALL).first.is_enabled()

    _inject_audio_plays(page, "ru", [ids[1]], count=1)
    page.evaluate("() => window.dispatchEvent(new Event('vb:learn-audio-played'))")
    assert finish_btn.get_attribute("aria-disabled") == "false"
    assert page.locator(_RECALL).first.is_enabled()
