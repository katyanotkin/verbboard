"""Publish a snapshot of docs/marketing/personas.md for the admin personas page (issue #143).

    python -m tools.persona_publish            # snapshot dated today (UTC), stores the current git commit
    python -m tools.persona_publish --dry-run  # parse and print a summary, write nothing

Run it after updating personas.md at a review. Writes Firestore persona_snapshots/<date> (needs GCP auth);
re-running on the same day replaces that day's snapshot.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from core.persona_snapshot_service import parse_personas_markdown, publish_snapshot

PERSONAS_FILE = Path("docs/marketing/personas.md")


def _git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="parse and print, write nothing")
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    text = PERSONAS_FILE.read_text(encoding="utf-8")
    parsed = parse_personas_markdown(text)
    for persona in parsed["personas"]:
        statuses = [claim["status"] for claim in persona["claims"]]
        print(
            f"{persona['name']}: {len(statuses)} claims ({', '.join(sorted(set(statuses)))}); next test {persona['next_test'] or '-'}"
        )
    for row in parsed["unparsed_rows"]:
        print(f"UNREADABLE ROW: {row}")
    if parsed["unparsed_rows"]:
        return 1  # fix the table first: a dropped claim would show up as a false "removed" event
    if args.dry_run:
        return 0
    today = datetime.now(UTC).date().isoformat()
    publish_snapshot(text, today, _git_commit())
    print(f"Published persona_snapshots/{today}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
