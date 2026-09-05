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


def resolve_signal_label(*, language: str, query: str) -> None:
    """Hide the demand-signal label for a query once its verb is live.

    Labels are only created when an admin classifies a signal group as
    "candidate" (`classify_signal_group` in `app/routes/admin_signals.py`);
    nothing downstream (manual generate+promote, or the instant autogen
    write path) ever updates that label, so it stays "candidate" forever
    even after the verb goes live. Best-effort: never raises, and is a
    no-op if no label exists for this query (e.g. the instant autogen path
    never went through classification).
    """
    normalized_query = query.strip().casefold()
    if not language or not normalized_query:
        return

    from core.settings import load_settings
    from core.storage.firestore_db import get_db

    lbl_col = load_settings().verb_signal_labels_collection
    if not lbl_col:
        return
    try:
        db = get_db()
        ref = db.collection(lbl_col).document(f"{language}_{normalized_query}")
        if ref.get().exists:
            ref.update({"hidden": True, "updated_at": datetime.now(UTC).isoformat()})
    except Exception:
        logger.exception("Failed to resolve demand-signal label for %s/%s", language, normalized_query)


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
