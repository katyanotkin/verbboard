from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import Request

from core.analytics.client_context import detect_device_type
from core.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

USAGE_EVENTS_COLLECTION = "usage_event"

USAGE_EVENT_PAGE_VIEW = "page_view"
USAGE_EVENT_SEARCH_HIT = "search_hit"
USAGE_EVENT_SEARCH_MISS = "search_miss"
USAGE_EVENT_FEEDBACK_SUBMIT = "feedback_submit"
USAGE_EVENT_LEARN_VIEW = "learn_view"
USAGE_EVENT_VERB_BROWSER_VIEW = "verb_browser_view"
USAGE_EVENT_CANDIDATE_PREVIEW_VIEW = "candidate_preview_view"
USAGE_EVENT_OTHER = "other"

VALID_USAGE_EVENT_TYPES = {
    USAGE_EVENT_PAGE_VIEW,
    USAGE_EVENT_SEARCH_HIT,
    USAGE_EVENT_SEARCH_MISS,
    USAGE_EVENT_FEEDBACK_SUBMIT,
    USAGE_EVENT_LEARN_VIEW,
    USAGE_EVENT_VERB_BROWSER_VIEW,
    USAGE_EVENT_CANDIDATE_PREVIEW_VIEW,
    USAGE_EVENT_OTHER,
}


def log_usage_event(
    *,
    request: Request,
    event_type: str,
    page: str,
    language: str = "",
    verb_id: str = "",
    query: str = "",
    source: str = "product",
) -> None:
    user_agent = request.headers.get("user-agent", "")
    resolved_event_type = (
        event_type if event_type in VALID_USAGE_EVENT_TYPES else USAGE_EVENT_OTHER
    )

    payload: dict[str, Any] = {
        "created_at": datetime.now(UTC),
        "event_type": resolved_event_type,
        "event_name": event_type,
        "page": page or "",
        "language": language or "",
        "verb_id": verb_id or "",
        "query": query.strip().casefold() if query else "",
        "source": source or "product",
        "path": request.url.path,
        "user_agent": user_agent,
        "device_type": detect_device_type(user_agent),
    }

    try:
        db = get_db()
        db.collection(USAGE_EVENTS_COLLECTION).document().set(payload)
    except Exception:
        logger.exception("Failed to write usage event")
