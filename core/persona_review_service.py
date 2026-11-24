"""Scheduled persona review (issue #142).

Cloud Scheduler calls `POST /internal/persona-review` weekly. A cron expression cannot say "every 21
days", so this module decides whether a review is due from the dated docs it leaves in
`persona_reviews/{YYYY-MM-DD}`. When due it snapshots the last 21 days from the Reports figures into
that doc (status "open", with the figures and the checklist from `.claude/skills/persona-review/SKILL.md`),
logs one `PERSONA_REVIEW_DUE` line (a Cloud Monitoring log alert emails the owner from it) and the admin
pages show a banner until `mark_done()` runs. With GITHUB_ISSUES_TOKEN and PERSONA_REVIEW_REPO set it also
opens a GitHub issue; without them nothing else changes. It never edits
`docs/marketing/personas.md`: the review itself stays a human or agent decision.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from datetime import UTC, date, datetime, timedelta
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
STATUS_OPEN = "open"
STATUS_DONE = "done"

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
        f"Opened automatically by Google Cloud Scheduler (#142). Window: {window['date_from']} to "
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


def summary_line(report: dict[str, Any], today: date) -> str:
    """One short log line (it goes into the alert email): the figures a reader checks first."""
    deltas = report.get("deltas", {})

    def current(key: str) -> str:
        entry = deltas.get(key)
        return _format_number(entry["current"]) if entry else "?"

    return (
        f"date={today.isoformat()} window={report['range']['date_from']}..{report['range']['date_to']} "
        f"sessions={current('non_bot_sessions')} practice_started={current('engagement.practice_started')} "
        f"share_landed={current('engagement.share_landed')} sign_in_failed={current('sign_in.failed_sessions')}"
    )


def create_github_issue(repo: str, token: str, title: str, body: str) -> int:
    """Open an issue and return its number. Raises on any failure."""
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


def _open_github_issue_if_configured(doc_ref: Any, title: str, body: str) -> None:
    """Optional extra when GITHUB_ISSUES_TOKEN and PERSONA_REVIEW_REPO are set.

    Never raises: the Firestore doc, the log line (email alert) and the banner already exist by now."""
    token = os.getenv("GITHUB_ISSUES_TOKEN", "")
    repo = os.getenv("PERSONA_REVIEW_REPO", "")
    if not (token and repo):
        return
    try:
        doc_ref.update({"issue_number": create_github_issue(repo, token, title, body)})
    except Exception:
        logger.exception("PERSONA_REVIEW_GITHUB_FAILED")


def run_review(*, today: date, dry_run: bool = False, force: bool = False) -> dict[str, Any]:
    """Record a review as due if one is. Idempotent per day; safe to call every week."""
    collection = get_db().collection(COLLECTION)
    if not force and not is_due([doc.id for doc in collection.stream()], today):
        return {"status": "not_due"}

    date_from, date_to = review_window(today)
    report = build_report(date_from.isoformat(), date_to.isoformat(), compare=True)
    body = build_issue_body(report, today)
    title = build_issue_title(today)
    if dry_run:
        return {"status": "dry_run", "title": title, "body": body}

    doc_ref = collection.document(today.isoformat())
    try:
        doc_ref.create(
            {
                "date": today.isoformat(),
                "status": STATUS_OPEN,
                "window": {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()},
                "title": title,
                "body": body,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
    except AlreadyExists:
        return {"status": "already_opened_today"}
    logger.warning("PERSONA_REVIEW_DUE %s", summary_line(report, today))
    _open_github_issue_if_configured(doc_ref, title, body)
    return {"status": "created", "date": today.isoformat()}


def open_review() -> dict[str, str] | None:
    """The newest review still waiting to be done, for the admin banner. Never raises."""
    try:
        open_docs = [
            (doc.id, doc.to_dict() or {})
            for doc in get_db().collection(COLLECTION).where("status", "==", STATUS_OPEN).stream()
        ]
        if not open_docs:
            return None
        doc_id, data = max(open_docs, key=lambda item: item[0])
        window = data.get("window") or {}
        return {
            "date": doc_id,
            "date_from": str(window.get("date_from", "")),
            "date_to": str(window.get("date_to", "")),
        }
    except Exception:
        logger.exception("persona review banner lookup failed")
        return None


def get_open_review_detail() -> dict[str, Any] | None:
    """The newest open review with its stored figures body, for the Personas page."""
    review = open_review()
    if review is None:
        return None
    data = get_db().collection(COLLECTION).document(review["date"]).get().to_dict() or {}
    return {
        "date": review["date"],
        "window": {"date_from": review["date_from"], "date_to": review["date_to"]},
        "body": str(data.get("body", "")),
    }


def list_reviews() -> list[dict[str, Any]]:
    """All reviews, newest first, without the figures body."""
    rows = []
    for doc in get_db().collection(COLLECTION).stream():
        data = doc.to_dict() or {}
        rows.append(
            {
                "date": doc.id,
                "status": data.get("status", ""),
                "window": data.get("window") or {},
                "issue_number": data.get("issue_number"),
                "created_at": data.get("created_at", ""),
                "done_at": data.get("done_at", ""),
            }
        )
    return sorted(rows, key=lambda row: row["date"], reverse=True)


def mark_done(review_date: str) -> bool:
    """Close one review (called by tools/persona_review_done.py). False when it does not exist."""
    ref = get_db().collection(COLLECTION).document(review_date)
    snapshot = ref.get()
    if not snapshot.exists:
        return False
    if (snapshot.to_dict() or {}).get("status") == STATUS_DONE:
        return True  # a second press or a stale tab must not overwrite done_at
    ref.update({"status": STATUS_DONE, "done_at": datetime.now(UTC).isoformat()})
    return True


def banner_text() -> str | None:
    """Admin banner while a review is waiting; never raises."""
    review = open_review()
    if review is None:
        return None
    return (
        f"Persona review due ({review['date_from']} to {review['date_to']}, opened {review['date']}). "
        "Open Personas to see the figures, then press Mark done."
    )
