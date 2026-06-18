"""
Bulk-call regen_forms for Hebrew verbs missing nikud in their forms field.

Reads verb_ids from a CSV produced by check_nikud (or a plain list -- one
verb_id per line, or the full check_nikud --missing output).

Usage (run while local server is up, or point at stage/prod):

    # From check_nikud --missing output piped in:
    python -m tools.check_nikud --missing | python -m tools.regen_forms_bulk

    # From the saved CSV:
    python -m tools.regen_forms_bulk --input missing-nikuud.csv

    # Against stage:
    python -m tools.regen_forms_bulk --input missing-nikuud.csv \\
        --base-url https://verbboard-stage.example.com
"""

from __future__ import annotations

import argparse
import re
import sys
import time

import requests

from core.admin_auth import ADMIN_SESSION_COOKIE, create_admin_session_token

_VERB_ID_RE = re.compile(r"\bhe_[a-z]+\b")


def _parse_verb_ids(lines: list[str]) -> list[str]:
    ids: list[str] = []
    seen: set[str] = set()
    for line in lines:
        for match in _VERB_ID_RE.finditer(line):
            vid = match.group()
            if vid not in seen:
                seen.add(vid)
                ids.append(vid)
    return ids


def main() -> None:
    parser = argparse.ArgumentParser(description="Bulk regen_forms for Hebrew verbs")
    parser.add_argument("--input", "-i", help="Input file (check_nikud output or plain list)")
    parser.add_argument(
        "--base-url",
        default="http://localhost:8001",
        help="Server base URL (default: http://localhost:8001)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=3.0,
        help="Seconds to wait between requests (default: 3 -- Claude rate limits)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print verb_ids without calling API")
    args = parser.parse_args()

    if args.input:
        with open(args.input) as fh:
            lines = fh.readlines()
    elif not sys.stdin.isatty():
        lines = sys.stdin.readlines()
    else:
        sys.exit("Provide --input or pipe check_nikud output.")

    verb_ids = _parse_verb_ids(lines)
    if not verb_ids:
        sys.exit("No he_* verb IDs found in input.")

    print(f"Found {len(verb_ids)} verbs to regen: {', '.join(verb_ids)}\n")

    if args.dry_run:
        print("Dry run -- no requests sent.")
        return

    token = create_admin_session_token()
    cookies = {ADMIN_SESSION_COOKIE: token}

    ok = failed = 0
    for i, verb_id in enumerate(verb_ids, 1):
        url = f"{args.base_url}/admin/api/verbs/{verb_id}/regen_forms"
        print(f"[{i}/{len(verb_ids)}] {verb_id} ... ", end="", flush=True)
        try:
            resp = requests.post(url, cookies=cookies, timeout=60)
            if resp.status_code == 200:
                print("OK")
                ok += 1
            else:
                print(f"FAILED {resp.status_code}: {resp.text[:120]}")
                failed += 1
        except Exception as exc:
            print(f"ERROR: {exc}")
            failed += 1

        if i < len(verb_ids):
            time.sleep(args.delay)

    print(f"\nDone: {ok} OK, {failed} failed.")
    if ok:
        print("Next: python -m tools.cache_audio --language he --bucket <bucket>")


if __name__ == "__main__":
    main()
