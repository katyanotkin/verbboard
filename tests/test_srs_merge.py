"""Unit tests: spaced-repetition (Leitner box) pure logic (core/progress/models.py).

Mirrors the client-side implementation in app/static/srs.js
(window.VerbBoardSRS). The two implementations must never drift -- see
test_srs_js_python_parity below, which runs a shared case table through
Node in a single subprocess and asserts the outputs match Python's.

Follows the pattern of the now-removed tests/test_streak_merge.py
(streak.py/streak.js parity test) exactly: (1) unit-test the pure Python
function directly, (2) reimplement any JS-only logic as a `_py_*` mirror
for cases with no server-side Python equivalent, (3) run a shared case
table through both a `_python_results()` function and a Node subprocess
harness, then diff the JSON outputs.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from core.progress.models import LEITNER_MAX_BOX, leitner_next_box

REPO_ROOT = Path(__file__).resolve().parent.parent
SRS_JS = REPO_ROOT / "app" / "static" / "srs.js"


# ---------------------------------------------------------------------------
# leitner_next_box (pure Python)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current_box, recalled, expected",
    [
        (0, True, 1),  # never-reviewed verb, recalled -> enters ladder at box 1
        (0, False, 1),  # never-reviewed verb, not recalled -> still box 1 (not 0)
        (1, True, 2),  # ordinary promotion
        (1, False, 1),  # demotion stays at 1 (no-op, already floor)
        (2, False, 1),  # demotion from mid-ladder
        (3, True, 4),  # ordinary promotion
        (4, True, 5),  # promotion into the max box
        (4, False, 1),  # demotion from just below max
        (5, True, 5),  # already maxed, recalled -> capped, does not overflow
        (5, False, 1),  # maxed verb forgotten -> back to box 1, not box 0
    ],
)
def test_leitner_next_box(current_box: int, recalled: bool, expected: int) -> None:
    assert leitner_next_box(current_box, recalled) == expected


def test_leitner_next_box_never_returns_zero() -> None:
    """A reviewed verb must never fall out of the ladder back to box 0,
    regardless of recall outcome or starting box."""
    for box in range(0, LEITNER_MAX_BOX + 1):
        assert leitner_next_box(box, True) >= 1
        assert leitner_next_box(box, False) >= 1


def test_leitner_next_box_never_exceeds_max() -> None:
    for box in range(0, LEITNER_MAX_BOX + 1):
        assert leitner_next_box(box, True) <= LEITNER_MAX_BOX
        assert leitner_next_box(box, False) <= LEITNER_MAX_BOX


def test_leitner_next_box_not_recalled_always_lands_on_one() -> None:
    for box in range(0, LEITNER_MAX_BOX + 1):
        assert leitner_next_box(box, False) == 1


# ---------------------------------------------------------------------------
# mergeFromServer -- last-write-wins-by-reviewed_at merge. No server-side
# Python equivalent exists (this is client-merge-on-hydrate logic only), so
# it's reimplemented here purely for the parity check, mirroring the old
# streak test's _py_bump() precedent for JS-only logic.
# ---------------------------------------------------------------------------


def _py_merge_from_server(local: dict, server_verbs: dict) -> dict:
    merged = {verb_id: dict(entry) for verb_id, entry in local.items()}

    for verb_id, state in (server_verbs or {}).items():
        if not state or not state.get("srs_box"):
            continue

        server_entry = {
            "box": state.get("srs_box"),
            "due_at": state.get("srs_due_at"),
            "reviewed_at": state.get("srs_reviewed_at"),
        }
        local_entry = merged.get(verb_id)

        if not local_entry:
            merged[verb_id] = server_entry
            continue

        # Mirrors srs.js exactly: a falsy reviewed_at (missing/None) is
        # treated as timestamp 0, not skipped/NaN.
        server_time = _parse_iso_ms(server_entry.get("reviewed_at"))
        local_time = _parse_iso_ms(local_entry.get("reviewed_at"))

        if server_time > local_time:
            merged[verb_id] = server_entry
        # else: local is newer or equal -- keep it (tie goes to local).

    return merged


def _parse_iso_ms(value: str | None) -> float:
    if not value:
        return 0
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000


# ---------------------------------------------------------------------------
# JS/Python parity
# ---------------------------------------------------------------------------

_NEXT_BOX_CASES = [
    # (current_box, recalled)
    (0, True),
    (0, False),
    (1, True),
    (1, False),
    (2, True),
    (2, False),
    (3, True),
    (3, False),
    (4, True),
    (4, False),
    (5, True),
    (5, False),
]

_MERGE_CASES: list[tuple[dict, dict]] = [
    # local missing entirely -> take server outright
    (
        {},
        {"v1": {"srs_box": 2, "srs_due_at": "2026-08-02T00:00:00.000Z", "srs_reviewed_at": "2026-08-01T00:00:00.000Z"}},
    ),
    # server has no entry for this verb at all -> local kept untouched
    (
        {"v1": {"box": 3, "due_at": "2026-08-05T00:00:00.000Z", "reviewed_at": "2026-08-04T00:00:00.000Z"}},
        {},
    ),
    # server entry present but srs_box is 0 (not in ladder) -> skipped, local kept
    (
        {"v1": {"box": 3, "due_at": "2026-08-05T00:00:00.000Z", "reviewed_at": "2026-08-04T00:00:00.000Z"}},
        {"v1": {"srs_box": 0, "srs_due_at": None, "srs_reviewed_at": None}},
    ),
    # server strictly newer reviewed_at -> server wins
    (
        {"v1": {"box": 2, "due_at": "L_due", "reviewed_at": "2026-01-01T00:00:00.000Z"}},
        {"v1": {"srs_box": 4, "srs_due_at": "S_due", "srs_reviewed_at": "2026-01-02T00:00:00.000Z"}},
    ),
    # local strictly newer reviewed_at -> local wins (kept)
    (
        {"v1": {"box": 2, "due_at": "L_due", "reviewed_at": "2026-01-05T00:00:00.000Z"}},
        {"v1": {"srs_box": 4, "srs_due_at": "S_due", "srs_reviewed_at": "2026-01-02T00:00:00.000Z"}},
    ),
    # equal timestamps -> tiebreak favors local (code only overwrites on strict >)
    (
        {"v1": {"box": 2, "due_at": "L_due", "reviewed_at": "2026-01-02T00:00:00.000Z"}},
        {"v1": {"srs_box": 4, "srs_due_at": "S_due", "srs_reviewed_at": "2026-01-02T00:00:00.000Z"}},
    ),
    # local entry has no reviewed_at at all (treated as 0) -> server (real timestamp) wins
    (
        {"v1": {"box": 1, "due_at": "L_due"}},
        {"v1": {"srs_box": 2, "srs_due_at": "S_due", "srs_reviewed_at": "2026-01-01T00:00:00.000Z"}},
    ),
    # both sides missing reviewed_at -> both computed as 0 -> tie -> local kept
    (
        {"v1": {"box": 1, "due_at": "L_due"}},
        {"v1": {"srs_box": 2, "srs_due_at": "S_due"}},
    ),
    # multiple verbs in one call, mixed outcomes
    (
        {
            "v1": {"box": 2, "due_at": "L1", "reviewed_at": "2026-01-05T00:00:00.000Z"},
            "v2": {"box": 1, "due_at": "L2", "reviewed_at": "2026-01-01T00:00:00.000Z"},
        },
        {
            "v1": {
                "srs_box": 3,
                "srs_due_at": "S1",
                "srs_reviewed_at": "2026-01-02T00:00:00.000Z",
            },  # older -> local kept
            "v2": {
                "srs_box": 5,
                "srs_due_at": "S2",
                "srs_reviewed_at": "2026-01-09T00:00:00.000Z",
            },  # newer -> server wins
            "v3": {
                "srs_box": 1,
                "srs_due_at": "S3",
                "srs_reviewed_at": "2026-01-01T00:00:00.000Z",
            },  # missing locally -> added
        },
    ),
]


def _python_results() -> dict:
    return {
        "next_box": [leitner_next_box(box, recalled) for box, recalled in _NEXT_BOX_CASES],
        "merge": [_py_merge_from_server(local, server) for local, server in _MERGE_CASES],
    }


_NODE_HARNESS = """
global.window = {
  VerbBoardStorage: {
    readJson: function () { return global.__CURRENT_LOCAL__; },
    writeJson: function () {},
  },
};
require(process.argv[1]);
const cases = JSON.parse(process.argv[2]);
const S = window.VerbBoardSRS;

