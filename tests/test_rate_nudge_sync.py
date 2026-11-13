"""Signed-in rate-nudge sync: service, POST /api/progress/rate_nudge, rate_nudge.js sync, auth.js wiring."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core import rate_nudge_service as service
from core.auth.models import AuthUser
from core.progress.progress_repository import delete_all_progress_data
from core.rate_limit import SlidingWindowRateLimiter

REPO_ROOT = Path(__file__).resolve().parent.parent
RATE_NUDGE_JS = REPO_ROOT / "app" / "static" / "rate_nudge.js"
AUTH_JS = REPO_ROOT / "app" / "static" / "auth.js"

USER = AuthUser(uid="u1", email="u@example.com", name="U", picture="")
FULL = {"votd_opens": 7, "votd_opens_at_last_ask": 2, "completed": 3, "asks": 1, "last_at": 1000, "tapped": False}


def _doc(fake_db, uid="u1"):
    return fake_db.collection("users").document(uid)


def _stored(fake_db, uid="u1"):
    snap = _doc(fake_db, uid).get()
    return snap.to_dict() if snap.exists else None


# ---------------------------------------------------------------------------
# service
# ---------------------------------------------------------------------------


def test_service_creates_missing_user_doc(fake_db) -> None:
    merged = service.sync_rate_nudge("u1", {**FULL, "last_at": 1})
    assert merged == {**FULL, "last_at": 1}
    stored = _stored(fake_db)["rate_nudge"]
    assert stored["votd_opens"] == 7 and stored["votd_opens_at_last_ask"] == 2
    assert "updated_at" in stored


def test_service_takes_max_and_ors_tapped(fake_db) -> None:
    _doc(fake_db).set(
        {
            "rate_nudge": {
                "votd_opens": 9,
                "votd_opens_at_last_ask": 1,
                "completed": 0,
                "asks": 2,
                "last_at": 5,
                "tapped": True,
            }
        }
    )
    merged = service.sync_rate_nudge("u1", {**FULL, "last_at": 3})
    assert merged == {
        "votd_opens": 9,
        "votd_opens_at_last_ask": 2,
        "completed": 3,
        "asks": 2,
        "last_at": 5,
        "tapped": True,
    }


def test_service_clamps_future_last_at_to_now(fake_db) -> None:
    far_future = int(datetime.now(UTC).timestamp() * 1000) + 10**12
    merged = service.sync_rate_nudge("u1", {**FULL, "last_at": far_future})
    now_ms = int(datetime.now(UTC).timestamp() * 1000)
    assert 0 < merged["last_at"] <= now_ms


def test_service_normalises_garbage_stored_doc(fake_db) -> None:
    _doc(fake_db).set({"rate_nudge": {"votd_opens": "lots", "asks": -4, "tapped": "yes", "completed": True}})
    merged = service.sync_rate_nudge("u1", {**FULL, "last_at": 1})
    assert merged["votd_opens"] == 7 and merged["asks"] == 1 and merged["completed"] == 3
    assert merged["tapped"] is False


def test_service_non_dict_stored_value(fake_db) -> None:
    _doc(fake_db).set({"rate_nudge": "junk"})
    assert service.sync_rate_nudge("u1", {**FULL, "last_at": 1})["votd_opens"] == 7


def test_service_no_write_when_nothing_changes(fake_db, monkeypatch) -> None:
    service.sync_rate_nudge("u1", {**FULL, "last_at": 1})
    before = _stored(fake_db)

    def boom(*args, **kwargs):
        raise AssertionError("unexpected write")

    from tests.fake_firestore import FakeDocRef

    monkeypatch.setattr(FakeDocRef, "set", boom)
    # Lower / equal incoming values merge to the stored state: no write.
    service.sync_rate_nudge("u1", {**FULL, "votd_opens": 1, "last_at": 0})
    service.sync_rate_nudge("u1", {**FULL, "last_at": 1})
    assert _stored(fake_db) == before


def test_service_leaves_user_timestamps_untouched(fake_db) -> None:
    _doc(fake_db).set({"email": "u@example.com", "updated_at": "UPD", "last_seen_at": "SEEN"})
    service.sync_rate_nudge("u1", {**FULL, "last_at": 1})
    data = _stored(fake_db)
    assert data["updated_at"] == "UPD" and data["last_seen_at"] == "SEEN"
    assert data["email"] == "u@example.com" and data["rate_nudge"]["votd_opens"] == 7


# ---------------------------------------------------------------------------
# route
# ---------------------------------------------------------------------------


@pytest.fixture()
def signed_in(monkeypatch):
    monkeypatch.setattr("app.routes.api_progress.get_optional_auth_user", lambda request: USER)


def _post(client, **overrides):
    body = {**FULL, **overrides}
    return client.post("/api/progress/rate_nudge", json=body)


def test_route_requires_auth(client: TestClient) -> None:
    assert _post(client).status_code == 401


def test_route_returns_merged_state(client, signed_in, fake_db) -> None:
    resp = _post(client, last_at=1, junk="ignored")
    assert resp.status_code == 200
    assert resp.json() == {**FULL, "last_at": 1}
    again = _post(client, votd_opens=2, completed=0, last_at=1)
    assert again.json()["votd_opens"] == 7 and again.json()["completed"] == 3


def test_route_ignores_extra_fields(client, signed_in, fake_db) -> None:
    resp = _post(client, last_at=1, uid="other", evil=1)
    assert resp.status_code == 200
    assert _stored(fake_db, "other") is None
    assert "evil" not in resp.json()


@pytest.mark.parametrize("field", ["votd_opens", "votd_opens_at_last_ask", "completed", "asks", "last_at"])
def test_route_rejects_negative(client, signed_in, fake_db, field) -> None:
    assert _post(client, **{field: -1}).status_code == 400


@pytest.mark.parametrize("field", ["votd_opens", "votd_opens_at_last_ask", "completed", "asks"])
def test_route_rejects_over_max_count(client, signed_in, fake_db, field) -> None:
    assert _post(client, **{field: 10001}).status_code == 400
    assert _post(client, **{field: 10000, "last_at": 1}).status_code == 200


def test_route_rate_limited(client, signed_in, fake_db, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.routes.api_progress._RATE_NUDGE_RATE_LIMITER", SlidingWindowRateLimiter(max_calls=1, window_seconds=600)
    )
    assert _post(client, last_at=1).status_code == 200
    assert _post(client, last_at=1).status_code == 429


def test_account_deletion_removes_rate_nudge(fake_db) -> None:
    service.sync_rate_nudge("u1", {**FULL, "last_at": 1})
    assert _stored(fake_db)["rate_nudge"]
    delete_all_progress_data("u1")
    assert _stored(fake_db) is None


# ---------------------------------------------------------------------------
# rate_nudge.js: mergeState, syncWithServer, baseline
# ---------------------------------------------------------------------------

_HARNESS = r"""
'use strict';
global.__store = {};
global.localStorage = {
  getItem: function (k) { return Object.prototype.hasOwnProperty.call(global.__store, k) ? global.__store[k] : null; },
  setItem: function (k, v) { global.__store[k] = String(v); },
  removeItem: function (k) { delete global.__store[k]; },
};
global.window = {};
global.document = {};
Object.defineProperty(global, 'navigator', { value: { userAgent: '' }, writable: true, configurable: true });
let fakeNow = null;
const realNow = Date.now;
Date.now = function () { return fakeNow === null ? realNow() : fakeNow; };
// Make the 4 s sync timeout fire immediately so a hung fetch resolves quickly.
const realSetTimeout = setTimeout;
global.setTimeout = function (fn) { return realSetTimeout(fn, 1); };

