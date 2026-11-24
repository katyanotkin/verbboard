"""Scheduled persona review (issue #142).

Cloud Scheduler calls `POST /internal/persona-review` weekly. A cron expression cannot say "every 21
days", so this module decides whether a review is due from the dated docs it leaves in
`persona_reviews/{YYYY-MM-DD}`. When due it snapshots the last 21 days from the Reports figures and
opens a GitHub issue holding the numbers and the checklist from `.claude/skills/persona-review/SKILL.md`.
It never edits `docs/marketing/personas.md`: the review itself stays a human or agent decision.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import date, timedelta
from typing import Any

from google.api_core.exceptions import AlreadyExists

from core.admin_report_service import build_report
from core.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

REVIEW_INTERVAL_DAYS = 21
COLLECTION = "persona_reviews"
PERSONAS_PATH = "docs/marketing/personas.md"
SKILL_PATH = ".claude/skills/persona-review/SKILL.md"
GITHUB_TIMEOUT_SECONDS = 10

# Figures worth reading at every review: (key in the report's flat delta table, label).
_HEADLINE_METRICS = (
    ("non_bot_sessions", "Non-bot sessions"),
    ("registered.sessions_with_uid", "Sessions with an account"),
    ("registered.new_registrations", "New registrations"),
    ("twa.sessions", "Google Play app sessions"),
    ("engagement.practice_started", "Practice started"),
    ("engagement.practice_completed", "Practice completed"),
    ("engagement.practice_gate_shown", "Practice gate shown"),
    ("engagement.share_tapped", "Share tapped"),
    ("engagement.share_landed", "Share landed (lower bound)"),
    ("engagement.votd_rate", "Verb of the Day click rate %"),
    ("sign_in.tapped", "Sign-in tapped"),
    ("sign_in.tapped_signed_in", "Sign-in tapped, then signed in"),
    ("sign_in.failed_sessions", "Sessions with a recorded sign-in failure"),
)

CHECKLIST = (
    "Read each persona's signal below with its n; mark a claim `observed` only with a named number "
    "(about 30 sessions or more), an issue or a feedback item.",
    f"Update claim status, evidence, n and last-checked in `{PERSONAS_PATH}`; flag claims not checked for over 60 days.",
    "Move refuted claims to Retired claims with one line on what we learned.",
    "Set each persona's Next test to its open issue; close finished experiment issues with the closing-comment form.",
    "Rebuild `docs/marketing/verbboard-personas.html` from the markdown (writer) and commit with the issue numbers.",
    "Propose merging or dropping a persona that never shows in the numbers.",
)


def review_window(today: date) -> tuple[date, date]:
    """The 21 complete days before `today` (today itself is still filling up)."""
    window_end = today - timedelta(days=1)
    return window_end - timedelta(days=REVIEW_INTERVAL_DAYS - 1), window_end


def is_due(review_dates: list[str], today: date) -> bool:
    """True when no review was opened within the last REVIEW_INTERVAL_DAYS days."""
    latest: date | None = None
    for raw in review_dates:
        try:
            parsed = date.fromisoformat(raw)
        except ValueError:
            continue
        if latest is None or parsed > latest:
            latest = parsed
    return latest is None or (today - latest).days >= REVIEW_INTERVAL_DAYS


def build_issue_title(today: date) -> str:
    return f"Persona review {today.isoformat()}"


def _format_number(value: Any) -> str:
    if isinstance(value, float) and not value.is_integer():
        return f"{value:.1f}"
    return str(int(value)) if isinstance(value, (int, float)) else str(value)


def build_issue_body(report: dict[str, Any], today: date) -> str:
    window = report["range"]
    deltas = report.get("deltas", {})
    lines = [
        f"Opened automatically from Google Cloud Scheduler (#142). Window: {window['date_from']} to "
        f"{window['date_to']} ({window['days']} days), compared with the 21 days before it.",
        "",
        f"Source of truth: `{PERSONAS_PATH}`. Steps: `{SKILL_PATH}`.",
        "",
        "## Figures (non-bot sessions, not visitors; referrer counts are lower bounds)",
        "",
        "| Metric | This window | Previous | Change |",
        "|---|---|---|---|",
    ]
    for key, label in _HEADLINE_METRICS:
        entry = deltas.get(key)
        if entry is None:
            continue
        change = entry["delta"]
        sign = "+" if change > 0 else ""
        lines.append(
            f"| {label} | {_format_number(entry['current'])} | {_format_number(entry['previous'])} | "
            f"{sign}{_format_number(change)} |"
        )

    sign_in = report.get("sign_in", {})
    failures = sign_in.get("failures_by_code") or {}
    if failures:
        lines += ["", "## Sign-in failures by code (lower bound)", ""]
        lines += [f"- {code}: {count}" for code, count in sorted(failures.items(), key=lambda item: -item[1])]

    lines += [
        "",
        "Retention and all-time figures are on `/admin/reports` (Signed-in retention card).",
        "",
        "## Checklist",
        "",
        *[f"- [ ] {item}" for item in CHECKLIST],
        "",
        "Fixed checks outside this cycle: share traffic (#137, around 2026-12-19) and the Hebrew UI decision "
        "(around 2026-12-25).",
    ]
    return "\n".join(lines)


def create_github_issue(repo: str, token: str, title: str, body: str) -> int:
    """Open an issue and return its number. Raises on any non-2xx answer."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=json.dumps({"title": title, "body": body}).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "verbboard-persona-review",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=GITHUB_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https host
        return int(json.loads(response.read().decode("utf-8"))["number"])


def run_review(
    *,
    today: date,
    repo: str,
    token: str,
    dry_run: bool = False,
    force: bool = False,
) -> dict[str, Any]:
    """Open the review issue if one is due. Idempotent per day; safe to call every week."""
    collection = get_db().collection(COLLECTION)
    # Only reviews that really opened an issue count; a marker left behind by a crash must not block 21 days.
    opened = [doc.id for doc in collection.stream() if (doc.to_dict() or {}).get("issue_number")]
    if not force and not is_due(opened, today):
        return {"status": "not_due"}

    date_from, date_to = review_window(today)
    body = build_issue_body(build_report(date_from.isoformat(), date_to.isoformat(), compare=True), today)
    title = build_issue_title(today)
    if dry_run:
        return {"status": "dry_run", "title": title, "body": body}

    marker = collection.document(today.isoformat())
    try:
        marker.create({"created_at": today.isoformat(), "issue_number": None})
    except AlreadyExists:
        return {"status": "already_opened_today"}
    try:
        issue_number = create_github_issue(repo, token, title, body)
    except urllib.error.HTTPError:
        marker.delete()  # GitHub definitely refused: nothing was created, so a retry is safe
        raise
    except Exception:
        # Timeout or lost response: the issue may exist. Keep the marker (it blocks a same-day duplicate and
        # does not count as a review, so the next weekly run tries again).
        logger.exception("PERSONA_REVIEW_GITHUB_UNCERTAIN")
        raise
    marker.update({"issue_number": issue_number})
    logger.info("PERSONA_REVIEW_OPENED issue=%s", issue_number)
    return {"status": "created", "issue_number": issue_number}
