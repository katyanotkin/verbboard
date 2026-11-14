"""Form -> example jump on /learn (issue #123): scroll/highlight, cycling, unmatched rows, fill mode."""

from __future__ import annotations

import os

import pytest

import app.routes.learn as learn_route
import core.render as render_module
from tests.test_fill_practice import _es_verb

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(bool(os.getenv("E2E_BASE_URL")), reason="stubs the in-process server"),
]


@pytest.fixture(autouse=True)
def stub_verb(monkeypatch):
    async def _noop(*args, **kwargs):
        return None

    verb = _es_verb()
    # Two examples for the same cell so the button has two targets to cycle through.
    verb.examples.append(verb.examples[2].__class__(dst=verb.examples[2].dst, target=dict(verb.examples[2].target)))
    monkeypatch.setattr(learn_route, "load_entry_by_id", lambda **kwargs: verb)
    monkeypatch.setattr(learn_route, "prewarm_verb_audio_keys", _noop)
    monkeypatch.setattr(learn_route, "confirmed_form_keys", lambda *a, **k: set())
    monkeypatch.setattr(render_module, "confirmed_form_keys", lambda *a, **k: set())


def _open(browser, base, viewport=None):
    ctx = browser.new_context(viewport=viewport) if viewport else browser.new_context()
    ctx.route("**/api/**", lambda r: r.fulfill(status=200, content_type="application/json", body="{}"))
    ctx.route("**/audio/**", lambda r: r.fulfill(status=200, content_type="audio/mpeg", body=b""))
    page = ctx.new_page()
    page.set_default_timeout(30_000)
    page.goto(f"{base}/learn?language=es&verb_id=es_abrir&ui_language=en")
    return ctx, page


def test_jump_highlights_and_cycles_and_unmatched_rows_have_no_button(browser, live_server_url):
    ctx, page = _open(browser, live_server_url)
    try:
        buttons = page.locator(".jump-example-btn")
        total_rows = page.locator("tr[data-form]").count()
        assert 0 < buttons.count() < total_rows
        multi = page.locator(".jump-example-btn[data-jump-examples*=','] ")
        assert multi.count() >= 1
        indexes = multi.first.get_attribute("data-jump-examples").split(",")
        highlighted = []
        for _ in range(3):
            multi.first.click()
            highlighted.append(page.locator("tr.example-jump-highlight").get_attribute("data-example-index"))
        assert highlighted == [indexes[0], indexes[1], indexes[0]]
    finally:
        ctx.close()


def test_highlight_stays_until_next_tap(browser, live_server_url):
    """Issue #126: the highlight is not a short flash; it stays until the learner's next move."""
    ctx, page = _open(browser, live_server_url)
    try:
        page.locator(".jump-example-btn").first.click()
        page.wait_for_timeout(2000)
        assert page.locator("tr.example-jump-highlight").count() == 1
        page.mouse.click(5, 5)
        assert page.locator("tr.example-jump-highlight").count() == 0
    finally:
        ctx.close()


def test_mobile_play_buttons_share_one_column(browser, live_server_url):
    """Issue #125: at phone width play stays in the same column whether or not a row has a magnifier."""
    ctx, page = _open(browser, live_server_url, viewport={"width": 375, "height": 700})
    try:
        assert page.locator(".jump-example-btn").count() > 0
        lefts = page.evaluate(
            """() => [...document.querySelectorAll('.conj-form')]
                .map(c => c.querySelector('.btn'))
                .filter(Boolean)
                .map(b => Math.round(b.getBoundingClientRect().left))"""
        )
        assert len(lefts) > 3
        assert len(set(lefts)) == 1
    finally:
        ctx.close()


def test_buttons_hidden_in_fill_mode(browser, live_server_url):
    ctx, page = _open(browser, live_server_url)
    try:
        page.evaluate("document.getElementById('learn-page').classList.add('fill-mode')")
        assert page.locator(".jump-example-btn").first.is_hidden()
    finally:
        ctx.close()
