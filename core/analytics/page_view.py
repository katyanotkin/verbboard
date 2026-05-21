from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from core.analytics.client_context import detect_device_type

logger = logging.getLogger(__name__)

COLLECTION = "page_views"
TRACKED_PATHS = frozenset({"/", "/verbs", "/learn"})

_pending: set[asyncio.Task] = set()


def _write(page: str, language: str, ui_lang: str, device_type: str) -> None:
    from core.storage.firestore_db import get_db

    try:
        get_db().collection(COLLECTION).document().set(
            {
                "created_at": datetime.now(UTC),
                "page": page,
                "language": language,
                "ui_lang": ui_lang,
                "device_type": device_type,
            }
        )
    except Exception:
        logger.exception("Failed to write page view")


async def record(
    path: str, language: str, ui_lang: str, user_agent: str | None
) -> None:
    if path not in TRACKED_PATHS:
        return
    device_type = detect_device_type(user_agent)
    task = asyncio.create_task(
        asyncio.to_thread(_write, path, language, ui_lang, device_type)
    )
    _pending.add(task)
    task.add_done_callback(_pending.discard)
