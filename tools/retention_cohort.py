"""Read-only signed-in retention cohort report (issue #112).

    python -m tools.retention_cohort
    python -m tools.retention_cohort --since 2026-10-01 --json

Needs GCP auth for Firestore. Nothing is written.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, date, datetime

from core.retention_service import build_retention_report, format_text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--since",
        help=(
            "only sessions on/after this date (YYYY-MM-DD). Users active before it are counted as new "
            "on their first in-window day, so start earlier than the cohorts you care about. "
            "Without it the whole analytics_sessions collection is read."
        ),
    )
    parser.add_argument("--json", action="store_true", help="print JSON instead of a table")
    args = parser.parse_args(argv)
    try:
        since = date.fromisoformat(args.since) if args.since else None
        report = build_retention_report(since, datetime.now(UTC).date())
    except Exception as exc:  # noqa: BLE001 - CLI boundary: report and exit 2
        print(f"could not run: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2) if args.json else format_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
