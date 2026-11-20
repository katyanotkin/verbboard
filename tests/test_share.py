"""Share with a friend on /verbs (issue #128): URL helpers, page markup, session flags,
i18n keys, the share.js click logic (Node harness) and the service-worker precache."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.analytics import session_tracker
from core.languages.config import FREE_STUDY_LANGUAGES
from core.share_service import is_share_landing, is_shareable_language, share_og_image_url, share_verbs_url

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-11-18"
PATH = f"analytics_sessions/{DATE}_fp1"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ── URL helpers ──────────────────────────────────────────────────────────────


def test_share_urls_use_public_base_url_and_no_ui_language(monkeypatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://example.test/")
    url = share_verbs_url("en")
    assert url == "https://example.test/verbs?language=en&utm_source=share"
    assert "ui_language" not in url
    assert share_og_image_url("en") == "https://example.test/static/og/verbs-en.png"


@pytest.mark.parametrize("language", ["tr", "xx", ""])
def test_share_helpers_empty_for_plus_only_and_unknown(language: str) -> None:
    assert not is_shareable_language(language)
    assert share_verbs_url(language) == ""
    assert share_og_image_url(language) == ""


def test_og_png_exists_for_every_free_language() -> None:
    for language in FREE_STUDY_LANGUAGES:
        assert (ROOT / f"app/static/og/verbs-{language}.png").is_file(), language


def test_is_share_landing() -> None:
    assert is_share_landing({"utm_source": "share"})
    assert not is_share_landing({"utm_source": "other"})
    assert not is_share_landing({})


# ── /verbs markup ────────────────────────────────────────────────────────────


def test_verbs_page_has_share_button_and_large_card(client: TestClient) -> None:
    html = client.get("/verbs?language=en").text
    assert 'id="vb-share-btn"' in html
    match = re.search(r'data-share-url="([^"]*)"', html)
    assert match
    assert "utm_source=share" in match.group(1)
    assert "ui_language" not in match.group(1)
    assert 'property="og:image"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html


def test_verbs_page_for_plus_only_language_has_no_share(client: TestClient) -> None:
    html = client.get("/verbs?language=tr").text
    assert 'id="vb-share-btn"' not in html
    assert 'property="og:image"' not in html
    assert 'name="twitter:card" content="summary"' in html


# ── session flags ────────────────────────────────────────────────────────────


def test_create_session_share_landed_flag(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "en", "en", share_landed=True)
    assert fake_db._docs[PATH]["share_landed"] is True


def test_create_session_share_landed_defaults_false_and_merges_later(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "en", "en")
    assert fake_db._docs[PATH]["share_landed"] is False
    session_tracker._create_session("fp1", DATE, "mobile", "en", "en", share_landed=True)
    assert fake_db._docs[PATH]["share_landed"] is True
    session_tracker._create_session("fp1", DATE, "mobile", "en", "en")  # a later normal view
    assert fake_db._docs[PATH]["share_landed"] is True


def test_positional_create_session_calls_still_work(fake_db) -> None:
    session_tracker._create_session("fp1", DATE, "mobile", "en", "en", True, "", True, False)
    assert fake_db._docs[PATH]["home_viewed"] is True


def test_share_tapped_is_set_once_and_never_creates_stub(fake_db) -> None:
    session_tracker._record_share_tapped("nobody", DATE)
    assert f"analytics_sessions/{DATE}_nobody" not in fake_db._docs

    fake_db._docs[PATH] = {"sid": "fp1"}
    session_tracker._record_share_tapped("fp1", DATE)
    session_tracker._record_share_tapped("fp1", DATE)
    assert fake_db._docs[PATH] == {"sid": "fp1", "share_tapped": True}
    session_tracker._create_session("fp1", DATE, "mobile", "en", "en")
    assert fake_db._docs[PATH]["share_tapped"] is True


def test_practice_event_endpoint_accepts_share_tapped(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_share_tapped", new_callable=AsyncMock) as rec:
        resp = client.post("/api/analytics/practice_event", json={"event": "share_tapped"})
    assert resp.status_code == 200 and resp.json() == {"ok": True}
    rec.assert_awaited_once()


def test_middleware_passes_share_landed(client: TestClient) -> None:
    with patch("core.analytics.session_tracker.start_session", new_callable=AsyncMock) as start:
        client.get("/verbs?language=en&utm_source=share")
        client.get("/verbs?language=en")
    assert [c.kwargs.get("share_landed") for c in start.call_args_list] == [True, False]


def test_middleware_creates_session_with_share_landed(client: TestClient, fake_db) -> None:
    client.get("/verbs?language=en&utm_source=share")
    deadline = time.time() + 2
    while time.time() < deadline and not any(k.startswith("analytics_sessions/") for k in fake_db._docs):
        time.sleep(0.05)
    sessions = [v for k, v in fake_db._docs.items() if k.startswith("analytics_sessions/")]
    assert sessions and sessions[0]["share_landed"] is True


def test_engagement_flags_list_share_flags() -> None:
    from core.admin_feedback_service import _ENGAGEMENT_FLAGS

    assert "share_tapped" in _ENGAGEMENT_FLAGS and "share_landed" in _ENGAGEMENT_FLAGS


# ── i18n ─────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "ru", "he", "es"])
def test_share_i18n_keys(locale: str) -> None:
    data = json.loads((ROOT / f"app/i18n/{locale}.json").read_text(encoding="utf-8"))
    for key in ("share.button", "share.copied", "share.text"):
        assert data.get(key), (locale, key)
    assert "{language}" in data["share.text"]


# ── service worker ───────────────────────────────────────────────────────────


def test_sw_precaches_share_js() -> None:
    sw = (ROOT / "app/static/sw.js").read_text(encoding="utf-8")
    assert '"/static/share.js"' in sw


# ── share.js (Node harness) ──────────────────────────────────────────────────

_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const [src, mode] = process.argv.slice(1);
const URL_ = 'https://x.test/verbs?language=en&utm_source=share';
const attrs = { 'data-share-url': URL_, 'data-share-text': 'T', 'data-share-title': 'VerbBoard', 'data-copied-label': 'COPIED' };
let click = null;
const btn = { addEventListener(e, f) { click = f; }, getAttribute: k => attrs[k] };
const status = { textContent: '' };
const calls = { share: [], clip: [], fetched: [] };
const nav = {};
if (mode === 'share_ok' || mode === 'share_abort' || mode === 'share_fail') {
  nav.share = d => { calls.share.push(d);
    if (mode === 'share_abort') return Promise.reject({ name: 'AbortError' });
    if (mode === 'share_fail') return Promise.reject(new Error('nope'));
    return Promise.resolve(); };
}
if (mode !== 'clip_fail') nav.clipboard = { writeText: t => { calls.clip.push(t); return Promise.resolve(); } };
else nav.clipboard = { writeText: () => Promise.reject(new Error('denied')) };
const ctx = {
  document: { readyState: 'complete', getElementById: id => id === 'vb-share-btn' ? btn : id === 'vb-share-status' ? status : null,
              addEventListener() {} },
  navigator: nav,
  fetch: (u, o) => { calls.fetched.push([u, o]); return Promise.resolve(); },
  setTimeout: () => 0, clearTimeout() {},
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(src, 'utf8'), ctx);
const ev = { currentTarget: btn };
click(ev); click(ev);
setTimeout(() => console.log(JSON.stringify({ calls, status: status.textContent, url: URL_ })), 20);
"""


