"""'Fill the form' practice page (/practice/fill).

The real route is served, but its Firestore-backed data builder and access check
are replaced with a small deterministic item set, so these tests cover the
client (grading flow, hidden-until-answered media, pool toggle, summary, RTL).
"""

from __future__ import annotations

import json
import os
import re

import pytest

import app.routes.practice_fill as fill_route
from core.fill_practice_service import ACCESS_OK, _fill_strings

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        bool(os.getenv("E2E_BASE_URL")),
        reason="stubs the in-process server (verb lookup / page data); not valid against a deployed URL",
    ),
]

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

ANSWERS = {
    "es": ["abrió", "comió", "vivió", "habló", "salió"],
    "he": ["הוֹלֵךְ", "אוֹכֵל", "כּוֹתֵב", "קוֹרֵא", "שׁוֹמֵעַ"],
}


def _stub_data(language: str, ui_language: str = "en", verb_id: str | None = None, count: int = 10) -> dict:
    answers = ANSWERS[language]
    items = []
    for n in range(count):
        verb = n % 5
        items.append(
            {
                "id": f"i{n}",
                "verbId": f"{language}_v{verb}",
                "lemma": f"lemma{verb}",
                "label": "Past, he/she",
                "prefix": f"Q{n} Ayer él ",
                "answer": answers[verb],
                "suffix": " la puerta.",
                "alternatives": [],
                "translation": f"Translation {n}",
                "audioSrc": f"/audio/{language}/{language}_v{verb}/female/stub_{n}.mp3",
            }
        )
    return {
        "language": language,
        "uiLanguage": ui_language,
        "verbId": verb_id,
        "studyDir": "rtl" if language == "he" else "ltr",
        "items": items,
        "strings": _fill_strings(ui_language),
        "limits": {"sessionSize": 8},
    }


@pytest.fixture
def stub_backend(monkeypatch):
    def install(language="es", **kwargs):
        monkeypatch.setattr(fill_route, "check_fill_access", lambda *a, **k: ACCESS_OK)
        monkeypatch.setattr(
            fill_route,
            "build_fill_page_data",
            lambda lang, ui, verb_id=None, **k: _stub_data(language, ui, verb_id, **kwargs),
        )

    return install


def _open(browser, base, *, language="es", ui="en", verb_id=None, user=None, viewport=None, local=None):
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
    if local:
        page.add_init_script(
            "; ".join(f"localStorage.setItem({json.dumps(k)}, {json.dumps(v)})" for k, v in local.items())
        )
    query = f"language={language}&ui_language={ui}" + (f"&verb_id={verb_id}" if verb_id else "")
    page.goto(f"{base}/practice/fill?{query}")
    page.wait_for_selector("#fill-input")
    return ctx, page, beacons, sessions


def _answer_for(page, language="es") -> str:
    number = int(page.inner_text(".fill-sentence").split()[0][1:])
    return ANSWERS[language][number % 5]


def _type_and_check(page, value):
    page.fill("#fill-input", value)
    page.keyboard.press("Enter")


