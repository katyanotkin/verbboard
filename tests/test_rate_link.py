"""Android-only 'rate us on Google Play' line: beacon, Reports row, i18n,
markup on About/Feedback, and the Android visibility logic in pwa.js."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from core.admin_report_service import build_report
from core.analytics import session_tracker

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-11-06"
PATH = f"analytics_sessions/{DATE}_fp1"
KEYS = ("about.rate_line", "feedback.rate_line", "rate.link_label")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_record_rate_clicked_sets_flag_once(fake_db) -> None:
    fake_db._docs[PATH] = {"sid": "fp1"}
    session_tracker._record_rate_clicked("fp1", DATE)
    session_tracker._record_rate_clicked("fp1", DATE)
    assert fake_db._docs[PATH] == {"sid": "fp1", "rate_clicked": True}


def test_record_rate_clicked_drops_without_session(fake_db) -> None:
    session_tracker._record_rate_clicked("fp1", DATE)
    assert fake_db._docs == {}


def test_rate_clicked_endpoint(client: TestClient) -> None:
    with patch("app.routes.api_analytics.record_rate_clicked", new_callable=AsyncMock) as rec:
        resp = client.post("/api/analytics/rate_clicked")
    assert resp.json() == {"ok": True}
    rec.assert_awaited_once()


def test_reports_engagement_counts_rate_clicked(fake_db) -> None:
    base = {"date": "2026-10-02", "device_type": "mobile", "verb_viewed": True}
    fake_db._docs["analytics_sessions/2026-10-02_a"] = {**base, "rate_clicked": True}
    fake_db._docs["analytics_sessions/2026-10-02_b"] = dict(base)  # pre-flag session
    report = build_report("2026-10-02", "2026-10-02")
    assert report["engagement"]["rate_clicked"] == 1


@pytest.mark.parametrize("lang", ["en", "ru", "he", "es"])
def test_i18n_keys_present(lang: str) -> None:
    data = json.loads((ROOT / "app" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    for key in KEYS:
        assert data.get(key), (lang, key)


def test_about_has_hidden_rate_line(client: TestClient) -> None:
    html = client.get("/about?ui_language=he").text
    assert 'id="rate-line" hidden' in html
    assert "utm_medium%3Drate_link" in html


def test_feedback_has_rate_line_but_not_in_plus_mode(client: TestClient) -> None:
    assert 'id="rate-line" hidden' in client.get("/feedback").text
    assert 'id="rate-line"' not in client.get("/feedback?page=plus&language=tr").text


def test_other_pages_have_no_rate_line(client: TestClient) -> None:
    assert 'id="rate-line"' not in client.get("/").text


_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const [src, ua, standalone] = process.argv.slice(1);
const line = { hidden: true, removeAttribute() { this.hidden = false; } };
let click = null; const fetched = [];
const link = { addEventListener(e, f) { click = f; } };
const ctx = {
  document: { getElementById: id => id === 'rate-line' ? line : id === 'rate-link' ? link : null,
              documentElement: {}, addEventListener() {} },
  navigator: { userAgent: ua, standalone: standalone === '1' },
  window: { matchMedia: () => ({ matches: standalone === '1' }), navigator: {} },
  fetch: (u, o) => { fetched.push([u, o]); return Promise.resolve(); },
  setInterval() {}, location: {},
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(src, 'utf8'), ctx);
if (click) click();
console.log(JSON.stringify({ shown: !line.hidden, fetched }));
"""

ANDROID = "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/120 Mobile Safari/537.36"
CASES = [
    (ANDROID, "0", True),
    (ANDROID, "1", True),  # installed app / TWA
    (ANDROID.replace("Android 14;", "Android 14; wv)").replace("; wv))", "; wv)"), "0", False),
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) Safari/604.1", "1", False),
    ("Mozilla/5.0 (X11; Linux x86_64) Chrome/120", "0", False),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
@pytest.mark.parametrize("ua,standalone,expected", CASES)
def test_pwa_rate_link_visibility(ua: str, standalone: str, expected: bool) -> None:
    out = subprocess.run(
        ["node", "-e", _HARNESS, str(ROOT / "app/static/pwa.js"), ua, standalone],
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(out.stdout)
    assert result["shown"] is expected
    beacons = [f for f in result["fetched"] if f[0] == "/api/analytics/rate_clicked"]
    assert len(beacons) == (1 if expected else 0)
    if beacons:
        assert beacons[0][1]["keepalive"] is True and beacons[0][1]["method"] == "POST"
