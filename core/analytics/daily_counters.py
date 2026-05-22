from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from google.cloud import firestore

from core.analytics.client_context import detect_device_type

logger = logging.getLogger(__name__)

COLLECTION = "analytics_daily"

_PAGE_NAMES = {
    "/": "home",
    "/verbs": "verbs",
    "/learn": "learn",
    "/feedback": "feedback",
}

_pending: set[asyncio.Task] = set()


def _write(date: str, page: str, language: str, ui_lang: str, device_type: str) -> None:
    from core.storage.firestore_db import get_db

    lang_key = language or "none"
    ui_key = ui_lang or "none"
    doc_id = f"{date}_{page}_{device_type}_{lang_key}_{ui_key}"
    try:
        get_db().collection(COLLECTION).document(doc_id).set(
            {
                "count": firestore.Increment(1),
                "date": date,
                "page": page,
                "device_type": device_type,
                "language": language,
                "ui_lang": ui_lang,
            },
            merge=True,
        )
    except Exception:
        logger.exception("Failed to write analytics counter")


async def record(
    path: str, language: str, ui_lang: str, user_agent: str | None
) -> None:
    page = _PAGE_NAMES.get(path)
    if page is None:
        return
    device_type = detect_device_type(user_agent)
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    task = asyncio.create_task(
        asyncio.to_thread(_write, date, page, language, ui_lang, device_type)
    )
    _pending.add(task)
    task.add_done_callback(_pending.discard)
