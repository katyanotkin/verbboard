from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import storage

from core.supported_languages import SUPPORTED_LANGUAGES


def parse_event_timestamp(timestamp_text: str) -> datetime | None:
    try:
        return datetime.fromisoformat(timestamp_text)
    except ValueError:
        return None


def list_blob_names(
    *,
    client: storage.Client,
    bucket_name: str,
    prefix: str,
) -> list[str]:
    blobs = client.list_blobs(bucket_name, prefix=prefix)
    return [blob.name for blob in blobs if not blob.name.endswith("/")]


def read_event(
    *,
    client: storage.Client,
    bucket_name: str,
    blob_name: str,
) -> dict[str, Any] | None:
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    try:
        payload_text = blob.download_as_text(encoding="utf-8")
        payload = json.loads(payload_text)
    except Exception:
        return None

    if not isinstance(payload, dict):
        return None

    language = payload.get("language")
    query = payload.get("query")
    timestamp_text = payload.get("ts")

    if not isinstance(language, str) or language not in SUPPORTED_LANGUAGES:
        return None
    if not isinstance(query, str):
        return None

    query = query.strip()
    if not query:
        return None

    if not isinstance(timestamp_text, str):
        return None

    event_timestamp = parse_event_timestamp(timestamp_text)
    if event_timestamp is None:
        return None

    return {
        "ts": timestamp_text,
        "language": language,
        "query": query,
        "blob_name": blob_name,
    }


def load_recent_events(
    *,
    bucket_name: str,
    prefix: str,
    days: int,
) -> list[dict[str, Any]]:
    client = storage.Client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    events: list[dict[str, Any]] = []
    for blob_name in list_blob_names(
        client=client,
        bucket_name=bucket_name,
        prefix=prefix,
    ):
        event = read_event(
            client=client,
            bucket_name=bucket_name,
            blob_name=blob_name,
        )
        if event is None:
            continue

        event_timestamp = parse_event_timestamp(event["ts"])
        if event_timestamp is None:
            continue

        if event_timestamp >= cutoff:
            events.append(event)

    events.sort(key=lambda event: event["ts"])
    return events