def test_correct_flow_hides_media_until_answered(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, _, _ = _open(browser, live_server_url)
    try:
        assert page.locator(".fill-play").count() == 0
        assert page.locator(".fill-translation").count() == 0
        assert page.locator(".fill-reveal").is_hidden()
        _type_and_check(page, _answer_for(page))
        assert page.locator(".fill-feedback--correct").is_visible()
        assert page.locator(".fill-play").is_visible()
        assert "Translation" in page.inner_text(".fill-translation")
        assert page.locator(".fill-blank--filled").inner_text() == _answer_for(page)
        assert page.locator("#fill-feedback").get_attribute("aria-live") == "polite"
    finally:
        ctx.close()


def test_accent_missing_is_forgiven_with_exact_answer(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, _, _ = _open(browser, live_server_url)
    try:
        answer = _answer_for(page)
        _type_and_check(page, answer.replace("ó", "o").replace("í", "i"))
        feedback = page.locator(".fill-feedback--accent")
        assert feedback.is_visible()
        assert answer in feedback.inner_text()
        recent = json.loads(page.evaluate("localStorage.getItem('fill_recent:es')"))
        assert recent[-1]["ok"] is True
    finally:
        ctx.close()


def test_wrong_answer_shows_answer_and_struck_attempt(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, _, _ = _open(browser, live_server_url)
    try:
        answer = _answer_for(page)
        _type_and_check(page, "xyz")
        assert page.locator(".fill-feedback--wrong").is_visible()
        assert answer in page.inner_text(".fill-feedback")
        assert page.locator(".fill-attempt s").inner_text() == "xyz"
        recent = json.loads(page.evaluate("localStorage.getItem('fill_recent:es')"))
        assert recent[-1]["ok"] is False
    finally:
        ctx.close()


def test_empty_answer_is_not_graded(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, _, _ = _open(browser, live_server_url)
    try:
        page.click("#fill-primary")
        assert page.locator(".fill-hint-line").inner_text() != ""
        assert page.locator(".fill-feedback--wrong, .fill-feedback--correct").count() == 0
        assert page.evaluate("localStorage.getItem('fill_recent:es')") is None
    finally:
        ctx.close()


def test_hint_then_show_answer_counts_wrong(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, _, _ = _open(browser, live_server_url)
    try:
        answer = _answer_for(page)
        page.click(".fill-actions .fill-btn--secondary")
        assert answer[0] in page.inner_text(".fill-hint-line")
        page.click(".fill-actions .fill-btn--secondary")
        assert page.locator(".fill-feedback--wrong").is_visible()
        assert answer in page.inner_text(".fill-feedback")
        recent = json.loads(page.evaluate("localStorage.getItem('fill_recent:es')"))
        assert recent[-1]["ok"] is False
    finally:
        ctx.close()


def test_pool_defaults(browser, live_server_url, stub_backend):
    stub_backend()
    known = json.dumps([f"es_v{n}" for n in range(5)])
    ctx, page, _, _ = _open(browser, live_server_url, local={"known:es": known})
    try:
        assert page.locator('[data-pool="known"]').get_attribute("aria-pressed") == "true"
    finally:
        ctx.close()

    ctx, page, _, _ = _open(browser, live_server_url)
    try:
        assert page.locator('[data-pool="all"]').get_attribute("aria-pressed") == "true"
        assert page.locator('[data-pool="known"]').is_disabled()
    finally:
        ctx.close()

    ctx, page, _, _ = _open(browser, live_server_url, verb_id="es_v1", local={"known:es": known})
    try:
        assert page.locator("#fill-pool").is_hidden()
    finally:
        ctx.close()


def test_summary_again_and_session_post(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, beacons, sessions = _open(browser, live_server_url, user=_FAKE_USER)
    try:
        page.wait_for_function("window.VerbBoardAuth && window.VerbBoardAuth.currentUser()")
        for n in range(8):
            assert page.inner_text("#fill-progress-text").replace(" ", "") == f"{n + 1}/8"
            _type_and_check(page, _answer_for(page) if n < 6 else "nope")
            page.keyboard.press("Enter")
        assert page.locator(".fill-score").inner_text().replace(" ", "") == "6/8"
        assert page.locator(".fill-review-item").count() == 2
        page.wait_for_timeout(300)
        assert len(sessions) == 1
        assert sessions[0]["auth"] == "Bearer tok"
        assert sessions[0]["body"] == {"language": "es", "answers": 8, "correct": 6, "completed": True}
        assert sum("fill_started" in b for b in beacons) == 1
        page.click("#fill-again")
        assert page.locator("#fill-input").is_visible()
        assert page.inner_text("#fill-progress-text").replace(" ", "") == "1/8"
    finally:
        ctx.close()


def test_anonymous_sends_no_session(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, _, sessions = _open(browser, live_server_url)
    try:
        _type_and_check(page, "nope")
        page.goto("about:blank")
        assert sessions == []
    finally:
        ctx.close()


def test_hebrew_rtl_fits_375(browser, live_server_url, stub_backend):
    stub_backend(language="he")
    ctx, page, _, _ = _open(browser, live_server_url, language="he", ui="he", viewport={"width": 375, "height": 700})
    try:
        assert page.locator(".fill-sentence").get_attribute("dir") == "rtl"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        _type_and_check(page, re.sub("[\u0591-\u05c7]", "", ANSWERS["he"][0]))
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    finally:
        ctx.close()


def test_spanish_ui_buttons_fit_375(browser, live_server_url, stub_backend):
    stub_backend()
    ctx, page, _, _ = _open(browser, live_server_url, ui="es", viewport={"width": 375, "height": 700})
    try:
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        for selector in (".fill-input", "#fill-primary"):
            assert page.locator(selector).bounding_box()["height"] >= 44
        assert (
            float(page.evaluate("getComputedStyle(document.querySelector('.fill-input')).fontSize.replace('px','')"))
            >= 16
        )
    finally:
        ctx.close()
