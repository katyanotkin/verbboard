"""Tests for the "new version available" banner in app/static/pwa.js.

Logic (cases 1-4) runs in a Node subprocess against the real pwa.js with a
stubbed navigator.serviceWorker / registration / document. Not automatable:
a real service-worker update flow (needs two deployed sw.js versions) and
standalone display-mode placement above the bottom nav (Playwright cannot
emulate display-mode for @media); both stay manual. Rendering at 375px is in
tests/e2e/test_update_banner.py.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PWA_JS = REPO_ROOT / "app" / "static" / "pwa.js"

_HARNESS = r"""
'use strict';
const cfg = JSON.parse(process.argv[2]);
const ops = JSON.parse(process.argv[3]);

function makeEl(tag) {
  const el = {
    tag, attrs: {}, children: [], listeners: {}, className: '', id: '',
    textContent: '', removed: false,
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k]; },
    appendChild(c) { this.children.push(c); c.parent = this; return c; },
    addEventListener(t, f) { (this.listeners[t] = this.listeners[t] || []).push(f); },
    click() { (this.listeners.click || []).forEach(f => f()); },
    remove() { this.removed = true; if (this.parent) this.parent.children = this.parent.children.filter(c => c !== this); },
  };
  return el;
}
function walk(el, out) { out.push(el); el.children.forEach(c => walk(c, out)); return out; }

const body = makeEl('body');
const docListeners = {};
global.document = {
  visibilityState: 'visible',
  documentElement: { lang: cfg.htmlLang || '' },
  body,
  createElement: makeEl,
  getElementById(id) { return walk(body, []).find(e => e.id === id) || null; },
  addEventListener(t, f) { (docListeners[t] = docListeners[t] || []).push(f); },
};
let now = 1000000;
Date.now = () => now;
const intervals = [];
global.setInterval = (f, ms) => { intervals.push({ f, ms }); return intervals.length; };

const regListeners = {};
const registration = {
  waiting: cfg.waiting ? makeWorker('installed') : null,
  installing: cfg.installing ? makeWorker('installing') : null,
  updateCalls: 0,
  addEventListener(t, f) { (regListeners[t] = regListeners[t] || []).push(f); },
  update() {
    this.updateCalls++;
    return cfg.updateRejects ? Promise.reject(new Error('offline')) : Promise.resolve();
  },
};
function makeWorker(state) {
  const l = [];
  return { state, addEventListener(t, f) { if (t === 'statechange') l.push(f); },
           setState(s) { this.state = s; l.forEach(f => f()); } };
}
let reloads = 0;
global.location = { reload() { reloads++; } };
global.window = { VB_UI_LANG: cfg.uiLang };
if (cfg.uiLang === undefined) delete global.window.VB_UI_LANG;
Object.defineProperty(global, 'navigator', { configurable: true, writable: true, value: cfg.noSW ? {} : {
  serviceWorker: {
    controller: cfg.controller ? {} : null,
    register() { return Promise.resolve(registration); },
  },
}});
global.window.matchMedia = () => ({ matches: false });

