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


def _count_device_types_feedback(*, days: int = 60, limit: int = 2000) -> dict[str, int]:
    db = get_db()
    cutoff = datetime.now(UTC) - timedelta(days=days)
    docs = (
        db.collection("feedback")
        .where("created_at", ">=", cutoff)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
        .stream()
    )
    counter: Counter[str] = Counter()
    for doc in docs:
        data = doc.to_dict() or {}
        device_type = str(data.get("device_type") or "unknown").lower()
        counter[device_type] += 1
    return dict(counter)


def _read_analytics_counters(*, days: int = 60) -> dict[str, Any]:
    db = get_db()
    cutoff_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    docs = db.collection("analytics_daily").where("date", ">=", cutoff_date).stream()

    by_page: Counter[str] = Counter()
    by_device: Counter[str] = Counter()
    by_language: Counter[str] = Counter()
    by_ui_lang: Counter[str] = Counter()

    for doc in docs:
        data = doc.to_dict() or {}
        n = int(data.get("count") or 0)
        by_page[str(data.get("page") or "unknown")] += n
        by_device[str(data.get("device_type") or "unknown").lower()] += n
        lang = str(data.get("language") or "none")
        by_language[lang] += n
        ui = str(data.get("ui_lang") or "none")
        by_ui_lang[ui] += n

    return {
        "by_page": dict(by_page),
        "by_device": dict(by_device),
        "by_language": dict(by_language),
        "by_ui_lang": dict(by_ui_lang),
    }


def get_device_mix(*, days: int = 60) -> dict[str, Any]:
    feedback_counts = _count_device_types_feedback(days=days)
    analytics = _read_analytics_counters(days=days)

    combined = Counter(feedback_counts)
    combined.update(analytics["by_device"])

    return {
        "days": days,
        "feedback": feedback_counts,
        "page_views": analytics["by_device"],
        "by_page": analytics["by_page"],
        "by_device": analytics["by_device"],
        "by_language": analytics["by_language"],
        "by_ui_lang": analytics["by_ui_lang"],
        "combined": dict(combined),
    }
