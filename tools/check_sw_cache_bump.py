"""Pre-commit guard: fail if a PRECACHE-listed static file changed without
bumping sw.js's CACHE version in the same commit.

sw.js's fetch handler is cache-first with no clients.claim(), so an
unchanged CACHE name means returning PWA users silently keep the old file
forever. This exact bug shipped four times (2026-07-29/30/31, then
2026-09-15) despite being documented in CLAUDE.md -- "remember to bump it"
was empirically not enough, hence this mechanical check.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SW_PATH = "app/static/sw.js"

CACHE_RE = re.compile(r'const CACHE = "([^"]+)"')
PRECACHE_RE = re.compile(r"const PRECACHE = \[(.*?)\]", re.DOTALL)
ENTRY_RE = re.compile(r'"(/static/[^"]+)"')


def _staged_files() -> set[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return {line.strip() for line in out.splitlines() if line.strip()}


def _file_at_ref(ref: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def _parse_precache(sw_text: str) -> set[str]:
    match = PRECACHE_RE.search(sw_text)
    if not match:
        return set()
    return set(ENTRY_RE.findall(match.group(1)))


def _parse_cache_version(sw_text: str) -> str | None:
    match = CACHE_RE.search(sw_text)
    return match.group(1) if match else None


def main() -> int:
    staged = _staged_files()

    head_sw = _file_at_ref("HEAD", SW_PATH)
    if head_sw is None:
        # sw.js is new/untracked at HEAD -- nothing to compare against.
        return 0

    precache_web_paths = _parse_precache(head_sw)
    # Map "/static/foo.js" -> "app/static/foo.js" to match git paths.
    precache_repo_paths = {f"app{p}" for p in precache_web_paths}

    changed_precache_files = sorted(staged & precache_repo_paths)
    if not changed_precache_files:
        return 0

    staged_sw = _file_at_ref(":0", SW_PATH) if SW_PATH in staged else head_sw
    old_version = _parse_cache_version(head_sw)
    new_version = _parse_cache_version(staged_sw) if staged_sw else old_version

    if SW_PATH in staged and old_version != new_version:
        return 0

    print(
        "check_sw_cache_bump: PRECACHE-listed file(s) changed without bumping "
        f"sw.js's CACHE version ({old_version!r} unchanged):\n  "
        + "\n  ".join(changed_precache_files)
        + "\n\nReturning PWA users are served cache-first and will silently keep "
        "the old file forever until CACHE changes. Bump CACHE in app/static/sw.js "
        "(and the matching assertion in tests/test_safe_return_and_privacy.py) "
        "in this same commit.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
