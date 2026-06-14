from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from core.polls import ACTIVE_POLL_ID, POLL_OPTIONS, POLL_QUESTIONS
from core.storage.firestore_db import get_db


def _normalize_feedback_doc(doc: Any) -> dict[str, Any]:
    data = doc.to_dict() or {}
    created_at = data.get("created_at")

    return {
        "id": doc.id,
        "comment": str(data.get("comment") or ""),
        "poll_id": str(data.get("poll_id") or ""),
        "poll_question": str(data.get("poll_question") or ""),
        "poll_answer": str(data.get("poll_answer") or ""),
        "language": str(data.get("language") or ""),
        "page": str(data.get("page") or ""),
        "source": str(data.get("source") or ""),
        "verb_id": str(data.get("verb_id") or ""),
        "hidden": bool(data.get("hidden", False)),
        "created_at": created_at.isoformat() if created_at else "",
    }


def _filter_feedback_rows(
    feedback_rows: list[dict[str, Any]],
    *,
    visibility: str,
    page: str,
    language: str,
    source: str,
    query: str,
) -> list[dict[str, Any]]:
    filtered_rows = feedback_rows

    if visibility == "visible":
        filtered_rows = [feedback_row for feedback_row in filtered_rows if not feedback_row.get("hidden", False)]
    elif visibility == "hidden":
        filtered_rows = [feedback_row for feedback_row in filtered_rows if feedback_row.get("hidden", False)]
    elif visibility != "all":
        raise ValueError("Invalid visibility value")

    if page:
        filtered_rows = [feedback_row for feedback_row in filtered_rows if feedback_row.get("page", "") == page]

    if language:
        filtered_rows = [feedback_row for feedback_row in filtered_rows if feedback_row.get("language", "") == language]

    if source:
        filtered_rows = [feedback_row for feedback_row in filtered_rows if feedback_row.get("source", "") == source]

    if query:
        normalized_query = query.casefold()
        filtered_rows = [
            feedback_row
            for feedback_row in filtered_rows
            if normalized_query in feedback_row.get("comment", "").casefold()
        ]

    return filtered_rows


def list_feedback_rows(
    *,
    sort: str,
    visibility: str,
    page: str,
    language: str,
    source: str,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    db = get_db()

    direction = "DESCENDING" if sort != "oldest" else "ASCENDING"
    docs = db.collection("feedback").order_by("created_at", direction=direction).limit(limit).stream()

    feedback_rows = [_normalize_feedback_doc(doc) for doc in docs]
    return _filter_feedback_rows(
        feedback_rows,
        visibility=visibility,
        page=page,
        language=language,
        source=source,
        query=query,
    )


def list_feedback_facets(*, limit: int = 1000) -> dict[str, list[str]]:
    db = get_db()
    docs = db.collection("feedback").order_by("created_at", direction="DESCENDING").limit(limit).stream()
    feedback_rows = [_normalize_feedback_doc(doc) for doc in docs]

    return {
        "pages": sorted({feedback_row["page"] for feedback_row in feedback_rows if feedback_row.get("page")}),
        "languages": sorted(
            {feedback_row["language"] for feedback_row in feedback_rows if feedback_row.get("language")}
        ),
        "sources": sorted({feedback_row["source"] for feedback_row in feedback_rows if feedback_row.get("source")}),
    }


def hide_feedback_by_id(doc_id: str) -> bool:
    db = get_db()
    ref = db.collection("feedback").document(doc_id)
    snapshot = ref.get()

    if not snapshot.exists:
        return False

    ref.update({"hidden": True})
    return True


def unhide_feedback_by_id(doc_id: str) -> bool:
    db = get_db()
    ref = db.collection("feedback").document(doc_id)
    snapshot = ref.get()

    if not snapshot.exists:
        return False

    ref.update({"hidden": False})
    return True


def get_active_poll_meta() -> dict:
    if not ACTIVE_POLL_ID:
        return {}

    options = [
        {"value": value, "label": labels.get("en") or value} for value, labels in POLL_OPTIONS.get(ACTIVE_POLL_ID, [])
    ]
    return {
        "poll_id": ACTIVE_POLL_ID,
        "question_en": POLL_QUESTIONS.get(ACTIVE_POLL_ID, {}).get("en", ""),
        "options": options,
    }


def _read_sessions_summary(*, days: int = 60) -> dict[str, Any]:
    db = get_db()
    cutoff_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    docs = db.collection("analytics_sessions").where("date", ">=", cutoff_date).stream()

    by_device: Counter[str] = Counter()
    by_language: Counter[str] = Counter()
    by_ui_lang: Counter[str] = Counter()
    total = 0
    logged_in = 0

    for doc in docs:
        data = doc.to_dict() or {}
        by_device[str(data.get("device_type") or "unknown").lower()] += 1
        by_language[str(data.get("language") or "none")] += 1
        by_ui_lang[str(data.get("ui_lang") or "none")] += 1
        total += 1
        if data.get("uid"):
            logged_in += 1

    return {
        "total_sessions": total,
        "logged_in_sessions": logged_in,
        "by_device": dict(by_device),
        "by_language": dict(by_language),
        "by_ui_lang": dict(by_ui_lang),
    }


def _read_practice_summary() -> dict[str, Any]:
    db = get_db()
    docs = db.collection_group("languages").stream()

    by_language: Counter[str] = Counter()
    users_with_practice: set[str] = set()

    for doc in docs:
        parts = doc.reference.path.split("/")
        if len(parts) != 4 or parts[0] != "user_practice":
            continue
        data = doc.to_dict() or {}
        if not data.get("badges"):
            continue
        uid = parts[1]
        lang = str(data.get("language") or parts[3])
        by_language[lang] += 1
        users_with_practice.add(uid)

    return {
        "practice_users_total": len(users_with_practice),
        "practice_by_language": dict(by_language),
    }


def _read_users_summary(*, days: int = 60) -> dict[str, Any]:
    db = get_db()
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    cutoff_7 = now - timedelta(days=7)

    docs = list(db.collection("users").stream())
    total = len(docs)
    new_users = 0
    active_60 = 0
    active_7 = 0

    for doc in docs:
        data = doc.to_dict() or {}
        created_at = data.get("created_at")
        updated_at = data.get("updated_at")
        if created_at and created_at >= cutoff:
            new_users += 1
        if updated_at and updated_at >= cutoff:
            active_60 += 1
        if updated_at and updated_at >= cutoff_7:
            active_7 += 1

    return {
        "total": total,
        "new_last_60d": new_users,
        "active_last_7d": active_7,
        "active_last_60d": active_60,
    }


def get_device_mix(*, days: int = 60) -> dict[str, Any]:
    sessions = _read_sessions_summary(days=days)
    users = _read_users_summary(days=days)
    practice = _read_practice_summary()

    return {
        "days": days,
        "total_sessions": sessions["total_sessions"],
        "logged_in_sessions": sessions["logged_in_sessions"],
        "by_device": sessions["by_device"],
        "by_language": sessions["by_language"],
        "by_ui_lang": sessions["by_ui_lang"],
        "users": users,
        "practice": practice,
    }
