"""Unit tests: rate-nudge decision logic (app/static/rate_nudge.js).

Node-subprocess harness like tests/test_login_nudge.py: the real JS file is
loaded with window/localStorage/navigator stubbed, and a list of ops is run
against window.VerbBoardRateNudge. buildCta's DOM wiring is not covered.

Ops: {"ua": str} sets navigator.userAgent; {"call": name, "args": [...]};
{"reload": true} re-requires the module (localStorage persists); {"get": key}
reads a localStorage value. Every op appends one result to the output list.
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
