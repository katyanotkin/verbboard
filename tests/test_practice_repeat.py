"""Unit tests: repeat-quota selection for seen-but-not-known verbs (issue #19).

`pickRepeatCandidates` in app/static/practice_loop.js is a pure function
exported on window.VerbBoardPracticeLoop. Same harness idea as
tests/test_srs_merge.py: one Node subprocess loads the real JS file with a
stubbed `window` and returns JSON, so nothing here re-implements the logic.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PRACTICE_LOOP_JS = REPO_ROOT / "app" / "static" / "practice_loop.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

_HARNESS = r"""
global.window = {};
require(process.argv[1]);
const pick = window.VerbBoardPracticeLoop.pickRepeatCandidates;
const c = JSON.parse(process.argv[2]);
const verbs = c.verbs.map(function (id) { return { id: id }; });
const ids = function (list) { return list.map(function (v) { return v.id; }); };

if (c.mode === "single") {
  const out = pick(verbs, new Set(c.seen), new Set(c.known), new Set(c.exclude || []),
                   c.lastRepeated || {}, c.size);
  console.log(JSON.stringify(ids(out)));
} else {
  // Simulate consecutive sessions: write back "now" for each pick, as startPractice does.
  const lastRepeated = {};
  const rounds = [];
  for (let t = 1; t <= c.rounds; t++) {
    const out = pick(verbs, new Set(c.seen), new Set(c.known), new Set(), lastRepeated, c.size);
    out.forEach(function (v) { lastRepeated[v.id] = t; });
    rounds.push(ids(out));
  }
  console.log(JSON.stringify(rounds));
}
"""


def _run(case: dict) -> list:
    result = subprocess.run(
        ["node", "-e", _HARNESS, str(PRACTICE_LOOP_JS), json.dumps(case)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


VERBS = [f"v{i}" for i in range(1, 13)]


def test_only_seen_and_not_known_and_not_excluded_verbs_are_picked() -> None:
    picked = _run(
        {
            "mode": "single",
            "verbs": VERBS,
            "seen": ["v1", "v2", "v3", "v4", "v5"],
            "known": ["v2"],
            "exclude": ["v3"],
            "size": 9,
        }
    )
    assert set(picked) <= {"v1", "v4", "v5"}
    assert len(picked) == 3


def test_never_seen_verbs_are_not_repeat_candidates() -> None:
    assert _run({"mode": "single", "verbs": VERBS, "seen": [], "known": [], "size": 6}) == []


@pytest.mark.parametrize(("size", "expected"), [(3, 1), (6, 2), (9, 3)])
def test_quota_is_a_third_of_the_session(size: int, expected: int) -> None:
    picked = _run({"mode": "single", "verbs": VERBS, "seen": VERBS, "known": [], "size": size})
    assert len(picked) == expected


def test_never_repeated_verbs_come_before_recently_repeated_ones() -> None:
    picked = _run(
        {
            "mode": "single",
            "verbs": VERBS[:4],
            "seen": VERBS[:4],
            "known": [],
            "lastRepeated": {"v1": 500, "v2": 100, "v3": 300},  # v4 never repeated
            "size": 6,
        }
    )
    assert picked == ["v4", "v2"]


def test_every_struggling_verb_resurfaces_within_a_bounded_number_of_sessions() -> None:
    # 6 stuck verbs, 2 repeat slots per session: all covered in 3 sessions, no verb twice before all once.
    rounds = _run({"mode": "rounds", "verbs": VERBS, "seen": VERBS[:6], "known": [], "size": 6, "rounds": 3})
    flat = [verb for picked in rounds for verb in picked]
    assert sorted(flat) == sorted(VERBS[:6])
