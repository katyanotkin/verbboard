"""Unit tests: practice-streak pure logic (core/progress/streak.py).

Mirrors the client-side implementation in app/static/streak.js
(window.VerbBoardStreak). The two implementations must never drift -- see
test_streak_js_python_parity below, which runs the same case tables through
Node in a single subprocess and asserts the outputs match Python's.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from core.progress.streak import StreakRecord, is_next_day, merge_streak

REPO_ROOT = Path(__file__).resolve().parent.parent
STREAK_JS = REPO_ROOT / "app" / "static" / "streak.js"


# ---------------------------------------------------------------------------
# is_next_day
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "earlier, later, expected",
    [
        ("2026-07-07", "2026-07-08", True),  # ordinary consecutive days
        ("2026-06-30", "2026-07-01", True),  # month boundary
        ("2026-12-31", "2027-01-01", True),  # year boundary
        ("2028-02-28", "2028-02-29", True),  # leap day
        ("2028-02-29", "2028-03-01", True),  # day after leap day
        ("2027-02-28", "2027-03-01", True),  # non-leap year: Feb 28 -> Mar 1
        ("2026-07-07", "2026-07-07", False),  # same day is not "next"
        ("2026-07-07", "2026-07-09", False),  # gap of 2
        ("2026-07-08", "2026-07-07", False),  # reversed order
        ("2026-07-01", "2026-08-01", False),  # gap spanning a whole month
    ],
)
def test_is_next_day(earlier: str, later: str, expected: bool) -> None:
    assert is_next_day(earlier, later) is expected


# ---------------------------------------------------------------------------
# merge_streak
# ---------------------------------------------------------------------------


def test_merge_both_none_returns_none() -> None:
    assert merge_streak(None, None) is None


def test_merge_a_none_returns_b() -> None:
    b: StreakRecord = {"last_day": "2026-07-01", "len": 4}
    assert merge_streak(None, b) == b


def test_merge_b_none_returns_a() -> None:
    a: StreakRecord = {"last_day": "2026-07-01", "len": 4}
    assert merge_streak(a, None) == a


def test_merge_same_day_keeps_larger_length() -> None:
    a: StreakRecord = {"last_day": "2026-07-01", "len": 2}
    b: StreakRecord = {"last_day": "2026-07-01", "len": 5}
    assert merge_streak(a, b) == {"last_day": "2026-07-01", "len": 5}


def test_merge_same_day_order_independent() -> None:
    a: StreakRecord = {"last_day": "2026-07-01", "len": 5}
    b: StreakRecord = {"last_day": "2026-07-01", "len": 2}
    assert merge_streak(a, b) == merge_streak(b, a) == {"last_day": "2026-07-01", "len": 5}


def test_merge_adjacent_days_extends_when_earlier_plus_one_wins() -> None:
    earlier: StreakRecord = {"last_day": "2026-07-01", "len": 5}
    later: StreakRecord = {"last_day": "2026-07-02", "len": 1}
    # later.len=1 vs earlier.len+1=6 -> earlier+1 wins
    assert merge_streak(earlier, later) == {"last_day": "2026-07-02", "len": 6}


def test_merge_adjacent_days_extends_when_later_len_already_ahead() -> None:
    earlier: StreakRecord = {"last_day": "2026-07-01", "len": 1}
    later: StreakRecord = {"last_day": "2026-07-02", "len": 9}
    # later.len=9 vs earlier.len+1=2 -> later.len wins (no double count)
    assert merge_streak(earlier, later) == {"last_day": "2026-07-02", "len": 9}


def test_merge_adjacent_days_order_independent() -> None:
    a: StreakRecord = {"last_day": "2026-07-01", "len": 5}
    b: StreakRecord = {"last_day": "2026-07-02", "len": 1}
    assert merge_streak(a, b) == merge_streak(b, a) == {"last_day": "2026-07-02", "len": 6}


def test_merge_gap_of_two_days_later_wins_outright() -> None:
    earlier: StreakRecord = {"last_day": "2026-07-01", "len": 30}
    later: StreakRecord = {"last_day": "2026-07-03", "len": 1}
    # streak was broken -- earlier's length is discarded, later wins as-is
    assert merge_streak(earlier, later) == later


def test_merge_gap_order_independent() -> None:
    a: StreakRecord = {"last_day": "2026-07-01", "len": 30}
    b: StreakRecord = {"last_day": "2026-07-03", "len": 1}
    assert merge_streak(a, b) == merge_streak(b, a) == b


def test_merge_month_boundary_is_treated_as_adjacent() -> None:
    earlier: StreakRecord = {"last_day": "2026-06-30", "len": 4}
    later: StreakRecord = {"last_day": "2026-07-01", "len": 1}
    assert merge_streak(earlier, later) == {"last_day": "2026-07-01", "len": 5}


def test_merge_year_boundary_is_treated_as_adjacent() -> None:
    earlier: StreakRecord = {"last_day": "2026-12-31", "len": 4}
    later: StreakRecord = {"last_day": "2027-01-01", "len": 1}
    assert merge_streak(earlier, later) == {"last_day": "2027-01-01", "len": 5}


# ---------------------------------------------------------------------------
# JS/Python parity
# ---------------------------------------------------------------------------

# Shared case table fed through both implementations. Each entry drives one
# assertion in Node and one in Python (below), and both outputs are diffed
# in test_streak_js_python_parity.
_BUMP_CASES = [
    # (rec, today) -> bump result
    (None, "2026-07-08"),  # first-ever
    ({"last_day": "2026-07-08", "len": 3}, "2026-07-08"),  # same day: no-op
    ({"last_day": "2026-07-07", "len": 3}, "2026-07-08"),  # adjacent: increment
    ({"last_day": "2026-07-01", "len": 30}, "2026-07-08"),  # gap: reset to 1
    ({"last_day": "2026-06-30", "len": 3}, "2026-07-01"),  # month boundary bump
    ({"last_day": "2026-12-31", "len": 3}, "2027-01-01"),  # year boundary bump
]

_MERGE_CASES: list[tuple[StreakRecord | None, StreakRecord | None]] = [
    # (a, b) -> merge result
    (None, None),
    (None, {"last_day": "2026-07-01", "len": 4}),
    ({"last_day": "2026-07-01", "len": 4}, None),
    ({"last_day": "2026-07-01", "len": 2}, {"last_day": "2026-07-01", "len": 5}),
    ({"last_day": "2026-07-01", "len": 5}, {"last_day": "2026-07-02", "len": 1}),
    ({"last_day": "2026-07-01", "len": 1}, {"last_day": "2026-07-02", "len": 9}),
    ({"last_day": "2026-07-01", "len": 30}, {"last_day": "2026-07-03", "len": 1}),
    ({"last_day": "2026-06-30", "len": 4}, {"last_day": "2026-07-01", "len": 1}),
    ({"last_day": "2026-12-31", "len": 4}, {"last_day": "2027-01-01", "len": 1}),
    ({"last_day": "2028-02-28", "len": 4}, {"last_day": "2028-02-29", "len": 1}),
    ({"last_day": "2028-02-29", "len": 4}, {"last_day": "2028-03-01", "len": 1}),
]

_DISPLAY_CASES = [
    # (rec, today) -> displayLen result
    (None, "2026-07-08"),
    ({"last_day": "2026-07-08", "len": 7}, "2026-07-08"),  # alive: today
    ({"last_day": "2026-07-07", "len": 7}, "2026-07-08"),  # alive: yesterday
    ({"last_day": "2026-07-06", "len": 7}, "2026-07-08"),  # lapsed: 2+ days
    ({"last_day": "2026-06-30", "len": 7}, "2026-07-01"),  # alive across month boundary
]

_IS_NEXT_DAY_CASES = [
    ("2026-07-07", "2026-07-08", True),
    ("2026-06-30", "2026-07-01", True),
    ("2026-12-31", "2027-01-01", True),
    ("2028-02-28", "2028-02-29", True),
    ("2028-02-29", "2028-03-01", True),
    ("2026-07-07", "2026-07-07", False),
    ("2026-07-07", "2026-07-09", False),
    ("2026-07-08", "2026-07-07", False),
]


def _py_bump(rec, today):
    """Reimplement bump() in Python for parity checking (bump has no server-side
    equivalent -- the server never computes "today" -- so we mirror the JS spec
    directly against merge_streak's building blocks)."""
    if rec is None or not rec.get("last_day"):
        return {"last_day": today, "len": 1}
    if rec["last_day"] == today:
        return rec
    if is_next_day(rec["last_day"], today):
        return {"last_day": today, "len": rec.get("len", 0) + 1}
    return {"last_day": today, "len": 1}


def _py_display_len(rec, today):
    if rec is None or not rec.get("last_day"):
        return 0
    if rec["last_day"] == today:
        return rec.get("len", 0)
    if is_next_day(rec["last_day"], today):
        return rec.get("len", 0)
    return 0


def _python_results() -> dict:
    return {
        "bump": [_py_bump(rec, today) for rec, today in _BUMP_CASES],
        "merge": [merge_streak(a, b) for a, b in _MERGE_CASES],
        "display": [_py_display_len(rec, today) for rec, today in _DISPLAY_CASES],
        "is_next_day": [is_next_day(a, b) for a, b, _ in _IS_NEXT_DAY_CASES],
    }


_NODE_HARNESS = """
global.window = {};
require(process.argv[1]);
const cases = JSON.parse(process.argv[2]);
const S = window.VerbBoardStreak;
const out = {
  bump: cases.bump.map(([rec, today]) => S.bump(rec, today)),
  merge: cases.merge.map(([a, b]) => S.merge(a, b)),
  display: cases.display.map(([rec, today]) => S.displayLen(rec, today)),
  is_next_day: cases.is_next_day.map(([a, b]) => S.isNextDay(a, b)),
};
process.stdout.write(JSON.stringify(out));
"""


def _run_node_harness() -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available in this environment")
    assert node is not None

    payload = {
        "bump": [[rec, today] for rec, today in _BUMP_CASES],
        "merge": [[a, b] for a, b in _MERGE_CASES],
        "display": [[rec, today] for rec, today in _DISPLAY_CASES],
        "is_next_day": [[a, b] for a, b, _ in _IS_NEXT_DAY_CASES],
    }

    result = subprocess.run(
        [node, "-e", _NODE_HARNESS, str(STREAK_JS), json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"node harness failed: {result.stderr}"
    return json.loads(result.stdout)


def test_streak_js_python_parity() -> None:
    """window.VerbBoardStreak (JS) must produce identical output to the Python
    implementation for every case in the shared table. A single Node
    subprocess evaluates all cases at once to keep the suite fast."""
    js_results = _run_node_harness()
    py_results = _python_results()

    assert js_results["bump"] == py_results["bump"]
    assert js_results["merge"] == py_results["merge"]
    assert js_results["display"] == py_results["display"]
    assert js_results["is_next_day"] == py_results["is_next_day"]
