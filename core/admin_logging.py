from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def log_missing_verb_search(
    *,
    language: str,
    query: str,
    page: str = "",
    source: str = "search",
    verb_id: str = "",
) -> None:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return

    now = datetime.now(UTC)
    record = {
        "created_at": now,
        "language": language,
        "query": normalized_query,
        "status": None,
        "page": page or "",
        "source": source or "",
        "verb_id": verb_id or "",
    }

    _write_firestore_signal(record)


def _write_firestore_signal(record: dict) -> None:
    from core.settings import load_settings
    from core.storage.firestore_db import get_db

    col = load_settings().verb_signals_collection
    if not col:
        return
    try:
        db = get_db()
        db.collection(col).document().set(record)
    except Exception:
        logger.exception("Failed to write verb signal to Firestore")
