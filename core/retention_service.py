"""Signed-in retention cohorts from analytics_sessions (issue #112).

Sessions are keyed (IP, UA, day), so only sessions that carry a `uid` give a cross-day
identity. A user's cohort day is their first date with a uid-bearing session. Numbers are a
lower bound: a return visit whose session never got a uid attached is not counted. Always
read the percentages together with `n`; cohorts here are tiny.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

from core.storage.firestore_db import get_db

EXACT_DAYS = (1, 7, 30)
# (label, first day offset, last day offset): "came back at least once in that window".
ROLLING_WINDOWS = (("d1_7", 1, 7), ("d8_30", 8, 30))


def _pct(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 1) if whole else None


def _week_label(day: date) -> str:
    monday = day - timedelta(days=day.weekday())
    return monday.isoformat()


def compute_retention(rows: Iterable[tuple[str, str]], today: date) -> dict[str, Any]:
    """rows: (uid, 'YYYY-MM-DD') per uid-bearing, non-bot session. Pure, no I/O."""
    days_by_uid: dict[str, set[date]] = defaultdict(set)
    for uid, day_text in rows:
        if not uid or not day_text:
            continue
        try:
            parsed_day = date.fromisoformat(day_text)
        except ValueError:
            continue
        days_by_uid[uid].add(parsed_day)

    def empty_bucket() -> dict[str, int]:
        bucket = {"users": 0}
        for offset in EXACT_DAYS:
            bucket[f"mature_d{offset}"] = 0
            bucket[f"returned_d{offset}"] = 0
        for label, _, last in ROLLING_WINDOWS:
            bucket[f"mature_{label}"] = 0
            bucket[f"returned_{label}"] = 0
        return bucket

    overall = empty_bucket()
    weekly: dict[str, dict[str, int]] = defaultdict(empty_bucket)

    for visit_days in days_by_uid.values():
        first = min(visit_days)
        for bucket in (overall, weekly[_week_label(first)]):
            bucket["users"] += 1
            for offset in EXACT_DAYS:
                if first + timedelta(days=offset) <= today:
                    bucket[f"mature_d{offset}"] += 1
                    if first + timedelta(days=offset) in visit_days:
                        bucket[f"returned_d{offset}"] += 1
            for label, start, last in ROLLING_WINDOWS:
                if first + timedelta(days=last) <= today:
                    bucket[f"mature_{label}"] += 1
                    if any(first + timedelta(days=step) in visit_days for step in range(start, last + 1)):
                        bucket[f"returned_{label}"] += 1

    return {
        "as_of": today.isoformat(),
        "overall": _summarise(overall),
        "weekly": [{"cohort_week": week, **_summarise(weekly[week])} for week in sorted(weekly)],
        "caveat": (
            "Lower bound: counts only sessions with a uid attached; first date = first uid-bearing "
            "session in the data (with --since, users active earlier look new). Read percentages together with n."
        ),
    }


def _summarise(bucket: dict[str, int]) -> dict[str, Any]:
    summary: dict[str, Any] = {"users": bucket["users"]}
    for offset in EXACT_DAYS:
        key = f"d{offset}"
        summary[key] = {
            "n": bucket[f"mature_{key}"],
            "returned": bucket[f"returned_{key}"],
            "pct": _pct(bucket[f"returned_{key}"], bucket[f"mature_{key}"]),
        }
    for label, _, _ in ROLLING_WINDOWS:
        summary[label] = {
            "n": bucket[f"mature_{label}"],
            "returned": bucket[f"returned_{label}"],
            "pct": _pct(bucket[f"returned_{label}"], bucket[f"mature_{label}"]),
        }
    return summary


def read_uid_session_rows(since: date | None, excluded_uids: set[str]) -> list[tuple[str, str]]:
    """Read-only scan of analytics_sessions: (uid, date) for non-bot sessions that have a uid."""
    collection = get_db().collection("analytics_sessions")
    query: Any = collection.where("date", ">=", since.isoformat()) if since is not None else collection
    rows: list[tuple[str, str]] = []
    for doc in query.stream():
        data = doc.to_dict() or {}
        uid = data.get("uid")
        if not uid or uid in excluded_uids:
            continue
        if str(data.get("device_type") or "").lower() == "bot":
            continue
        rows.append((str(uid), str(data.get("date") or "")))
    return rows


def build_retention_report(since: date | None, today: date) -> dict[str, Any]:
    from core.admin_feedback_service import _excluded_uids

    return compute_retention(read_uid_session_rows(since, _excluded_uids()), today)


def format_text(report: dict[str, Any]) -> str:
    def cell(entry: dict[str, Any]) -> str:
        pct = entry["pct"]
        return "  -  " if pct is None else f"{pct:5.1f}% ({entry['returned']}/{entry['n']})"

    header = f"{'cohort week':<12} {'users':>5}  {'day 1':<16} {'day 7':<16} {'day 30':<16} {'1-7':<16} {'8-30':<16}"
    lines = [f"Signed-in retention as of {report['as_of']}", header]
    for label, block in [("ALL", report["overall"])] + [(w["cohort_week"], w) for w in report["weekly"]]:
        lines.append(
            f"{label:<12} {block['users']:>5}  {cell(block['d1']):<16} {cell(block['d7']):<16} "
            f"{cell(block['d30']):<16} {cell(block['d1_7']):<16} {cell(block['d8_30']):<16}"
        )
    lines.append(report["caveat"])
    return "\n".join(lines)
