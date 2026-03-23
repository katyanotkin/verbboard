from __future__ import annotations

import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger(__name__)


def log_missing_verb_search(language: str, query: str) -> None:
    normalized_query = query.strip().casefold()
    if not normalized_query:
        return

    record = {
        "ts": datetime.now(UTC).isoformat(),
        "language": language,
        "query": normalized_query,
    }

    _append_local(record)
    _write_gcs_event(record)


def _append_local(record: dict[str, str]) -> None:
    log_dir = Path("runtime/admin_logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    log_path = log_dir / "missing_verb_searches.jsonl"
    with log_path.open("a", encoding="utf-8") as output_file:
        output_file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _write_gcs_event(record: dict[str, str]) -> None:
    bucket_name = os.getenv("ADMIN_LOG_BUCKET")
    if not bucket_name:
        return

    try:
        from google.cloud import storage
    except Exception:
        logger.exception("google-cloud-storage is not available for admin logging")
        return

    try:
        client = storage.Client()
        bucket = client.bucket(bucket_name)

        timestamp = record["ts"].replace(":", "-")
        safe_language = quote(record["language"], safe="")
        safe_query = quote(record["query"], safe="")
        blob_name = (
            "admin/missing-verb-searches/"
            f"{timestamp}_{safe_language}_{safe_query}.json"
        )

        blob = bucket.blob(blob_name)
        blob.upload_from_string(
            json.dumps(record, ensure_ascii=False, indent=2),
            content_type="application/json",
        )
    except Exception:
        logger.exception("Failed to write missing verb search to GCS")
