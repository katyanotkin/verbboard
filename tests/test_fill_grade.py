"""Unit tests: fill-the-form grading (app/static/fill_grade.js) via a Node subprocess."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

GRADE_JS = Path(__file__).resolve().parent.parent / "app" / "static" / "fill_grade.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

_HARNESS = r"""
const cases = JSON.parse(process.argv[2]);
const g = require(process.argv[1]);
process.stdout.write(JSON.stringify(cases.map(function (c) {
  return g.grade(c[0], c[1], c[2], c[3] || []);
})));
"""


def _grades(cases):
    proc = subprocess.run(
        ["node", "-e", _HARNESS, str(GRADE_JS), json.dumps(cases)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(proc.stdout)


CASES = [
    # Spanish: accent forgiven, exact answer still correct
    ("es", "abrió", "abrió", "correct"),
    ("es", "abrio", "abrió", "accent"),
    ("es", "ABRIÓ", "abrió", "correct"),
    ("es", "abri", "abrió", "wrong"),
    ("es", "  abrió  ", "abrió", "correct"),
    # Turkish dotted/dotless i and friends
    ("tr", "ISTIYORUM", "istiyorum", "accent"),
    ("tr", "ISTIYORUM", "ıstıyorum", "correct"),
    ("tr", "yapiyorum", "yapıyorum", "accent"),
    ("tr", "yapıyorum", "yapıyorum", "correct"),
    ("tr", "İstiyorum", "istiyorum", "correct"),
    ("tr", "gidiyorsun", "gidiyorsun", "correct"),
    ("tr", "gorduk", "gördük", "accent"),
    ("tr", "sevdim", "sevdin", "wrong"),
    # Russian: ё == е and stress marks ignored, и/й stay distinct
    ("ru", "идет", "идёт", "correct"),
    ("ru", "иде́т", "идёт", "correct"),
    ("ru", "Идёт", "идёт", "correct"),
    ("ru", "мои", "мой", "wrong"),
    # Hebrew: niqqud ignored on both sides
    ("he", "הולך", "הוֹלֵךְ", "correct"),
    ("he", "הוֹלֵךְ", "הולך", "correct"),
    ("he", "הולכת", "הולך", "wrong"),
    # French: optional subject pronoun, elision, accent forgiveness
    ("fr", "je mange", "mange", "correct"),
    ("fr", "j'ai", "ai", "correct"),
    ("fr", "j’ai", "ai", "correct"),
    ("fr", "ils mangent", "mangent", "correct"),
    ("fr", "elle va", "va", "correct"),
    ("fr", "il a", "a", "correct"),
    ("fr", "je mange", "mangeons", "wrong"),
    ("fr", "ete", "été", "accent"),
    ("fr", "j'ete", "été", "accent"),
    # English: case-insensitive
    ("en", "Went", "went", "correct"),
    ("en", "goed", "went", "wrong"),
    # Alternatives and slash-separated answers
    ("es", "fuese", "fuera", "wrong"),
    ("es", "fuese", "fuera/fuese", "correct"),
    ("es", "fuese", "fuera", "correct", ["fuese"]),
    ("es", "fuése", "fuera", "accent", ["fuese"]),
    # Apostrophes and whitespace
    ("en", "i’m", "I'm", "correct"),
    ("en", "I   am", "I am", "correct"),
    # Empty is never graded
    ("es", "", "abrió", "empty"),
    ("es", "   ", "abrió", "empty"),
]


def test_grading_table():
    payload = [[c[0], c[1], c[2], c[4] if len(c) > 4 else []] for c in CASES]
    assert _grades(payload) == [c[3] for c in CASES]
