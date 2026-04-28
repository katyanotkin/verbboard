from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
import json

from core.analytics.client_context import detect_device_type

logger = logging.getLogger(__name__)


def log_missing_verb_search(
    *,
    language: str,
    query: str,
    page: str = "",
    source: str = "search",
    verb_id: str = "",
    user_agent: str = "",
    device_type: str = "unknown",
    viewport_width: int | None = None,
) -> None:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return

    resolved_device_type = device_type
    if resolved_device_type == "unknown":
        resolved_device_type = detect_device_type(user_agent)

    now = datetime.now(UTC)
    record = {
        "created_at": now,
        "language": language,
        "query": normalized_query,
        "status": None,
        # metadata
        "page": page or "",
        "source": source or "",
        "verb_id": verb_id or "",
        "user_agent": user_agent or "",
        "device_type": resolved_device_type,
        "viewport_width": viewport_width,
    }

    _append_local(record)
    _write_firestore_signal(record)


def _append_local(record: dict) -> None:
    log_dir = Path("runtime/admin_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "missing_verb_searches.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        json_safe = {
            **record,
            "created_at": record["created_at"].isoformat()
            if hasattr(record.get("created_at"), "isoformat")
            else record.get("created_at"),
        }
        f.write(json.dumps(json_safe, ensure_ascii=False) + "\n")


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
