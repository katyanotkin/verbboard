"""Unit tests: login-nudge scoring/decision logic (app/static/login_nudge.js).

login_nudge.js is a browser-only IIFE with no server-side Python equivalent
(unlike srs.js's leitner_next_box), so there's nothing to diff against --
this file instead follows the *harness* half of the pattern established by
tests/test_srs_merge.py: a single Node subprocess loads the real JS module
and drives its public API (window.VerbBoardLoginNudge) through a small
sequence of ops, with window/document/localStorage/VerbBoardAuth stubbed.

A hand-rolled localStorage stub is used (rather than relying on Node's own
experimental global localStorage) so behavior is pinned down exactly and
independent of Node version, matching the explicit-stubbing style already
used for window.VerbBoardStorage in test_srs_merge.py.

Two extra ops beyond plain get/call/set exist because the module under test
keeps one piece of state in a closure variable (`shownThisPageLoad`), not in
localStorage, and that variable is documented to reset "naturally on every
navigation/reload":
  - "reset"  -- clears the fake localStorage *and* reloads the module, i.e.
               simulates a brand-new anonymous browser session.
  - "reload" -- reloads the module only (localStorage persists), i.e.
               simulates a page navigation/reload within the same session.
Reloading is implemented by evicting the module from Node's require cache
and re-requiring it, since plain `require()` would otherwise return the
already-cached (and already-mutated) module.

Not covered here: whenAuthReady() (a DOMContentLoaded/auth.js timing
helper, not scoring logic -- would need a jsdom-style environment to test
meaningfully) and buildCta()/markDismissed()'s DOM/event-listener wiring.
Both are exercised indirectly by the e2e-less integration of learn.js /
learn_practice.js / practice_loop.js, which is out of scope for a pure-JS
unit harness.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
LOGIN_NUDGE_JS = REPO_ROOT / "app" / "static" / "login_nudge.js"

_HARNESS = r"""
'use strict';

global.__store = {};
global.localStorage = {
  getItem: function (key) {
    return Object.prototype.hasOwnProperty.call(global.__store, key)
      ? global.__store[key]
      : null;
  },
  setItem: function (key, value) {
    global.__store[key] = String(value);
  },
  removeItem: function (key) {
    delete global.__store[key];
  },
};

let __anonymous = true;
global.window = {
  VerbBoardAuth: {
    currentUser: function () {
      return __anonymous ? null : { uid: 'test-uid' };
    },
    ready: function () {
      return Promise.resolve();
    },
  },
};
global.document = {
  readyState: 'complete',
  addEventListener: function () {},
};

const modulePath = process.argv[1];

function loadModule() {
  delete require.cache[require.resolve(modulePath)];
  require(modulePath);
  return global.window.VerbBoardLoginNudge;
}

let NUDGE = loadModule();

const ops = JSON.parse(process.argv[2]);
const results = [];

for (const op of ops) {
  const kind = op[0];
  if (kind === 'reset') {
    global.__store = {};
    __anonymous = true;
    NUDGE = loadModule();
    results.push(null);
  } else if (kind === 'reload') {
    NUDGE = loadModule();
    results.push(null);
  } else if (kind === 'setAnonymous') {
    __anonymous = !!op[1];
    results.push(null);
  } else if (kind === 'call') {
    const fn = NUDGE[op[1]];
    const args = op.slice(2);
    const ret = fn.apply(NUDGE, args);
    results.push(ret === undefined ? null : ret);
  } else if (kind === 'getItem') {
    results.push(global.localStorage.getItem(op[1]));
  } else if (kind === 'setItem') {
    global.localStorage.setItem(op[1], op[2]);
    results.push(null);
  } else {
    throw new Error('unknown op: ' + kind);
  }
}

