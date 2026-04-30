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
        f"{base}/verbs?language=en",
        "verbs: back to home",
        require=('href="/?language=en"',),
    )
    _check(
        f"{base}/verbs?language=en", "verbs: feedback context", require=("page=verbs",)
    )

    # ── about ─────────────────────────────────────────────────────────────
    _check(f"{base}/about", "about: renders", require=("VerbBoard",))
    _check(f"{base}/about", "about: back to home", require=('href="/"',))
    _check(f"{base}/about", "about: feedback link", require=("page=about",))

    # ── feedback: return_to roundtrip ──────────────────────────────────────
    learn_url = quote("/learn?language=en&verb_id=en_go", safe="/")
    _check(
        f"{base}/feedback?page=learn&language=en&verb_id=en_go&return_to={learn_url}",
        "feedback: back link survives learn return_to",
        require=("secondary-link", "/learn"),
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

    print("\nAll nav smoke tests passed.\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/smoke_nav.py <base_url>")
        sys.exit(1)
    main(sys.argv[1])