let fetchMode = { kind: 'ok', body: {} };
global.__fetchCalls = [];
global.fetch = function (url, opts) {
  global.__fetchCalls.push({ url: url, opts: opts });
  if (fetchMode.kind === 'ok') {
    return Promise.resolve({ ok: true, json: function () { return Promise.resolve(fetchMode.body); } });
  }
  if (fetchMode.kind === 'status') return Promise.resolve({ ok: false, status: fetchMode.status });
  if (fetchMode.kind === 'reject') return Promise.reject(new Error('network'));
  return new Promise(function (resolve, reject) {
    opts.signal.addEventListener('abort', function () { reject(new Error('aborted')); });
  });
};

const modulePath = process.argv[1];
function loadModule() {
  delete require.cache[require.resolve(modulePath)];
  require(modulePath);
  return global.window.VerbBoardRateNudge;
}
let NUDGE = loadModule();

(async function () {
  const ops = JSON.parse(process.argv[2]);
  const out = [];
  for (const op of ops) {
    if ('ua' in op) { global.navigator.userAgent = op.ua; out.push(null); }
    else if ('set' in op) { global.localStorage.setItem(op.set, op.value); out.push(null); }
    else if ('now' in op) { fakeNow = op.now; out.push(null); }
    else if ('fetch' in op) { fetchMode = op.fetch; out.push(null); }
    else if (op.reload) { NUDGE = loadModule(); out.push(null); }
    else if (op.calls) { out.push(global.__fetchCalls.map(function (c) {
      return { url: c.url, method: c.opts.method, auth: c.opts.headers.Authorization, body: JSON.parse(c.opts.body) };
    })); }
    else if ('get' in op) { out.push(global.localStorage.getItem(op.get)); }
    else { out.push(await NUDGE[op.call].apply(null, op.args || [])); }
  }
  process.stdout.write(JSON.stringify(out));
})();
"""

ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36"
DAY = 24 * 60 * 60 * 1000


def _run(ops: list[dict]) -> list:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    assert node is not None
    proc = subprocess.run(
        [node, "-e", _HARNESS, str(RATE_NUDGE_JS), json.dumps(ops)], capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _local_ops(**values):
    keys = {
        "votd_opens": "rate_nudge_votd_opens",
        "votd_opens_at_last_ask": "rate_nudge_votd_baseline",
        "completed": "rate_nudge_completed",
        "asks": "rate_nudge_asks",
        "last_at": "rate_nudge_last_at",
    }
    return [{"set": keys[k], "value": str(v)} for k, v in values.items()]


def _get_all():
    return [
        {"get": k}
        for k in (
            "rate_nudge_votd_opens",
            "rate_nudge_votd_baseline",
            "rate_nudge_completed",
            "rate_nudge_asks",
            "rate_nudge_last_at",
            "rate_nudge_tapped",
        )
    ]


def test_merge_state_takes_max_and_ors_tapped():
    a = {"votd_opens": 5, "votd_opens_at_last_ask": 0, "completed": 4, "asks": 1, "last_at": 10, "tapped": False}
    b = {"votd_opens": 2, "votd_opens_at_last_ask": 2, "completed": 9, "asks": 0, "last_at": 3, "tapped": True}
    out = _run([{"call": "mergeState", "args": [a, b]}, {"call": "mergeState", "args": [b, a]}])
    expected = {"votd_opens": 5, "votd_opens_at_last_ask": 2, "completed": 9, "asks": 1, "last_at": 10, "tapped": True}
    assert out == [expected, expected]


def test_merge_state_garbage_and_missing_never_lowers():
    a = {"votd_opens": 5, "completed": 2, "asks": 1, "tapped": True}
    out = _run(
        [
            {"call": "mergeState", "args": [a, {"votd_opens": "x", "completed": -3, "asks": None, "tapped": "1"}]},
            {"call": "mergeState", "args": [None, None]},
        ]
    )
    assert out[0]["votd_opens"] == 5 and out[0]["completed"] == 2 and out[0]["asks"] == 1
    assert out[0]["tapped"] is True
    assert out[1] == {
        "tapped": False,
        "votd_opens": 0,
        "votd_opens_at_last_ask": 0,
        "completed": 0,
        "asks": 0,
        "last_at": 0,
    }


def test_sync_no_token_returns_false_without_fetch():
    out = _run([{"call": "syncWithServer", "args": [""]}, {"calls": True}])
    assert out == [False, []]


def test_sync_posts_local_state_and_writes_max_back():
    server = {"votd_opens": 8, "votd_opens_at_last_ask": 3, "completed": 1, "asks": 2, "last_at": 500, "tapped": True}
    out = _run(
        [
            *_local_ops(votd_opens=4, votd_opens_at_last_ask=1, completed=6, asks=1, last_at=900),
            {"fetch": {"kind": "ok", "body": server}},
            {"call": "syncWithServer", "args": ["tok"]},
            {"calls": True},
            *_get_all(),
        ]
    )
    assert out[6] is True
    call = out[7][0]
    assert call["url"] == "/api/progress/rate_nudge" and call["method"] == "POST"
    assert call["auth"] == "Bearer tok"
    assert call["body"] == {
        "votd_opens": 4,
        "votd_opens_at_last_ask": 1,
        "completed": 6,
        "asks": 1,
        "last_at": 900,
        "tapped": False,
    }
    assert out[8:] == ["8", "3", "6", "2", "900", "1"]


@pytest.mark.parametrize(
    "mode", [{"kind": "status", "status": 500}, {"kind": "status", "status": 401}, {"kind": "reject"}]
)
def test_sync_failure_keeps_local_state(mode):
    out = _run(
        [
            *_local_ops(votd_opens=4, completed=2, asks=1),
            {"fetch": mode},
            {"call": "syncWithServer", "args": ["tok"]},
            *_get_all(),
        ]
    )
    assert out[4] is False
    assert out[5:] == ["4", None, "2", "1", None, None]


def test_sync_hung_fetch_gives_up_via_abort():
    out = _run(
        [
            *_local_ops(votd_opens=4),
            {"fetch": {"kind": "hang"}},
            {"call": "syncWithServer", "args": ["tok"]},
            {"get": "rate_nudge_votd_opens"},
        ]
    )
    assert out[2:] == [False, "4"]


def test_baseline_votd_due_again_only_after_five_more_opens():
    out = _run(
        [
            {"ua": ANDROID},
            {"now": 1_000_000_000_000},
            *_local_ops(votd_opens=5),
            {"call": "votdNudgeDue"},
            {"call": "markShown"},
            {"call": "votdNudgeDue"},
            {"now": 1_000_000_000_000 + 31 * DAY},
            {"call": "votdNudgeDue"},
            *_local_ops(votd_opens=9),
            {"call": "votdNudgeDue"},
            *_local_ops(votd_opens=10),
            {"call": "votdNudgeDue"},
        ]
    )
    assert out[3] is True
    assert out[5] is False  # just shown
    assert out[7] is False  # gap passed, only 0 new opens
    assert out[9] is False  # 4 new opens
    assert out[11] is True  # 5 new opens
    assert out[-1] is True


def test_baseline_survives_sync_roundtrip():
    out = _run(
        [
            {"ua": ANDROID},
            *_local_ops(votd_opens=5),
            {"call": "markShown"},
            {"fetch": {"kind": "ok", "body": {}}},
            {"call": "syncWithServer", "args": ["tok"]},
            {"calls": True},
        ]
    )
    assert out[-1][0]["body"]["votd_opens_at_last_ask"] == 5
    assert out[-1][0]["body"]["votd_opens"] == 5


def test_legacy_done_flag_migrates_before_sync():
    out = _run(
        [
            {"set": "rate_nudge_done", "value": "1"},
            {"fetch": {"kind": "ok", "body": {}}},
            {"call": "syncWithServer", "args": ["tok"]},
            {"calls": True},
        ]
    )
    assert out[-1][0]["body"]["asks"] == 1


# ---------------------------------------------------------------------------
# auth.js wiring (source assertion, kept loose)
# ---------------------------------------------------------------------------


def test_auth_hydrate_calls_rate_nudge_sync_before_language_early_return():
    source = AUTH_JS.read_text(encoding="utf-8")
    call = re.search(r"window\.VerbBoardRateNudge\)\s*await\s+window\.VerbBoardRateNudge\.syncWithServer\(", source)
    assert call, "hydrateProgress must guard on window.VerbBoardRateNudge and await syncWithServer"
    guard_pos = source.index("if (window.VerbBoardRateNudge)")
    language_lookup = source.index('select[name="language"]', guard_pos)
    assert guard_pos < language_lookup
    # It sits inside a try block so a sync failure can never break hydrateProgress.
    assert "try {" in source[max(0, guard_pos - 40) : guard_pos]
