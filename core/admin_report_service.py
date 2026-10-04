"""Admin Report: how Google Play closed testing is going (issue #67).

Counts are *sessions* (one analytics_sessions doc per IP+UA+day), not people:
no cross-day visitor identity exists, so the same tester on three days is three
sessions. Percentages use non-bot sessions as the denominator.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any

from core.admin_feedback_service import _ENGAGEMENT_FLAGS, _excluded_uids
from core.storage.firestore_db import get_db

MAX_RANGE_DAYS = 366

# The `twa` session flag is only written for sessions created on/after this
# date; earlier sessions are covered by the legacy approximation below.
TWA_TRACKING_SINCE = "2026-10-03"

_REPORT_FLAGS = ("verb_viewed",) + tuple(
    f for f in _ENGAGEMENT_FLAGS if f.startswith("practice_") and f != "practice_gate_shown"
)
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ANDROID_APP_REFERRER = "android-app://"


def _parse_date(value: str, label: str) -> date:
    if not isinstance(value, str) or not _DATE_RE.match(value):
        raise ValueError(f"{label} must be YYYY-MM-DD")
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{label} is not a valid date") from exc


def _pct(part: int, whole: int) -> float:
    return round(100.0 * part / whole, 1) if whole else 0.0


def _is_legacy_twa(data: dict[str, Any]) -> bool:
    """Pre-`twa`-field session that still looks like a Play app launch."""
    if "twa" in data:
        return False
    referrer = str(data.get("referrer") or "").lower()
    return referrer.startswith(_ANDROID_APP_REFERRER) or data.get("sign_in_tapped_branch") == "twa"


def _read_window(start: date, end: date, excluded_uids: set[str]) -> dict[str, Any]:
    db = get_db()
    docs = (
        db.collection("analytics_sessions")
        .where("date", ">=", start.isoformat())
        .where("date", "<=", end.isoformat())
        .stream()
    )

    non_bot = bot = with_uid = twa = legacy_twa = 0
    users: set[str] = set()
    twa_users: set[str] = set()
    flags: Counter[str] = Counter()
    by_device: Counter[str] = Counter()
    daily: dict[str, dict[str, int]] = {}
    day = start
    while day <= end:
        daily[day.isoformat()] = {"sessions": 0, "registered": 0, "twa": 0}
        day += timedelta(days=1)

    for doc in docs:
        data = doc.to_dict() or {}
        uid = data.get("uid")
        if uid and uid in excluded_uids:
            continue
        device_type = str(data.get("device_type") or "unknown").lower()
        if device_type == "bot":
            bot += 1
            continue
        non_bot += 1
        by_device[device_type] += 1
        row = daily.get(str(data.get("date") or ""))
        if row is not None:
            row["sessions"] += 1
        if uid:
            with_uid += 1
            users.add(uid)
            if row is not None:
                row["registered"] += 1
        is_twa = bool(data.get("twa"))
        if is_twa:
            twa += 1
            if uid:
                twa_users.add(uid)
            if row is not None:
                row["twa"] += 1
        elif _is_legacy_twa(data):
            legacy_twa += 1
        for flag in _REPORT_FLAGS:
            if data.get(flag):
                flags[flag] += 1

    new_registrations = 0
    range_start = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    range_end = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
    user_docs = (
        db.collection("users").where("created_at", ">=", range_start).where("created_at", "<=", range_end).stream()
    )
    for user_doc in user_docs:
        if user_doc.id not in excluded_uids:
            new_registrations += 1

    return {
        "range": {"date_from": start.isoformat(), "date_to": end.isoformat(), "days": (end - start).days + 1},
        "non_bot_sessions": non_bot,
        "bot_sessions": bot,
        "registered": {
            "sessions_with_uid": with_uid,
            "pct": _pct(with_uid, non_bot),
            "distinct_users": len(users),
            "new_registrations": new_registrations,
        },
        "twa": {
            "sessions": twa,
            "pct": _pct(twa, non_bot),
            "signed_in_users": len(twa_users),
            "legacy_approximate_sessions": legacy_twa,
            "tracking_since": TWA_TRACKING_SINCE,
            "note": (
                f"The twa flag is only recorded for sessions created from {TWA_TRACKING_SINCE}. "
                "Earlier Play-app sessions are counted separately as legacy approximations "
                "(android-app:// referrer or a TWA sign-in tap)."
            ),
        },
        "engagement": {flag: flags[flag] for flag in _REPORT_FLAGS},
        "daily": [{"date": day_key, **counts} for day_key, counts in daily.items()],
        "by_device": dict(by_device),
    }


def _flat_metrics(report: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {
        "non_bot_sessions": report["non_bot_sessions"],
        "bot_sessions": report["bot_sessions"],
    }
    for key, value in report["registered"].items():
        metrics[f"registered.{key}"] = value
    for key in ("sessions", "pct", "signed_in_users", "legacy_approximate_sessions"):
        metrics[f"twa.{key}"] = report["twa"][key]
    for key, value in report["engagement"].items():
        metrics[f"engagement.{key}"] = value
    return metrics


def build_report(date_from: str, date_to: str, compare: bool = False) -> dict[str, Any]:
    start = _parse_date(date_from, "date_from")
    end = _parse_date(date_to, "date_to")
    if start > end:
        raise ValueError("date_from must be on or before date_to")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise ValueError(f"range is limited to {MAX_RANGE_DAYS} days")

    excluded_uids = _excluded_uids()
    report = _read_window(start, end, excluded_uids)

    if compare:
        length = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=length - 1)
        previous = _read_window(previous_start, previous_end, excluded_uids)
        current_metrics = _flat_metrics(report)
        previous_metrics = _flat_metrics(previous)
        report["previous"] = previous
        report["deltas"] = {
            key: {
                "current": current_metrics[key],
                "previous": previous_metrics[key],
                "delta": round(current_metrics[key] - previous_metrics[key], 1),
            }
            for key in current_metrics
        }
    return report
