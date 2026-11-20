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
from core.i18n import get_strings
from core.languages.config import FREE_STUDY_LANGUAGES
from core.models import Board, VerbEntry
from core.render import render_board_html
from core.share_service import (
    is_share_landing,
    is_shareable_language,
    share_learn_url,
    share_og_image_url,
    share_verbs_url,
)

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


# ── /learn and home share (issue #128 follow-up) ─────────────────────────────


def _learn_html(language: str, verb_id: str, lemma, candidate: str | None = None, display_lemma=None) -> str:
    verb = VerbEntry(id=verb_id, rank=1, lemma=lemma, forms={}, examples=[], display_lemma=display_lemma)
    board = Board(language=language, verb=verb, voice_key="female", voice_label="Female", sections=[])
    return render_board_html(board, ui_strings=get_strings("en"), ui_lang="en", candidate_verb_id=candidate)


def _attr(html: str, name: str) -> str:
    import html as html_lib

    match = re.search(rf'{name}="([^"]*)"', html)
    assert match, name
    return html_lib.unescape(match.group(1))


def test_share_learn_url_free_language() -> None:
    url = share_learn_url("en", "en_go")
    assert "/learn?language=en&verb_id=en_go&utm_source=share" in url
    assert "ui_language" not in url


@pytest.mark.parametrize("language,verb_id", [("tr", "tr_gitmek"), ("xx", "xx_a"), ("en", "")])
def test_share_learn_url_empty_cases(language: str, verb_id: str) -> None:
    assert share_learn_url(language, verb_id) == ""


def test_learn_page_has_share_button_and_og_image() -> None:
    html = _learn_html("en", "en_go", "go")
    assert 'id="learn-share-btn"' in html
    url = _attr(html, "data-share-url")
    assert "verb_id=en_go" in url and "utm_source=share" in url and "ui_language" not in url
    assert 'data-share-status="learn-share-status"' in html
    assert 'id="learn-share-status"' in html
    assert 'property="og:image"' in html
    assert "/static/share.js" in html


def test_learn_share_text_escapes_quote_and_ampersand() -> None:
    html = _learn_html("en", "en_odd", 'a"b&c')
    # The attribute must stay intact: no raw quote ends it early.
    assert 'data-share-text="' in html
    match = re.search(r'data-share-text="([^"]*)"', html)
    assert match is not None
    raw = match.group(1)
    assert '"' not in raw and "&c" not in raw.replace("&amp;", "").replace("&#34;", "")
    assert 'a"b&c' in _attr(html, "data-share-text")


def test_candidate_preview_has_no_share_and_no_og_image() -> None:
    html = _learn_html("en", "en_go", "go", candidate="cand1")
    assert "learn-share-btn" not in html
    assert 'property="og:image"' not in html
    assert 'name="twitter:card" content="summary"' in html


def test_plus_only_language_learn_has_no_share() -> None:
    html = _learn_html("tr", "tr_gitmek", "gitmek")
    assert "learn-share-btn" not in html
    assert 'property="og:image"' not in html


def test_russian_share_text_strips_stress_marks() -> None:
    html = _learn_html("ru", "ru_idti", "идти\u0301")
    text = _attr(html, "data-share-text")
    assert "\u0301" not in text
    assert "идти" in text


def test_russian_aspect_pair_share_text_has_no_dangling_slash() -> None:
    both = _learn_html(
        "ru", "ru_delat", "x", display_lemma={"imperfective": "дела\u0301ть", "perfective": "сде\u0301лать"}
    )
    text = _attr(both, "data-share-text")
    assert "\u0301" not in text and "делать / сделать" in text
    only = _learn_html("ru", "ru_delat", "x", display_lemma={"imperfective": "делать", "perfective": ""})
    text = _attr(only, "data-share-text")
    assert "делать" in text and "/" not in text


def test_hebrew_learn_renders_share() -> None:
    html = _learn_html("he", "he_lilmod", "לִלְמוֹד")
    assert 'id="learn-share-btn"' in html
    assert "לִלְמוֹד" in _attr(html, "data-share-text")


def test_home_has_share_button_for_free_language(client: TestClient) -> None:
    html = client.get("/?language=en").text
    assert 'id="home-share-btn"' in html
    url = _attr(html, "data-share-url")
    assert "/verbs?language=en" in url and "utm_source=share" in url
    assert 'data-share-status="home-share-status"' in html


def test_home_has_no_share_button_for_plus_only_language(client: TestClient) -> None:
    resp = client.get("/?language=tr", follow_redirects=True)
    assert 'id="home-share-btn"' not in resp.text


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


@pytest.mark.parametrize("locale", ["en", "ru", "he", "es"])
def test_share_text_verb_i18n_key(locale: str) -> None:
    data = json.loads((ROOT / f"app/i18n/{locale}.json").read_text(encoding="utf-8"))
    assert "{language}" in data["share.text_verb"]
    assert "{lemma}" in data["share.text_verb"]


# ── service worker ───────────────────────────────────────────────────────────


def test_sw_precaches_share_js() -> None:
    sw = (ROOT / "app/static/sw.js").read_text(encoding="utf-8")
    assert '"/static/share.js"' in sw


# ── share.js (Node harness) ──────────────────────────────────────────────────

_HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const [src, mode, btnId, statusId] = process.argv.slice(1);
const URL_ = 'https://x.test/verbs?language=en&utm_source=share';
const attrs = { 'data-share-url': URL_, ...(statusId && statusId !== 'vb-share-status' ? { 'data-share-status': statusId } : {}), 'data-share-text': 'T', 'data-share-title': 'VerbBoard', 'data-copied-label': 'COPIED' };
let click = null;
const btn = { addEventListener(e, f) { click = f; }, getAttribute: k => attrs[k] };
const status = { textContent: '' };
const decoy = { textContent: '' };
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
  document: { readyState: 'complete', getElementById: id => id === (btnId || 'vb-share-btn') ? btn : id === (statusId || 'vb-share-status') ? status : id === 'vb-share-status' ? decoy : null,
              addEventListener() {} },
  navigator: nav,
  fetch: (u, o) => { calls.fetched.push([u, o]); return Promise.resolve(); },
  setTimeout: () => 0, clearTimeout() {},
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(src, 'utf8'), ctx);
const ev = { currentTarget: btn };
click(ev); click(ev);
setTimeout(() => console.log(JSON.stringify({ calls, status: status.textContent, decoy: decoy.textContent, url: URL_ })), 20);
"""


def _run_share_js(mode: str, button_id: str = "vb-share-btn", status_id: str = "vb-share-status") -> dict:
    out = subprocess.run(
        ["node", "-e", _HARNESS, str(ROOT / "app/static/share.js"), mode, button_id, status_id],
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

    @pytest.mark.parametrize(
        "button_id,status_id",
        [("home-share-btn", "home-share-status"), ("learn-share-btn", "learn-share-status")],
    )
    def test_other_button_ids_write_status_to_named_element(self, button_id: str, status_id: str) -> None:
        r = _run_share_js("no_share", button_id, status_id)
        assert r["status"] == "COPIED"
        assert r["decoy"] == ""
