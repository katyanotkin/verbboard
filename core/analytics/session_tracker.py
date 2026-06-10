from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from fastapi import Request

logger = logging.getLogger(__name__)

COLLECTION = "analytics_sessions"

_pending: set[asyncio.Task] = set()


def get_fingerprint_sid(request: Request, date: str) -> str:
    """Deterministic session ID: SHA256(forwarded_ip|user_agent|date)[:32].

    Firebase Hosting strips all cookies except __session, so cookie-based
    session IDs cannot survive to Cloud Run. A server-side fingerprint derived
    from stable request headers gives one session doc per (IP, UA, day) without
    any cookie round-trip.
    """
    ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
        or "unknown"
    )
    ua = request.headers.get("user-agent", "")
    raw = f"{ip}|{ua}|{date}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _create_session(
    fingerprint: str, date: str, device_type: str, language: str, ui_lang: str
) -> None:
    from google.api_core.exceptions import AlreadyExists

    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        get_db().collection(COLLECTION).document(doc_id).create(
            {
                "sid": fingerprint,
                "date": date,
                "device_type": device_type,
                "language": language or "",
                "ui_lang": ui_lang or "",
                "uid": None,
                "created_at": datetime.now(UTC),
            }
        )
    except AlreadyExists:
        pass  # returning visitor within the same day -- expected, not an error
    except Exception:
        logger.exception("Failed to write analytics session")


async def start_session(
    fingerprint: str, date: str, device_type: str, language: str, ui_lang: str
) -> None:
    task = asyncio.create_task(
        asyncio.to_thread(
            _create_session, fingerprint, date, device_type, language, ui_lang
        )
    )
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _attach_uid(fingerprint: str, date: str, uid: str) -> None:
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        get_db().collection(COLLECTION).document(doc_id).set(
            {"uid": uid},
            merge=True,
        )
    except Exception:
        logger.exception("Failed to attach uid to analytics session")


async def attach_uid(fingerprint: str, date: str, uid: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_attach_uid, fingerprint, date, uid))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