def _run_share_js(mode: str) -> dict:
    out = subprocess.run(
        ["node", "-e", _HARNESS, str(ROOT / "app/static/share.js"), mode],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(out.stdout)


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
class TestShareJs:
    def test_native_share_gets_url_and_beacon_fires_once(self) -> None:
        r = _run_share_js("share_ok")
        assert len(r["calls"]["share"]) == 2
        assert r["calls"]["share"][0]["url"] == r["url"]
        beacons = [f for f in r["calls"]["fetched"] if f[0] == "/api/analytics/practice_event"]
        assert len(beacons) == 1
        assert json.loads(beacons[0][1]["body"]) == {"event": "share_tapped"}
        assert r["status"] == ""

    def test_abort_shows_nothing(self) -> None:
        r = _run_share_js("share_abort")
        assert r["status"] == "" and r["calls"]["clip"] == []

    def test_share_failure_falls_back_to_clipboard(self) -> None:
        r = _run_share_js("share_fail")
        assert r["calls"]["clip"] and r["calls"]["clip"][0] == r["url"]
        assert r["status"] == "COPIED"

    def test_no_native_share_copies_link(self) -> None:
        r = _run_share_js("no_share")
        assert r["status"] == "COPIED"

    def test_clipboard_failure_shows_the_url(self) -> None:
        r = _run_share_js("clip_fail")
        assert r["status"] == r["url"]
