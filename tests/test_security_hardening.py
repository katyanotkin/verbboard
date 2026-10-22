"""Security hardening: audio route, admin login limiter, headers, docs, admin JS (#75, #80, #81)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from core.audio_service import build_hashed_audio_key
from core.models import VerbEntry
from core.rate_limit import SlidingWindowRateLimiter
from tests.conftest import patch_everywhere

REPO_ROOT = Path(__file__).resolve().parent.parent
STATIC = REPO_ROOT / "app" / "static"


@pytest.fixture(autouse=True)
def _fresh_limiters(monkeypatch):
    monkeypatch.setattr(
        "app.routes.audio._GENERATION_LIMITER", SlidingWindowRateLimiter(max_calls=30, window_seconds=600)
    )
    monkeypatch.setattr(
        "app.routes.admin_auth._LOGIN_LIMITER", SlidingWindowRateLimiter(max_calls=5, window_seconds=600)
    )


def _no_audio(monkeypatch):
    monkeypatch.setattr("app.routes.audio.read_audio_bytes", lambda **kw: None)


# ---- #81 audio ----


def test_audio_generation_failure_is_503_no_store(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    _no_audio(monkeypatch)

    async def _boom(**kwargs):
        raise RuntimeError("tts down")

    monkeypatch.setattr("app.routes.audio.ensure_audio", _boom)
    patch_everywhere(monkeypatch, "core.verb_loader.load_entry_by_id", lambda **kw: mock_verb)
    resp = client.get(f"/audio/en/en_go/female/{build_hashed_audio_key('base', 'go')}.mp3")
    assert resp.status_code == 503
    assert resp.headers["cache-control"] == "no-store"


def _candidate_only_loader(mock_verb: VerbEntry):
    def _load(**kw):
        return mock_verb if kw.get("source") == "candidate" else None

    return _load


def test_audio_candidate_not_generated_for_anonymous(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    _no_audio(monkeypatch)
    calls: list = []

    async def _ensure(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.routes.audio.ensure_audio", _ensure)
    patch_everywhere(monkeypatch, "core.verb_loader.load_entry_by_id", _candidate_only_loader(mock_verb))
    resp = client.get(f"/audio/en/en_go/female/{build_hashed_audio_key('base', 'go')}.mp3")
    assert resp.status_code == 404
    assert calls == []


def test_audio_candidate_generated_for_admin(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    _no_audio(monkeypatch)
    calls: list = []

    async def _ensure(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("app.routes.audio.ensure_audio", _ensure)
    monkeypatch.setattr("app.routes.audio.read_session_claims", lambda request: {"role": "admin"})
    patch_everywhere(monkeypatch, "core.verb_loader.load_entry_by_id", _candidate_only_loader(mock_verb))
    resp = client.get(f"/audio/en/en_go/female/{build_hashed_audio_key('base', 'go')}.mp3")
    assert resp.status_code == 200
    assert len(calls) == 1


def test_audio_generation_rate_limited_per_ip(client: TestClient, monkeypatch, mock_verb: VerbEntry) -> None:
    _no_audio(monkeypatch)
    monkeypatch.setattr(
        "app.routes.audio._GENERATION_LIMITER", SlidingWindowRateLimiter(max_calls=2, window_seconds=600)
    )

    async def _ensure(**kwargs):
        pass

    monkeypatch.setattr("app.routes.audio.ensure_audio", _ensure)
    patch_everywhere(monkeypatch, "core.verb_loader.load_entry_by_id", lambda **kw: mock_verb)
    url = f"/audio/en/en_go/female/{build_hashed_audio_key('base', 'go')}.mp3"
    codes = [client.get(url).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---- #80 ----


def test_admin_login_rate_limited(client: TestClient) -> None:
    codes = [
        client.post("/admin/login", data={"password": "wrong"}, follow_redirects=False).status_code for _ in range(6)
    ]
    assert codes[:5] == [303] * 5
    assert codes[5] == 429


def test_admin_login_successful_logins_do_not_consume_attempts(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.admin_auth.verify_admin_password", lambda password: password == "right")
    for _ in range(8):
        assert client.post("/admin/login", data={"password": "right"}, follow_redirects=False).status_code == 200
    # the owner is never locked out by successes, and failures still count
    codes = [
        client.post("/admin/login", data={"password": "wrong"}, follow_redirects=False).status_code for _ in range(6)
    ]
    assert codes[5] == 429


def test_security_headers_present_and_no_coop(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["x-frame-options"] == "SAMEORIGIN"
    assert "frame-ancestors 'self'" in resp.headers["content-security-policy"]
    assert "referrer-policy" in resp.headers
    assert "cross-origin-opener-policy" not in resp.headers


def test_docs_disabled_outside_local(monkeypatch) -> None:
    import importlib

    import app.main as main

    monkeypatch.setenv("ENVIRONMENT", "prod")
    try:
        reloaded = importlib.reload(main)
        assert reloaded.app.docs_url is None
        assert reloaded.app.openapi_url is None
        assert reloaded.app.redoc_url is None
    finally:
        monkeypatch.undo()
        importlib.reload(main)


# ---- #75 admin JS ----

_ADMIN_JS = ["admin_signals.js", "admin_candidates.js", "admin_live_verbs.js"]


@pytest.mark.parametrize("name", _ADMIN_JS)
def test_admin_js_has_no_inline_handlers_in_templates(name: str) -> None:
    source = (STATIC / name).read_text()
    assert not re.search(r"\bon(click|change|input|submit)\s*=", source), name


def test_admin_dispatch_passes_data_attributes_verbatim() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available")
    assert node is not None
    script = r"""
const fs = require('fs');
const listeners = {};
global.window = { ADMIN_ROOT: '/admin' };
global.document = { addEventListener: (t, f) => { listeners[t] = f; } };
const src = fs.readFileSync(process.argv[1], 'utf8') + '\n;globalThis.__A = ADMIN_ACTIONS;';
(0, eval)(src);
const got = [];
__A.go = (a, b, el) => got.push([a, b, el.id]);
const evil = "x');alert(1);('";
const el = { id: 'e1', dataset: { act: 'go', a1: evil, a2: 'en' } };
const target = { closest: () => el };
listeners.click({ type: 'click', target });
listeners.change({ type: 'change', target });   // click-type element ignores change
el.dataset.on = 'change';
listeners.click({ type: 'click', target });     // change-type element ignores click
listeners.change({ type: 'change', target });
el.dataset.act = 'constructor';                  // not an own action
listeners.change({ type: 'change', target });
console.log(JSON.stringify(got));
"""
    out = subprocess.run(
        [node, "-e", script, str(STATIC / "admin_shared.js")], capture_output=True, text=True, check=True
    ).stdout
    assert json.loads(out) == [["x');alert(1);('", "en", "e1"]] * 2
