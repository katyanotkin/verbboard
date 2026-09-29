"""Structural checks on app/static/common.css.

These are source-level (regex/brace-balance) checks, not rendered/browser
checks. Playwright/CDP's Emulation.setEmulatedMedia does not actually affect
`@media (display-mode: standalone)` evaluation in the Chromium version this
project's e2e suite runs against, so a live "is .nav-btn--ghost hidden in
standalone mode" browser test is not feasible here -- this file instead pins
the CSS source structure that behavior depends on.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
COMMON_CSS_PATH = REPO_ROOT / "app" / "static" / "common.css"

_STANDALONE_MEDIA_QUERY = "@media (display-mode: standalone) and (max-width: 639px)"


def _read_common_css() -> str:
    assert COMMON_CSS_PATH.is_file(), f"common.css not found at {COMMON_CSS_PATH}"
    return COMMON_CSS_PATH.read_text(encoding="utf-8")


def _extract_block(css_text: str, header: str) -> str:
    """Return the brace-balanced body of the first `header { ... }` block."""
    start = css_text.index(header)
    open_brace = css_text.index("{", start)
    depth = 0
    for index in range(open_brace, len(css_text)):
        char = css_text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return css_text[open_brace + 1 : index]
    raise AssertionError(f"unbalanced braces looking for the end of {header!r}")


def test_nav_btn_ghost_hidden_rule_is_nested_inside_standalone_media_block() -> None:
    """`.nav-btn--ghost { display: none; }` must live inside the exact same
    `@media (display-mode: standalone) and (max-width: 639px)` block that
    shows `.bottom-nav` -- so the two rules can never drift apart (one control
    hidden without the other one shown to replace it, or vice versa)."""
    css_text = _read_common_css()
    block_body = _extract_block(css_text, _STANDALONE_MEDIA_QUERY)

    assert re.search(r"\.bottom-nav\s*{", block_body), (
        ".bottom-nav display rule must be inside the standalone media block"
    )
    assert re.search(r"\.nav-btn--ghost\s*{\s*display:\s*none;\s*}", block_body), (
        ".nav-btn--ghost { display: none; } must be inside the same standalone media block"
    )


def test_nav_btn_ghost_hidden_rule_appears_exactly_once_in_the_stylesheet() -> None:
    """`.nav-btn--ghost` also has an unrelated base style rule elsewhere in the
    file (and a :hover variant) -- this checks specifically for the
    `display: none;` override, which must appear exactly once. A future
    accidental extraction/duplication of that specific rule outside the
    standalone media block would still pass the nesting check above (the
    original copy would still be there) -- this catches a second, unguarded
    copy anywhere else in the file."""
    css_text = _read_common_css()
    occurrences = len(re.findall(r"\.nav-btn--ghost\s*{\s*display:\s*none;\s*}", css_text))
    assert occurrences == 1, f"expected exactly one .nav-btn--ghost display:none rule, found {occurrences}"
