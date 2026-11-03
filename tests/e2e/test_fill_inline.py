"""In-place "Fill in the blank" mode on /learn (toggle, ?mode=fill, grading, per-row unlock, beacons).

The real /learn route is served with the verb lookup replaced by a small tagged Spanish verb, so nothing
here depends on live Firestore data. Firebase is stubbed like tests/e2e/test_fill_practice.py.
"""

from __future__ import annotations

import json

import pytest

import app.routes.learn as learn_route
import core.render as render_module
from tests.test_fill_practice import _es_verb

pytestmark = pytest.mark.e2e

_CONFIG_STUB = """
Object.defineProperty(window, 'FIREBASE_WEB_CONFIG', {
  get: function () { return { apiKey: 'test', projectId: 'test' }; },
  set: function () {},
});
"""

_FIREBASE_STUB = """
window.firebase = {
  initializeApp: function () {},
  auth: function () {
    return {
      onAuthStateChanged: function (cb) { setTimeout(function () { cb(__USER__); }, 0); },
      getRedirectResult: function () { return Promise.resolve({ user: null }); },
    };
  },
};
window.firebase.auth.GoogleAuthProvider = function () { this.setCustomParameters = function () {}; };
"""

_FAKE_USER = "{ uid: 'u1', getIdToken: function () { return Promise.resolve('tok'); } }"


