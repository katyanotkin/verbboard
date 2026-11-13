"""Unit tests: rate-nudge decision logic (app/static/rate_nudge.js).

Node-subprocess harness like tests/test_login_nudge.py: the real JS file is
loaded with window/localStorage/navigator stubbed, and a list of ops is run
against window.VerbBoardRateNudge. buildCta's DOM wiring is not covered.

Ops: {"ua": str} sets navigator.userAgent; {"call": name, "args": [...]};
{"reload": true} re-requires the module (localStorage persists); {"get": key}
reads a localStorage value; {"set": key, "value": v} writes one; {"now": ms}
fakes Date.now(). Every op appends one result to the output list.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RATE_NUDGE_JS = REPO_ROOT / "app" / "static" / "rate_nudge.js"

ANDROID_CHROME = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
ANDROID_WEBVIEW = (
    "Mozilla/5.0 (Linux; Android 14; Pixel 8; wv) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 Mobile Safari/537.36"
)
IPHONE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
)
DESKTOP = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

_HARNESS = r"""
'use strict';
global.__store = {};
global.localStorage = {
  getItem: function (k) {
    return Object.prototype.hasOwnProperty.call(global.__store, k) ? global.__store[k] : null;
  },
  setItem: function (k, v) { global.__store[k] = String(v); },
  removeItem: function (k) { delete global.__store[k]; },
};
global.window = {};
global.document = {};
Object.defineProperty(global, 'navigator', {
  value: { userAgent: '' }, writable: true, configurable: true,
});

let fakeNow = null;
const realNow = Date.now;
Date.now = function () { return fakeNow === null ? realNow() : fakeNow; };

const modulePath = process.argv[1];
function loadModule() {
  delete require.cache[require.resolve(modulePath)];
  require(modulePath);
  return global.window.VerbBoardRateNudge;
}
let NUDGE = loadModule();

