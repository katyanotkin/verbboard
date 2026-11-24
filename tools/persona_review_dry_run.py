"""Print the persona review issue body without opening an issue (issue #142).

    python -m tools.persona_review_dry_run

Reads Firestore (needs GCP auth), writes nothing, ignores whether a review is due.
"""

from __future__ import annotations

from datetime import UTC, datetime

from core.admin_report_service import build_report
from core.persona_review_service import build_issue_body, build_issue_title, review_window


def main() -> int:
    today = datetime.now(UTC).date()
    date_from, date_to = review_window(today)
    report = build_report(date_from.isoformat(), date_to.isoformat(), compare=True)
    print(build_issue_title(today))
    print()
    print(build_issue_body(report, today))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