@pytest.fixture(autouse=True)
def stub_verb(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(learn_route, "load_entry_by_id", lambda **kwargs: _es_verb())
    monkeypatch.setattr(learn_route, "prewarm_verb_audio_keys", _noop)
    monkeypatch.setattr(learn_route, "confirmed_form_keys", lambda *a, **k: set())
    monkeypatch.setattr(render_module, "confirmed_form_keys", lambda *a, **k: set())


def _open(browser, base, *, query="", ui="en", user=None, viewport=None):
    ctx = browser.new_context(**({"viewport": viewport} if viewport else {}))
    beacons: list[str] = []
    sessions: list[dict] = []

    def _analytics(route):
        if "practice_event" in route.request.url:
            beacons.append(route.request.post_data or "")
        route.fulfill(status=204)

    def _fill_session(route):
        sessions.append({"auth": route.request.headers.get("authorization"), "body": route.request.post_data_json})
        route.fulfill(status=200, content_type="application/json", body="{}")

    ctx.route("**/api/analytics/**", _analytics)
    ctx.route("**/api/progress/**", lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
    ctx.route("**/api/progress/fill_session", _fill_session)
    ctx.route("**/audio/**", lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=b""))
    page = ctx.new_page()
    page.set_default_timeout(30_000)
    page.route("https://www.gstatic.com/firebasejs/**", lambda r: r.abort())
    page.add_init_script(_CONFIG_STUB)
    page.add_init_script(_FIREBASE_STUB.replace("__USER__", user or "null"))
    page.goto(f"{base}/learn?language=es&verb_id=es_abrir&ui_language={ui}{query}")
    page.wait_for_selector("#fill-toggle:not([hidden])")
    return ctx, page, beacons, sessions


def _row(page, n):
    return page.locator("tr.fill-row").nth(n)


def _no_horizontal_scroll(page) -> bool:
    return page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")


def test_toggle_on_blanks_rows_and_locks_media_until_answered(browser, live_server_url):
    ctx, page, _, _ = _open(browser, live_server_url)
    try:
        assert page.locator("#fill-banner").is_hidden()
        hint = page.locator("#fill-toggle-wrap .help-hint-trigger")
        assert hint.is_visible()
        hint.click()
        assert page.locator("#fill-toggle-wrap .help-hint-panel").is_visible()
        page.click("#fill-toggle")
        assert page.get_attribute("#fill-toggle", "aria-pressed") == "true"
        assert page.locator("#fill-banner").is_visible()
        assert page.locator(".fill-inline-input").count() == 3
        assert "mode=fill" in page.url
        row = _row(page, 0)
        # Translations are independent of fill mode: hidden until the translations toggle is used.
        assert row.locator(".example-translation").is_hidden()
        assert float(row.locator("td").last.evaluate("e => getComputedStyle(e).opacity")) < 1
        assert row.locator(".fill-chip").inner_text() == "Preterite · él/ella/Ud."

        row.locator(".fill-inline-input").fill("abrió")
        page.keyboard.press("Enter")
        assert row.locator(".fill-feedback--correct").is_visible()
        assert row.locator("mark.fill-answer--correct").inner_text() == "abrió"
        assert row.locator(".example-src").inner_text() == "El camarero abrió una botella."
        assert row.locator(".example-translation").inner_text() == "The waiter opened a bottle."
        assert row.locator(".example-translation").is_hidden()  # answering does not reveal it
        assert float(row.locator("td").last.evaluate("e => getComputedStyle(e).opacity")) == 1
        # The next row stays locked.
        assert float(_row(page, 1).locator("td").last.evaluate("e => getComputedStyle(e).opacity")) < 1
    finally:
        ctx.close()


def test_accent_only_and_wrong_answers(browser, live_server_url):
    ctx, page, beacons, _ = _open(browser, live_server_url)
    try:
        page.click("#fill-toggle")
        _row(page, 0).locator(".fill-inline-input").fill("abrio")
        _row(page, 0).locator(".fill-check-btn").click()
        feedback = _row(page, 0).locator(".fill-feedback--accent")
        assert feedback.is_visible() and "abrió" in feedback.inner_text()
        _row(page, 1).locator(".fill-inline-input").fill("zzz")
        _row(page, 1).locator(".fill-check-btn").click()
        wrong = _row(page, 1).locator(".fill-feedback--wrong")
        assert wrong.locator("s").inner_text() == "zzz" and "abrimos" in wrong.inner_text()
        _row(page, 2).locator(".fill-show-link").click()
        assert _row(page, 2).locator(".fill-feedback--wrong").is_visible()
        recent = json.loads(page.evaluate("localStorage.getItem('fill_recent:es')"))
        assert [entry["ok"] for entry in recent] == [True, False, False]
        assert recent[0]["id"].startswith("es_abrir:")
        assert len(beacons) == 1 and "fill_started" in beacons[0]
    finally:
        ctx.close()


def test_mode_fill_url_opens_in_fill_mode_and_toggle_off_restores(browser, live_server_url):
    ctx, page, _, _ = _open(browser, live_server_url, query="&mode=fill")
    try:
        assert page.locator("#fill-banner").is_visible()
        assert page.locator(".fill-inline-input").count() == 3
        assert page.locator("form.voice-control input[name=mode]").get_attribute("value") == "fill"
        page.click("#fill-toggle")
        assert page.locator(".fill-inline-input").count() == 0
        assert "mode=" not in page.url
        assert page.locator("form.voice-control input[name=mode]").count() == 0
        assert page.locator("tr.fill-row").first.locator(".example-src").inner_text() == (
            "El camarero abrió una botella."
        )
    finally:
        ctx.close()


def test_answered_state_survives_toggle_off_and_on(browser, live_server_url):
    ctx, page, _, _ = _open(browser, live_server_url, query="&mode=fill")
    try:
        _row(page, 0).locator(".fill-inline-input").fill("abrió")
        page.keyboard.press("Enter")
        page.click("#fill-toggle")
        assert _row(page, 0).get_attribute("class").count("fill-answered") == 1
        page.click("#fill-toggle")
        assert _row(page, 0).locator("mark.fill-answer--correct").is_visible()
        assert page.locator(".fill-inline-input").count() == 2
    finally:
        ctx.close()


def test_signed_in_sends_inline_totals_once_on_hide(browser, live_server_url):
    ctx, page, _, sessions = _open(browser, live_server_url, query="&mode=fill", user=_FAKE_USER)
    try:
        page.wait_for_timeout(300)
        _row(page, 0).locator(".fill-inline-input").fill("abrió")
        page.keyboard.press("Enter")
        _row(page, 1).locator(".fill-inline-input").fill("zzz")
        page.keyboard.press("Enter")
        page.evaluate(
            "Object.defineProperty(document,'visibilityState',{value:'hidden',configurable:true});"
            "document.dispatchEvent(new Event('visibilitychange'))"
        )
        page.wait_for_timeout(500)
        assert len(sessions) == 1
        assert sessions[0]["body"] == {
            "language": "es",
            "answers": 2,
            "correct": 1,
            "completed": False,
            "mode": "inline",
        }
        assert sessions[0]["auth"] == "Bearer tok"
    finally:
        ctx.close()


def test_anonymous_sends_no_progress(browser, live_server_url):
    ctx, page, _, sessions = _open(browser, live_server_url, query="&mode=fill")
    try:
        _row(page, 0).locator(".fill-inline-input").fill("abrió")
        page.keyboard.press("Enter")
        page.evaluate("window.dispatchEvent(new Event('pagehide'))")
        page.wait_for_timeout(300)
        assert sessions == []
    finally:
        ctx.close()


@pytest.mark.parametrize("ui", ["en", "es"])
def test_375px_no_horizontal_scroll_and_buttons_fit(browser, live_server_url, ui):
    ctx, page, _, _ = _open(browser, live_server_url, query="&mode=fill", ui=ui, viewport={"width": 375, "height": 800})
    try:
        assert _no_horizontal_scroll(page)
        for selector in (".fill-check-btn", ".fill-show-link", ".fill-chip", ".fill-inline-input"):
            box = page.locator(selector).first.bounding_box()
            assert box is not None and box["x"] >= 0 and box["x"] + box["width"] <= 375, selector
        font_px = page.locator(".fill-inline-input").first.evaluate("e => parseFloat(getComputedStyle(e).fontSize)")
        assert font_px >= 16
        _row(page, 0).locator(".fill-inline-input").fill("zzz")
        page.keyboard.press("Enter")
        assert _no_horizontal_scroll(page)
    finally:
        ctx.close()


def test_unanswered_audio_is_inert_and_focus_moves_on(browser, live_server_url):
    ctx, page, _, _ = _open(browser, live_server_url, query="&mode=fill")
    try:
        assert _row(page, 0).locator("td").last.evaluate("e => e.inert") is True
        _row(page, 0).locator(".fill-inline-input").fill("abrió")
        page.keyboard.press("Enter")
        assert _row(page, 0).locator("td").last.evaluate("e => e.inert") is False
        assert page.evaluate("document.activeElement.classList.contains('fill-inline-input')")
        assert page.evaluate("document.querySelector('[aria-live=polite].fill-sr-only')") is not None
        label = _row(page, 1).locator(".fill-inline-input").get_attribute("aria-label")
        assert label.startswith("abrir")
    finally:
        ctx.close()
