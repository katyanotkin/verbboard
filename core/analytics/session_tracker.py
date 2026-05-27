from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import Request, Response

logger = logging.getLogger(__name__)

COLLECTION = "analytics_sessions"

_SID_COOKIE = "vb_sid"
_SEEN_COOKIE = "vb_seen"

_pending: set[asyncio.Task] = set()


def ensure_sid(request: Request) -> tuple[str, bool]:
    """Return (sid, is_new). is_new=True means no session cookie was present."""
    sid = request.cookies.get(_SID_COOKIE)
    if sid:
        return sid, False
    return str(uuid.uuid4()), True


def get_seen_pages(request: Request, date: str) -> set[str]:
    """Return set of page names already counted today for this session."""
    raw = request.cookies.get(_SEEN_COOKIE, "")
    if not raw:
        return set()
    cookie_date, _, pages_str = raw.partition("|")
    if cookie_date != date:
        return set()
    return set(pages_str.split(",")) if pages_str else set()


def set_seen_cookie(response: Response, date: str, pages: set[str]) -> None:
    value = f"{date}|{','.join(sorted(pages))}"
    response.set_cookie(_SEEN_COOKIE, value, httponly=True, samesite="lax")


def _write_session(
    sid: str, date: str, device_type: str, language: str, ui_lang: str
) -> None:
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{sid}"
    try:
        get_db().collection(COLLECTION).document(doc_id).set(
            {
                "sid": sid,
                "date": date,
                "device_type": device_type,
                "language": language or "",
                "ui_lang": ui_lang or "",
                "uid": None,
                "created_at": datetime.now(UTC),
            }
        )
    except Exception:
        logger.exception("Failed to write analytics session")


async def start_session(
    sid: str, date: str, device_type: str, language: str, ui_lang: str
) -> None:
    task = asyncio.create_task(
        asyncio.to_thread(_write_session, sid, date, device_type, language, ui_lang)
    )
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _attach_uid(sid: str, date: str, uid: str) -> None:
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{sid}"
    try:
        get_db().collection(COLLECTION).document(doc_id).set(
            {"uid": uid},
            merge=True,
        )
    except Exception:
        logger.exception("Failed to attach uid to analytics session")


async def attach_uid(sid: str, date: str, uid: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_attach_uid, sid, date, uid))
    _pending.add(task)
    task.add_done_callback(_pending.discard)
