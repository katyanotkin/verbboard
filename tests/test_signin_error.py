"""Tests for the sign-in failure message in app/static/signin_error.js (issue #141).

Runs the real file in a Node subprocess against a stubbed document. Non-English
wording is deliberately not asserted (it may change after language review): only
keys, structure and behaviour. Browser integration is in
tests/e2e/test_signin_failure_message.py.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SIGNIN_ERROR_JS = REPO_ROOT / "app" / "static" / "signin_error.js"

# The script (argv[3]) runs with: api, body, doc, setUiLang, run() helpers, and must
# return a JSON-serialisable value (it may be async).
_HARNESS = r"""
'use strict';
const cfg = JSON.parse(process.argv[2]);
function makeEl(tag) {
  return {
    tag, attrs: {}, children: [], listeners: {}, className: '', id: '', textContent: '',
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    appendChild(c) { this.children.push(c); c.parent = this; return c; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    click() { (this.listeners.click || []).forEach(f => f()); },
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); },
  };
}
function walk(el, out) { out.push(el); el.children.forEach(c => walk(c, out)); return out; }
const body = makeEl('body');
global.window = {};
if (cfg.uiLang !== undefined) window.VB_UI_LANG = cfg.uiLang;
if (!cfg.noDocument) {
  global.document = {
    documentElement: { lang: cfg.htmlLang || '' },
    body: cfg.noBody ? null : body,
    createElement: makeEl,
    getElementById(id) { return walk(body, []).find(e => e.id === id) || null; },
  };
  window.document = global.document;
}
const unhandled = [];
process.on('unhandledRejection', e => unhandled.push(String(e)));
const api = require(process.argv[1]);
const banners = () => body.children.filter(c => c.id === 'vb-signin-error');
(async () => {
  const fn = new Function('api', 'body', 'banners', 'unhandled', 'return (async () => {' + process.argv[3] + '})();');
  const result = await fn(api, body, banners, unhandled);
  process.stdout.write(JSON.stringify(result === undefined ? null : result));
})().catch(e => { console.error(e); process.exit(1); });
"""


def _run(script: str, **cfg) -> object:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available in this environment")
    assert node is not None
    result = subprocess.run(
        [node, "-e", _HARNESS, str(SIGNIN_ERROR_JS), json.dumps(cfg), script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"node harness failed: {result.stderr}"
    return json.loads(result.stdout)


LANGS = ["en", "ru", "es", "he"]
KEYS = ["cancelled", "blocked", "network", "unavailable", "generic", "retry", "close"]


@pytest.mark.parametrize(
    "code,key",
    [
        ("popup_closed", "cancelled"),
        ("popup_blocked", "blocked"),
        ("network", "network"),
        ("sdk_unavailable", "unavailable"),
        ("unauthorized_domain", "generic"),
        ("redirect_failed", "generic"),
        ("other", "generic"),
        ("totally_unknown", "generic"),
        ("", "generic"),
    ],
)
def test_code_to_message_key(code, key):
    assert _run(f"return api.messageKey({json.dumps(code)});") == key


def test_every_locale_has_every_key_non_empty():
    strings = _run("return api.STRINGS;")
    assert sorted(strings) == sorted(LANGS)
    for lang in LANGS:
        for key in KEYS:
            assert isinstance(strings[lang].get(key), str) and strings[lang][key].strip(), (lang, key)


def test_english_texts():
    out = _run("return api.messageFor('popup_closed', 'en', '');")
    assert out["text"].startswith("Sign-in was cancelled")
    assert out["retry"] == "Try again"


def test_message_for_each_code_differs_by_key_per_locale():
    for lang in LANGS:
        texts = _run(
            "return ['popup_closed','popup_blocked','network','sdk_unavailable','other']"
            f".map(c => api.messageFor(c, '{lang}', '').text);"
        )
        assert len(set(texts)) == 5, lang


def test_language_pick_order():
    pick = "return api.messageFor('other', %s, %s).lang;"
    assert _run(pick % ('"ru"', '"es"')) == "ru"  # VB_UI_LANG wins
    assert _run(pick % ("undefined", '"es-MX"')) == "es"  # then html lang
    assert _run(pick % ("undefined", '""')) == "en"
    assert _run(pick % ('"fr"', '"de"')) == "en"  # unknown falls to en
    assert _run(pick % ('"fr"', '"he"')) == "he"  # unknown ui lang falls through to html lang


def test_show_reads_ui_lang_then_html_lang():
    out = _run("return api.show('other', null).getAttribute('dir') || null;", uiLang="he")
    assert out == "rtl"
    out = _run("return api.show('other', null).getAttribute('dir') || null;", htmlLang="he")
    assert out == "rtl"
    out = _run("return api.show('other', null).getAttribute('dir') || null;", uiLang="en", htmlLang="he")
    assert out is None
    out = _run("return api.show('other', null).getAttribute('dir') || null;")
    assert out is None


@pytest.mark.parametrize("lang", LANGS)
def test_dir_rtl_only_for_hebrew(lang):
    out = _run(
        "const b = api.show('other', () => {}); return {dir: b.getAttribute('dir') || null, role: b.getAttribute('role'), id: b.id};",
        uiLang=lang,
    )
    assert out["dir"] == ("rtl" if lang == "he" else None)
    assert out["role"] == "alert"
    assert out["id"] == "vb-signin-error"


def test_hostile_values_cannot_inject_markup():
    out = _run(
        """
        const evil = '<img src=x onerror=alert(1)>';
        window.VB_UI_LANG = evil;
        document.documentElement.lang = evil;
        const b = api.show(evil, () => {});
        const all = [];
        (function w(e) { all.push(e); e.children.forEach(w); })(b);
        return {
          tags: all.map(e => e.tag),
          texts: all.map(e => e.textContent),
          hasInner: all.some(e => 'innerHTML' in e),
          fellBack: api.messageFor(evil, evil, evil).lang,
        };
        """
    )
    assert out["tags"] == ["div", "span", "button", "button"]
    assert not out["hasInner"]
    assert out["fellBack"] == "en"
    assert not any("<" in t for t in out["texts"])


def test_second_show_replaces_first():
    out = _run(
        """
        api.show('popup_closed', () => {});
        api.show('network', () => {});
        return {count: banners().length, text: banners()[0].children[0].textContent,
                expected: api.messageFor('network', 'en', '').text};
        """
    )
    assert out["count"] == 1
    assert out["text"] == out["expected"]


def test_show_without_body_returns_null():
    assert _run("return api.show('other', () => {});", noBody=True) is None


def test_show_without_document_returns_null_and_dismiss_safe():
    assert _run("const r = api.show('other', () => {}); api.dismiss(); return r;", noDocument=True) is None


def test_retry_calls_callback_and_removes_banner():
    out = _run(
        """
        let calls = 0;
        const b = api.show('popup_closed', () => { calls++; });
        const retry = b.children[1];
        retry.click();
        await new Promise(r => setImmediate(r));
        return {calls, count: banners().length, retryText: retry.textContent,
                expected: api.messageFor('x', 'en', '').retry};
        """
    )
    assert out["calls"] == 1
    assert out["count"] == 0
    assert out["retryText"] == out["expected"]


def test_rejecting_retry_has_no_unhandled_rejection():
    out = _run(
        """
        const b = api.show('popup_closed', () => Promise.reject(new Error('popup closed again')));
        b.children[1].click();
        await new Promise(r => setTimeout(r, 20));
        return {unhandled, count: banners().length};
        """
    )
    assert out["unhandled"] == []
    assert out["count"] == 0


def test_close_button_removes_banner():
    out = _run(
        """
        const b = api.show('other', () => {});
        const close = b.children[2];
        const label = close.getAttribute('aria-label');
        close.click();
        return {count: banners().length, label};
        """
    )
    assert out["count"] == 0
    assert out["label"]


def test_no_callback_means_no_retry_button():
    out = _run(
        """
        const b = api.show('other');
        return {kids: b.children.map(c => c.tag), close: b.children[b.children.length - 1].textContent};
        """
    )
    assert out["kids"] == ["span", "button"]
    assert out["close"] == "×"


def test_dismiss_with_nothing_shown_does_not_throw():
    assert _run("api.dismiss(); api.dismiss(); return banners().length;") == 0