const ops = JSON.parse(process.argv[2]);
const out = [];
for (const op of ops) {
  if ('ua' in op) { global.navigator.userAgent = op.ua; out.push(null); }
  else if ('set' in op) { global.localStorage.setItem(op.set, op.value); out.push(null); }
  else if ('now' in op) { fakeNow = op.now; out.push(null); }
  else if (op.reload) { NUDGE = loadModule(); out.push(null); }
  else if ('get' in op) { out.push(global.localStorage.getItem(op.get)); }
  else { out.push(NUDGE[op.call].apply(null, op.args || [])); }
}
process.stdout.write(JSON.stringify(out));
"""


def _run(ops: list[dict]) -> list:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    assert node is not None
    proc = subprocess.run(
        [node, "-e", _HARNESS, str(RATE_NUDGE_JS), json.dumps(ops)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


@pytest.mark.parametrize(
    "ua,expected",
    [
        (ANDROID_CHROME, True),
        (ANDROID_WEBVIEW, False),
        (IPHONE, False),
        (DESKTOP, False),
        ("", False),
    ],
)
def test_is_android_browser(ua, expected):
    out = _run([{"call": "isAndroidBrowser", "args": [ua]}])
    assert out == [expected]


def test_record_completed_true_on_second_for_android():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"call": "recordCompleted"},
            {"call": "recordCompleted"},
        ]
    )
    assert out[1:] == [False, True]


def test_record_completed_false_after_mark_shown():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"call": "recordCompleted"},
            {"call": "recordCompleted"},
            {"call": "markShown"},
            {"call": "recordCompleted"},
            {"call": "recordCompleted"},
        ]
    )
    assert out[2] is True
    assert out[4:] == [False, False]


@pytest.mark.parametrize("ua", [IPHONE, DESKTOP, ANDROID_WEBVIEW])
def test_record_completed_false_when_not_android_browser(ua):
    out = _run([{"ua": ua}] + [{"call": "recordCompleted"}] * 3)
    assert out[1:] == [False, False, False]


def test_can_show_respects_done_flag_and_ua():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"call": "canShow"},
            {"ua": IPHONE},
            {"call": "canShow"},
            {"ua": ANDROID_CHROME},
            {"call": "markShown"},
            {"call": "canShow"},
        ]
    )
    assert out[1] is True
    assert out[3] is False
    assert out[6] is False


def test_counter_persists_across_module_reload():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"call": "recordCompleted"},
            {"reload": True},
            {"call": "recordCompleted"},
            {"get": "rate_nudge_completed"},
        ]
    )
    assert out[2 + 1] is True
    assert out[4] == "2"


DAY_MS = 24 * 60 * 60 * 1000
T0 = 1_800_000_000_000


def _votd_opens(n):
    return [{"call": "recordVotdOpened"}] * n


def test_votd_four_opens_not_due_fifth_due_on_android():
    out = _run(
        [{"ua": ANDROID_CHROME}, *_votd_opens(4), {"call": "votdNudgeDue"}, *_votd_opens(1), {"call": "votdNudgeDue"}]
    )
    assert out[5] is False
    assert out[7] is True


@pytest.mark.parametrize("ua", [IPHONE, ANDROID_WEBVIEW, DESKTOP])
def test_votd_never_due_when_not_android_browser(ua):
    out = _run([{"ua": ua}, *_votd_opens(6), {"call": "votdNudgeDue"}])
    assert out[-1] is False


def test_votd_counter_persists_across_reload():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            *_votd_opens(3),
            {"reload": True},
            *_votd_opens(2),
            {"get": "rate_nudge_votd_opens"},
            {"call": "votdNudgeDue"},
        ]
    )
    assert out[-2:] == ["5", True]


def test_votd_counter_resets_after_show():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"now": T0},
            *_votd_opens(5),
            {"call": "markShown"},
            {"get": "rate_nudge_votd_opens"},
            {"call": "votdNudgeDue"},
        ]
    )
    assert out[-2:] == ["0", False]


def test_votd_second_ask_needs_30_days_and_cap_is_two():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"now": T0},
            *_votd_opens(5),
            {"call": "markShown"},
            *_votd_opens(5),
            {"now": T0 + 29 * DAY_MS},
            {"call": "votdNudgeDue"},
            {"now": T0 + 30 * DAY_MS},
            {"call": "votdNudgeDue"},
            {"call": "markShown"},
            *_votd_opens(5),
            {"now": T0 + 90 * DAY_MS},
            {"call": "votdNudgeDue"},
        ]
    )
    assert out[14] is False
    assert out[16] is True
    assert out[-1] is False


def test_votd_tapped_stops_it():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            *_votd_opens(5),
            {"set": "rate_nudge_tapped", "value": "1"},
            {"call": "votdNudgeDue"},
        ]
    )
    assert out[-1] is False


def test_mark_shown_increments_asks_and_sets_last_at():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"now": T0},
            {"call": "markShown"},
            {"get": "rate_nudge_asks"},
            {"get": "rate_nudge_last_at"},
        ]
    )
    assert out[3:] == ["1", str(T0)]


def test_second_ask_needs_30_days_and_cap_is_two():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"now": T0},
            {"call": "markShown"},
            {"now": T0 + 29 * DAY_MS},
            {"call": "canShow"},
            {"now": T0 + 30 * DAY_MS},
            {"call": "canShow"},
            {"call": "markShown"},
            {"now": T0 + 90 * DAY_MS},
            {"call": "canShow"},
        ]
    )
    assert out[4] is False
    assert out[6] is True
    assert out[9] is False


def test_tapped_blocks_forever():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"set": "rate_nudge_tapped", "value": "1"},
            {"call": "canShow"},
            *_votd_opens(5),
            {"call": "votdNudgeDue"},
        ]
    )
    assert out[2] is False
    assert out[-1] is False


def test_legacy_done_flag_migrates_to_one_ask_now():
    out = _run(
        [
            {"ua": ANDROID_CHROME},
            {"now": T0},
            {"set": "rate_nudge_done", "value": "1"},
            {"call": "canShow"},
            {"get": "rate_nudge_asks"},
            {"get": "rate_nudge_last_at"},
            {"now": T0 + 31 * DAY_MS},
            {"call": "canShow"},
        ]
    )
    assert out[3] is False
    assert out[4:6] == ["1", str(T0)]
    assert out[7] is True


def test_home_loads_rate_nudge_before_home_js(client) -> None:
    html = client.get("/").text
    assert "/static/rate_nudge.js" in html
    assert html.index("/static/rate_nudge.js") < html.index("/static/home.js")