(async () => {
  require(process.argv[1]);
  await new Promise(r => setImmediate(r));
  const out = [];
  const banners = () => body.children.filter(c => c.id === 'vb-update-banner');
  for (const op of ops) {
    if (op[0] === 'show') window.VerbBoardUpdate.show();
    else if (op[0] === 'updatefound') {
      registration.installing = makeWorker('installing');
      (regListeners.updatefound || []).forEach(f => f());
    }
    else if (op[0] === 'installing_state') registration.installing.setState(op[1]);
    else if (op[0] === 'advance') now += op[1];
    else if (op[0] === 'visible') { document.visibilityState = 'visible'; (docListeners.visibilitychange || []).forEach(f => f()); }
    else if (op[0] === 'hidden') { document.visibilityState = 'hidden'; (docListeners.visibilitychange || []).forEach(f => f()); }
    else if (op[0] === 'tick') intervals.forEach(i => i.f());
    else if (op[0] === 'click_update') document.getElementById('vb-update-reload').click();
    else if (op[0] === 'click_dismiss') document.getElementById('vb-update-dismiss').click();
    await new Promise(r => setImmediate(r));
  }
  const b = banners()[0];
  process.stdout.write(JSON.stringify({
    count: banners().length,
    reloads,
    updateCalls: registration.updateCalls,
    intervalMs: intervals.map(i => i.ms),
    banner: b ? {
      role: b.attrs.role, live: b.attrs['aria-live'], dir: b.attrs.dir || null,
      text: b.children[0].textContent, button: b.children[1].textContent,
      close: b.children[2].attrs['aria-label'],
    } : null,
  }));
})().catch(e => { console.error(e); process.exit(1); });
"""

HOUR = 60 * 60 * 1000


def _run(cfg: dict, ops: list) -> dict:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not available in this environment")
    assert node is not None
    result = subprocess.run(
        [node, "-e", _HARNESS, str(PWA_JS), json.dumps(cfg), json.dumps(ops)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"node harness failed: {result.stderr}"
    return json.loads(result.stdout)


@pytest.mark.parametrize(
    "lang,text,button,close",
    [
        ("en", "A new version is available", "Update", "Close"),
        ("ru", "Доступна новая версия", "Обновить", "Закрыть"),
        ("es", "Hay una nueva versión disponible", "Actualizar", "Cerrar"),
        ("he", "גרסה חדשה זמינה", "עדכון", "סגירה"),
    ],
)
def test_strings_per_language(lang, text, button, close):
    out = _run({"uiLang": lang, "controller": True}, [["show"]])
    b = out["banner"]
    assert (b["text"], b["button"], b["close"]) == (text, button, close)
    assert b["role"] == "status" and b["live"] == "polite"
    assert b["dir"] == ("rtl" if lang == "he" else None)


def test_language_order_ui_lang_then_html_lang_then_en():
    assert _run({"uiLang": "ru", "htmlLang": "es"}, [["show"]])["banner"]["button"] == "Обновить"
    assert _run({"htmlLang": "es-MX"}, [["show"]])["banner"]["button"] == "Actualizar"
    assert _run({}, [["show"]])["banner"]["button"] == "Update"
    assert _run({"uiLang": "fr", "htmlLang": "es"}, [["show"]])["banner"]["button"] == "Update"


def test_no_banner_on_first_install():
    out = _run(
        {"controller": False, "installing": True},
        [["updatefound"], ["installing_state", "installed"], ["installing_state", "activated"]],
    )
    assert out["count"] == 0


def test_no_banner_on_first_install_with_waiting_worker():
    assert _run({"controller": False, "waiting": True}, [])["count"] == 0


def test_banner_when_controlled_page_sees_worker_activate():
    out = _run(
        {"controller": True},
        [["updatefound"], ["installing_state", "installed"]],
    )
    assert out["count"] == 0  # installed is not enough
    out = _run(
        {"controller": True},
        [["updatefound"], ["installing_state", "installed"], ["installing_state", "activated"]],
    )
    assert out["count"] == 1
    assert out["reloads"] == 0  # never auto-reloads


def test_banner_when_waiting_worker_already_present():
    assert _run({"controller": True, "waiting": True}, [])["count"] == 1


def test_banner_when_installing_worker_activates_after_register():
    out = _run({"controller": True, "installing": True}, [])
    assert out["count"] == 0


def test_no_banner_without_service_worker_support():
    out = _run({"noSW": True}, [])
    assert out["count"] == 0


def test_update_button_reloads_dismiss_removes_idempotent():
    out = _run({"controller": True}, [["show"], ["show"]])
    assert out["count"] == 1
    out = _run({"controller": True}, [["show"], ["click_update"]])
    assert out["reloads"] == 1
    out = _run({"controller": True}, [["show"], ["click_dismiss"]])
    assert out["count"] == 0 and out["reloads"] == 0


def test_update_rejection_offline_is_silent():
    out = _run(
        {"controller": True, "updateRejects": True},
        [["tick"]],
    )
    assert out["updateCalls"] == 1  # harness would exit non-zero on unhandled rejection


def test_hourly_timer_checks_for_update():
    out = _run({"controller": True}, [["tick"]])
    assert out["intervalMs"] == [HOUR]
    assert out["updateCalls"] == 1


def test_visibility_check_throttled_to_hourly():
    # Immediately visible: no check.
    assert _run({"controller": True}, [["visible"]])["updateCalls"] == 0
    # Just under an hour: no check.
    assert _run({"controller": True}, [["advance", HOUR - 1000], ["visible"]])["updateCalls"] == 0
    # An hour later: one check; a second return right after is throttled.
    out = _run({"controller": True}, [["advance", HOUR], ["visible"], ["visible"]])
    assert out["updateCalls"] == 1
    # Hidden never checks.
    assert _run({"controller": True}, [["advance", HOUR], ["hidden"]])["updateCalls"] == 0


def test_timer_skips_check_when_page_hidden():
    out = _run({"controller": True}, [["hidden"], ["tick"]])
    assert out["updateCalls"] == 0
