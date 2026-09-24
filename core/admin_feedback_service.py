from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from core.polls import ACTIVE_POLL_ID, POLL_OPTIONS, POLL_QUESTIONS
from core.settings import load_settings, verb_candidates_collection_name
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
        "contact_email": str(data.get("contact_email") or ""),
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


def _excluded_uids() -> set[str]:
    """Firebase UIDs for own/test emails (ANALYTICS_EXCLUDED_EMAILS secret) to drop from counts."""
    excluded_emails = load_settings().analytics_excluded_emails
    if not excluded_emails:
        return set()

    db = get_db()
    docs = db.collection("users").where("email", "in", list(excluded_emails)).stream()
    return {doc.id for doc in docs}


# Set-once boolean flags on analytics_sessions. home_viewed only exists on
# sessions created on/after 2026-09-24, so votd_clicked / home_viewed is only
# meaningful for that window.
_ENGAGEMENT_FLAGS = ("home_viewed", "votd_clicked", "practice_started", "practice_completed")

_TOP_SEARCH_HITS = 10


def _read_search_hits_summary() -> dict[str, Any]:
    """Searches that resolved to an existing verb (verb_search_hits), with the
    verbs generated on the spot by autogen split out: promoted verb_candidates
    docs with source == "autogen" share the live verb's doc id (autogen also
    writes rejected/needs_review docs, which never became live verbs)."""
    db = get_db()
    autogen_docs = (
        db.collection(verb_candidates_collection_name())
        .where("source", "==", "autogen")
        .where("status", "==", "promoted")
        .stream()
    )
    autogen_ids = {doc.id for doc in autogen_docs}

    rows: list[dict[str, Any]] = []
    for doc in db.collection("verb_search_hits").stream():
        data = doc.to_dict() or {}
        verb_id = str(data.get("verb_id") or "")
        rows.append({"verb_id": verb_id, "hits": int(data.get("hits") or 0), "autogen": verb_id in autogen_ids})

    autogen_rows = [row for row in rows if row["autogen"]]
    return {
        "autogen_verbs_total": len(autogen_ids),
        "autogen_verbs_searched_again": len(autogen_rows),
        "autogen_hits_total": sum(row["hits"] for row in autogen_rows),
        "top": sorted(rows, key=lambda row: row["hits"], reverse=True)[:_TOP_SEARCH_HITS],
    }


def _read_sessions_summary(*, days: int = 60, excluded_uids: set[str] | None = None) -> dict[str, Any]:
    excluded_uids = excluded_uids or set()
    db = get_db()
    cutoff_date = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    docs = db.collection("analytics_sessions").where("date", ">=", cutoff_date).stream()

    by_device: Counter[str] = Counter()
    by_language: Counter[str] = Counter()
    by_ui_lang: Counter[str] = Counter()
    total = 0
    bot_sessions = 0
    logged_in = 0
    verb_viewed = 0
    flag_counts: Counter[str] = Counter()

    for doc in docs:
        data = doc.to_dict() or {}
        if data.get("uid") in excluded_uids:
            continue
        device_type = str(data.get("device_type") or "unknown").lower()
        if device_type == "bot":
            # Self-identified crawlers/scanners: counted apart, kept out of
            # every other figure. Sessions before 2026-09-24 are unclassified.
            bot_sessions += 1
            continue
        by_device[device_type] += 1
        by_language[str(data.get("language") or "none")] += 1
        by_ui_lang[str(data.get("ui_lang") or "none")] += 1
        total += 1
        if data.get("uid"):
            logged_in += 1
        if data.get("verb_viewed"):
            verb_viewed += 1
        for flag in _ENGAGEMENT_FLAGS:
            if data.get(flag):
                flag_counts[flag] += 1

    return {
        "total_sessions": total,
        "bot_sessions": bot_sessions,
        "logged_in_sessions": logged_in,
        "verb_viewed_sessions": verb_viewed,
        "engagement": {flag: flag_counts[flag] for flag in _ENGAGEMENT_FLAGS},
        "by_device": dict(by_device),
        "by_language": dict(by_language),
        "by_ui_lang": dict(by_ui_lang),
    }


def _read_practice_summary(*, excluded_uids: set[str] | None = None) -> dict[str, Any]:
    excluded_uids = excluded_uids or set()
    db = get_db()
    docs = db.collection_group("languages").stream()

    by_language: Counter[str] = Counter()
    users_with_practice: set[str] = set()

    for doc in docs:
        parts = doc.reference.path.split("/")
        if len(parts) != 4 or parts[0] != "user_practice":
            continue
        uid = parts[1]
        if uid in excluded_uids:
            continue
        data = doc.to_dict() or {}
        if not data.get("badges"):
            continue
        lang = str(data.get("language") or parts[3])
        by_language[lang] += 1
        users_with_practice.add(uid)

    return {
        "practice_users_total": len(users_with_practice),
        "practice_by_language": dict(by_language),
    }


def _read_users_summary(*, days: int = 60, excluded_uids: set[str] | None = None) -> dict[str, Any]:
    excluded_uids = excluded_uids or set()
    db = get_db()
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    cutoff_7 = now - timedelta(days=7)

    docs = [doc for doc in db.collection("users").stream() if doc.id not in excluded_uids]
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
    excluded_uids = _excluded_uids()
    sessions = _read_sessions_summary(days=days, excluded_uids=excluded_uids)
    users = _read_users_summary(days=days, excluded_uids=excluded_uids)
    practice = _read_practice_summary(excluded_uids=excluded_uids)

    return {
        "days": days,
        "total_sessions": sessions["total_sessions"],
        "bot_sessions": sessions["bot_sessions"],
        "logged_in_sessions": sessions["logged_in_sessions"],
        "verb_viewed_sessions": sessions["verb_viewed_sessions"],
        "engagement": sessions["engagement"],
        "search_hits": _read_search_hits_summary(),
        "by_device": sessions["by_device"],
        "by_language": sessions["by_language"],
        "by_ui_lang": sessions["by_ui_lang"],
        "users": users,
        "practice": practice,
    }