const nextBoxOut = cases.next_box.map(function (c) { return S.nextBox(c[0], c[1]); });

const mergeOut = cases.merge.map(function (c) {
  global.__CURRENT_LOCAL__ = c[0];
  return S.mergeFromServer('en', c[1]);
});

process.stdout.write(JSON.stringify({ next_box: nextBoxOut, merge: mergeOut }));
"""


def _run_node_harness() -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available in this environment")
    assert node is not None

    payload = {
        "next_box": [[box, recalled] for box, recalled in _NEXT_BOX_CASES],
        "merge": [[local, server] for local, server in _MERGE_CASES],
    }

    result = subprocess.run(
        [node, "-e", _NODE_HARNESS, str(SRS_JS), json.dumps(payload)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"node harness failed: {result.stderr}"
    return json.loads(result.stdout)


def test_srs_js_python_parity() -> None:
    """window.VerbBoardSRS (JS) must produce identical output to the Python
    implementation for every case in the shared table. A single Node
    subprocess evaluates all cases at once to keep the suite fast."""
    js_results = _run_node_harness()
    py_results = _python_results()

    assert js_results["next_box"] == py_results["next_box"]
    assert js_results["merge"] == py_results["merge"]


# ---------------------------------------------------------------------------
# getDueVerbIds -- pure filter over local storage state, no browser API
# dependency beyond window.VerbBoardStorage.readJson. practice_loop.js's
# dueReviewCandidates() (not unit-tested; see report) depends on this
# directly, so it's worth pinning down in isolation via the same Node
# harness style even though it has no Python-side mirror to diff against.
# ---------------------------------------------------------------------------


def test_get_due_verb_ids_filters_by_box_and_due_date() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available in this environment")
    assert node is not None

    local_state = {
        "v_due": {"box": 2, "due_at": "2026-01-01T00:00:00.000Z", "reviewed_at": "2025-12-25T00:00:00.000Z"},
        "v_due_exactly_now": {
            "box": 1,
            "due_at": "2026-01-05T00:00:00.000Z",
            "reviewed_at": "2025-12-30T00:00:00.000Z",
        },
        "v_not_due": {"box": 2, "due_at": "2026-01-10T00:00:00.000Z", "reviewed_at": "2025-12-25T00:00:00.000Z"},
        "v_box_zero": {"box": 0, "due_at": "2025-01-01T00:00:00.000Z", "reviewed_at": "2025-01-01T00:00:00.000Z"},
    }
    now_ms = int(datetime(2026, 1, 5, tzinfo=timezone.utc).timestamp() * 1000)

    harness = """
global.window = {
  VerbBoardStorage: {
    readJson: function () { return JSON.parse(process.argv[3]); },
    writeJson: function () {},
  },
};
require(process.argv[1]);
const nowMs = Number(process.argv[2]);
const S = window.VerbBoardSRS;
const due = S.getDueVerbIds('en', nowMs).sort();
process.stdout.write(JSON.stringify(due));
"""

    result = subprocess.run(
        [node, "-e", harness, str(SRS_JS), str(now_ms), json.dumps(local_state)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"node harness failed: {result.stderr}"
    due_ids = json.loads(result.stdout)

    assert due_ids == ["v_due", "v_due_exactly_now"]
