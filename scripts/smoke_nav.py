"""Nav link smoke tests — runs against a live URL.

Validates that every user-facing page renders its navigation links correctly
and that the feedback return_to roundtrip is intact.

Usage:
    python scripts/smoke_nav.py https://stage.verbboard.com
    python scripts/smoke_nav.py http://localhost:8001
"""

from __future__ import annotations

import sys
from urllib.parse import quote

import requests


def _check(
    url: str,
    name: str,
    require: tuple[str, ...] = (),
    exclude: tuple[str, ...] = (),
) -> None:
    try:
        resp = requests.get(url, timeout=15, allow_redirects=True)
    except requests.RequestException as exc:
        print(f"[ERROR] {name}: {exc}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"[FAIL]  {name}: HTTP {resp.status_code}")
        sys.exit(1)

    text = resp.text
    for s in require:
        if s not in text:
            print(f"[FAIL]  {name}: expected {s!r} not found")
            sys.exit(1)
    for s in exclude:
        if s in text:
            print(f"[FAIL]  {name}: unexpected {s!r} found in response")
            sys.exit(1)

    print(f"[OK]    {name}")


def main(base: str) -> None:
    base = base.rstrip("/")
    print(f"\nNav smoke: {base}\n")

    # ── home ──────────────────────────────────────────────────────────────
    _check(f"{base}/?language=en", "home: renders", require=("<form",))
    _check(f"{base}/?language=en", "home: about link", require=("/about",))
    _check(f"{base}/?language=en", "home: verbs link", require=("/verbs",))
    _check(
        f"{base}/?language=en",
        "home: feedback context",
        require=("page=home", "language=en"),
    )

    # ── verbs ─────────────────────────────────────────────────────────────
    _check(f"{base}/verbs?language=en", "verbs: renders", require=("vb-list",))
    _check(
        f"{base}/verbs?language=en&ui_language=en",
        "verbs: back to home",
        require=('href="/?language=en&amp;ui_language=en"',),
    )
    _check(f"{base}/verbs?language=en", "verbs: feedback context", require=("page=verbs",))

    # ── about ─────────────────────────────────────────────────────────────
    _check(f"{base}/about", "about: renders", require=("VerbBoard",))
    _check(f"{base}/about", "about: back to home", require=('href="/"',))
    _check(f"{base}/about", "about: feedback link", require=("page=about",))

    # ── feedback: return_to roundtrip ──────────────────────────────────────
    learn_url = quote("/learn?language=en&verb_id=en_go", safe="/")
    _check(
        f"{base}/feedback?page=learn&language=en&verb_id=en_go&return_to={learn_url}",
        "feedback: back link survives learn return_to",
        require=("feedback-link", "/learn"),
    )

    # ── feedback: open redirect guard ──────────────────────────────────────
    _check(
        f"{base}/feedback?return_to=https://evil.com/path",
        "feedback: external return_to blocked",
        exclude=("evil.com",),
    )
    _check(
        f"{base}/feedback?return_to=//evil.com/path",
        "feedback: protocol-relative return_to blocked",
        exclude=("evil.com",),
    )

    # ── learn (board) ──────────────────────────────────────────────────────
    _check(
        f"{base}/learn?language=en&verb_id=en_go",
        "learn: renders",
        require=("nav-btn",),
    )
    _check(
        f"{base}/learn?language=en&verb_id=en_go",
        "learn: feedback context",
        require=("page=learn", "en_go"),
    )
    _check(
        f"{base}/learn?language=en&verb_id=en_go",
        "learn: return_to URL-encoded in feedback href",
        require=("%3F", "%26"),
    )
    _check(
        f"{base}/learn?language=en&verb_id=en_go",
        "learn: voice toggle",
        require=("voice-toggle",),
    )
    _check(
        f"{base}/learn?language=en&verb_id=en_go",
        "learn: known button",
        require=("known-btn",),
    )

    # ── Hebrew verb board ──────────────────────────────────────────────────
    _check(
        f"{base}/learn?language=he&verb_id=he_lgdvl",
        "learn he_lgdvl (לִגְדּוֹל): renders",
        require=("nav-btn",),
    )
    _check(
        f"{base}/learn?language=he&verb_id=he_lbva",
        "learn he_lbva (לבוא): renders",
        require=("nav-btn",),
    )
    _check(
        f"{base}/learn?language=he&verb_id=he_lgdvl&ui_language=he",
        "learn he_lgdvl: Hebrew UI → Hebrew tense titles",
        require=("הווה", "עבר", "עתיד"),
    )
    _check(
        f"{base}/learn?language=he&verb_id=he_lgdvl&ui_language=ru",
        "learn he_lgdvl: Russian UI → Russian tense titles",
        require=("Настоящее", "Прошедшее", "Будущее"),
    )
    _check(
        f"{base}/learn?language=he&verb_id=he_lgdvl&ui_language=en",
        "learn he_lgdvl: English UI → English tense titles",
        require=("Present", "Past", "Future"),
    )
    _check(
        f"{base}/learn?language=he&verb_id=he_lbva&ui_language=ru",
        "learn he_lbva: Russian UI → Russian tense titles",
        require=("Настоящее", "Прошедшее", "Будущее"),
    )

    # ── UI language globe ──────────────────────────────────────────────────
    _check(
        f"{base}/?language=he",
        "home: UI language globe trigger present",
        require=("ui-lang-trigger", "ui-lang-dropdown"),
    )
    _check(
        f"{base}/?language=he&ui_language=ru",
        "home: Russian UI served correctly",
        require=("Выбрать глагол", "Я изучаю"),
        exclude=("Browse verbs",),
    )

    # ── Sort label not 'By frequency' ─────────────────────────────────────
    _check(
        f"{base}/verbs?language=he&ui_language=en",
        "verbs: sort label renamed from 'By frequency'",
        exclude=("By frequency",),
    )
    _check(
        f"{base}/verbs?language=he&ui_language=ru",
        "verbs: Russian sort label renamed from 'По частоте'",
        exclude=("По частоте",),
    )

    # ── Language switching ─────────────────────────────────────────────────
    resp = requests.get(
        f"{base}/set_language?language=en",
        allow_redirects=False,
        timeout=15,
    )
    if resp.status_code not in (301, 302, 307, 308):
        print(f"[FAIL]  set_language: expected redirect, got {resp.status_code}")
        sys.exit(1)
    location = resp.headers.get("location", "")
    if "language=en" not in location:
        print(f"[FAIL]  set_language: redirect missing language param: {location!r}")
        sys.exit(1)
    print("[OK]    set_language: redirects with language param")

    print("\nAll nav smoke tests passed.\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/smoke_nav.py <base_url>")
        sys.exit(1)
    main(sys.argv[1])
