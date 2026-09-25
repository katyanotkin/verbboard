"""Unit tests: shared JS URL builder (app/static/nav_urls.js) via a Node subprocess."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

NAV_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "nav_urls.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

_HARNESS = r"""
const cases = JSON.parse(process.argv[2]);
const nav = require(process.argv[1]);
const out = cases.map(function (c) {
  if (c.ui === null) { delete globalThis.VB_UI_LANG; } else { globalThis.VB_UI_LANG = c.ui; }
  return c.fn === 'verbsUrl' ? nav.verbsUrl(...c.args) : nav.learnUrl(...c.args);
});
process.stdout.write(JSON.stringify(out));
"""


def _run(cases):
    proc = subprocess.run(
        ["node", "-e", _HARNESS, str(NAV_JS), json.dumps(cases)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


def test_urls_exact_strings():
    cases = [
        {"fn": "verbsUrl", "ui": "ru", "args": ["es"]},
        {"fn": "verbsUrl", "ui": None, "args": ["es"]},
        {"fn": "verbsUrl", "ui": "", "args": ["es"]},
        {"fn": "learnUrl", "ui": "ru", "args": ["es", "es_ir", {"returnTo": "/verbs?language=es&ui_language=ru"}]},
        {"fn": "learnUrl", "ui": None, "args": ["es", "es_ir", {"returnTo": "/verbs?language=es"}]},
        {"fn": "learnUrl", "ui": "he", "args": ["en", "en_be"]},
        {"fn": "learnUrl", "ui": "he", "args": ["en", "en_be", {}]},
    ]
    assert _run(cases) == [
        "/verbs?language=es&ui_language=ru",
        "/verbs?language=es",
        "/verbs?language=es",
        "/learn?language=es&verb_id=es_ir&return_to=%2Fverbs%3Flanguage%3Des%26ui_language%3Dru&ui_language=ru",
        "/learn?language=es&verb_id=es_ir&return_to=%2Fverbs%3Flanguage%3Des",
        "/learn?language=en&verb_id=en_be&ui_language=he",
        "/learn?language=en&verb_id=en_be&ui_language=he",
    ]


def test_special_characters_are_encoded():
    cases = [
        {"fn": "learnUrl", "ui": "r&u", "args": ["e s", "a&b=c#d", {"returnTo": "/verbs?x=1&y=2"}]},
        {"fn": "learnUrl", "ui": None, "args": ["he", "he_הלך"]},
    ]
    assert _run(cases) == [
        "/learn?language=e%20s&verb_id=a%26b%3Dc%23d&return_to=%2Fverbs%3Fx%3D1%26y%3D2&ui_language=r%26u",
        "/learn?language=he&verb_id=he_%D7%94%D7%9C%D7%9A",
    ]
