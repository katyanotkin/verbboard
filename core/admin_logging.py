from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


def log_missing_verb_search(language: str, query: str) -> None:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return
    record = {
        "ts": datetime.now(UTC).isoformat(),
        "language": language,
        "query": normalized_query,
        "status": None,
    }
    _append_local(record)
    _write_firestore_signal(record)


def _append_local(record: dict) -> None:
    log_dir = Path("runtime/admin_logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "missing_verb_searches.jsonl"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


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