process.stdout.write(JSON.stringify(results));
"""


def _run_ops(ops: list) -> list:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available in this environment")
    assert node is not None

    result = subprocess.run(
        [node, "-e", _HARNESS, str(LOGIN_NUDGE_JS), json.dumps(ops)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"node harness failed: {result.stderr}"
    return json.loads(result.stdout)


# ---------------------------------------------------------------------------
# 1. Score accumulation: view=+1, known=+3, badge=+10, and composition.
# ---------------------------------------------------------------------------


def test_score_accumulates_across_signal_types() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["call", "recordVerbView"],  # 0 -> 1
            ["call", "recordVerbView"],  # 1 -> 2
            ["call", "recordVerbView"],  # 2 -> 3
            ["call", "recordKnownMarked"],  # 3 -> 6 (3 views + 1 known)
        ]
    )
    assert results == [None, 1, 2, 3, 6]


def test_badge_earned_adds_ten_and_returns_show_decision() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["call", "recordVerbView"],  # -> 1
            ["call", "recordKnownMarked"],  # -> 4
            ["call", "recordBadgeEarned"],  # -> 14, should show (True)
            ["getItem", "login_nudge_score"],
        ]
    )
    assert results[1] == 1
    assert results[2] == 4
    assert results[3] is True
    assert results[4] == "14"


# ---------------------------------------------------------------------------
# 2. Lifetime cap: once shows_count reaches 5, neither recordBadgeEarned()'s
#    immediate-show nor shouldShowThresholdCard() fire again, regardless of
#    score.
# ---------------------------------------------------------------------------


def test_lifetime_cap_blocks_both_surfaces_regardless_of_score() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["setItem", "login_nudge_shows_count", "5"],
            ["setItem", "login_nudge_score", "500"],  # far past threshold
            ["reload"],  # fresh page load: shownThisPageLoad is not the blocker
            ["call", "shouldShowThresholdCard"],
            ["call", "recordBadgeEarned"],
            ["getItem", "login_nudge_score"],  # bump still records the signal
        ]
    )
    assert results[4] is False, "threshold card must not show once lifetime cap is hit"
    assert results[5] is False, "badge-earned must not show once lifetime cap is hit"
    assert results[6] == "510", "score still accumulates even when capped"


def test_lifetime_cap_boundary_at_exactly_five() -> None:
    # 4 shows so far -- cap not yet reached -- badge-earned should still fire.
    results = _run_ops(
        [
            ["reset"],
            ["setItem", "login_nudge_shows_count", "4"],
            ["reload"],
            ["call", "recordBadgeEarned"],
        ]
    )
    assert results[3] is True


# ---------------------------------------------------------------------------
# 3. Badge bypasses the dismiss-cooldown but still respects the lifetime cap.
# ---------------------------------------------------------------------------


def test_badge_earned_bypasses_dismissal_cooldown() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["setItem", "login_nudge_score", "20"],
            ["call", "markDismissed"],  # dismissed_at_score := 20
            ["getItem", "login_nudge_dismissed_at_score"],
            # Cooldown requires score >= 40 for the threshold card -- confirm
            # the threshold card itself stays quiet (isolating the cooldown).
            ["call", "shouldShowThresholdCard"],
            # ...but a badge earned moments later still fires immediately.
            ["call", "recordBadgeEarned"],
            ["getItem", "login_nudge_score"],
        ]
    )
    assert results[3] == "20"
    assert results[4] is False, "threshold card respects cooldown"
    assert results[5] is True, "badge-earned ignores the dismissal cooldown"
    assert results[6] == "30"


def test_badge_earned_still_blocked_by_lifetime_cap_even_during_cooldown() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["setItem", "login_nudge_score", "20"],
            ["call", "markDismissed"],
            ["setItem", "login_nudge_shows_count", "5"],
            ["reload"],
            ["call", "recordBadgeEarned"],
        ]
    )
    assert results[5] is False


# ---------------------------------------------------------------------------
# 4. Threshold card respects the dismiss-cooldown: after a dismissal at
#    score N, it doesn't reappear until score reaches roughly 2N.
# ---------------------------------------------------------------------------


def test_threshold_card_cooldown_requires_roughly_double_the_dismissed_score() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["setItem", "login_nudge_score", "12"],
            ["call", "shouldShowThresholdCard"],  # eligible pre-dismissal
            ["call", "markShown"],
            ["call", "markDismissed"],  # dismissed_at_score := 12
            ["reload"],  # new page load -- shownThisPageLoad no longer a factor
            ["call", "shouldShowThresholdCard"],  # score 12 < 24 -- still cooling down
            ["setItem", "login_nudge_score", "23"],
            ["call", "shouldShowThresholdCard"],  # 23 < 24 -- still cooling down
            ["setItem", "login_nudge_score", "24"],
            ["call", "shouldShowThresholdCard"],  # 24 >= 24 -- cooldown cleared
        ]
    )
    assert results[2] is True
    assert results[6] is False
    assert results[8] is False
    assert results[10] is True


def test_threshold_card_never_fires_below_threshold_even_without_prior_dismissal() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["setItem", "login_nudge_score", "11"],
            ["call", "shouldShowThresholdCard"],
        ]
    )
    assert results[2] is False


# ---------------------------------------------------------------------------
# 5. reserveThisPageLoad() vs markShown(): reserving blocks a second surface
#    on the same page load without bumping the lifetime shows_count counter;
#    only an actual render via markShown() bumps it.
# ---------------------------------------------------------------------------


def test_reserve_blocks_same_page_load_without_bumping_lifetime_counter() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["call", "reserveThisPageLoad"],
            ["getItem", "login_nudge_shows_count"],  # untouched by reserve
            ["setItem", "login_nudge_score", "12"],
            ["call", "shouldShowThresholdCard"],  # blocked: slot already reserved
            ["call", "markShown"],
            ["getItem", "login_nudge_shows_count"],  # now bumped by the real render
        ]
    )
    assert results[2] is None, "reserveThisPageLoad must not touch the lifetime counter"
    assert results[4] is False, "a reserved slot blocks a second surface same page load"
    assert results[6] == "1"


def test_reservation_does_not_survive_a_reload() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["call", "reserveThisPageLoad"],
            ["setItem", "login_nudge_score", "12"],
            ["reload"],  # simulates navigating to a new page
            ["call", "shouldShowThresholdCard"],  # slot is free again on the new page load
        ]
    )
    assert results[4] is True


def test_mark_shown_alone_bumps_counter_and_reserves_slot() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["getItem", "login_nudge_shows_count"],
            ["call", "markShown"],
            ["getItem", "login_nudge_shows_count"],
            ["setItem", "login_nudge_score", "12"],
            ["call", "shouldShowThresholdCard"],  # same page load, already shown
        ]
    )
    assert results[1] is None
    assert results[3] == "1"
    assert results[5] is False


# ---------------------------------------------------------------------------
# 6. Anonymous-only: with a mocked VerbBoardAuth.currentUser() returning a
#    truthy user, isAnonymous() is false and nothing increments/shows.
# ---------------------------------------------------------------------------


def test_signed_in_user_is_not_anonymous_and_accrues_nothing() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["setAnonymous", False],
            ["call", "isAnonymous"],
            ["call", "recordVerbView"],
            ["call", "recordKnownMarked"],
            ["call", "recordBadgeEarned"],
            ["getItem", "login_nudge_score"],
        ]
    )
    assert results[2] is False
    assert results[3] == 0
    assert results[4] == 0
    assert results[5] is False
    assert results[6] is None, "no score should ever be written for a signed-in user"


def test_signed_in_user_never_sees_threshold_card_even_with_leftover_score() -> None:
    # Simulates a user who accrued anonymous score, then signed in without a
    # page reload -- the live isAnonymous() check must still win.
    results = _run_ops(
        [
            ["reset"],
            ["setItem", "login_nudge_score", "100"],
            ["setAnonymous", False],
            ["call", "shouldShowThresholdCard"],
        ]
    )
    assert results[3] is False


def test_anonymous_user_is_unaffected_by_isAnonymous_check() -> None:
    results = _run_ops(
        [
            ["reset"],
            ["setAnonymous", True],
            ["call", "isAnonymous"],
        ]
    )
    assert results[2] is True
