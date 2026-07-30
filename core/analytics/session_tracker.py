from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from fastapi import Request

from core.analytics.daily_counters import _clean_lang

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
    fingerprint: str, date: str, device_type: str, language: str, ui_lang: str, verb_viewed: bool = False
) -> None:
    from google.api_core.exceptions import AlreadyExists

    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    clean_language = _clean_lang(language)
    clean_ui_lang = _clean_lang(ui_lang)
    try:
        get_db().collection(COLLECTION).document(doc_id).create(
            {
                "sid": fingerprint,
                "date": date,
                "device_type": device_type,
                "language": clean_language,
                "ui_lang": clean_ui_lang,
                "uid": None,
                "verb_viewed": verb_viewed,
                "created_at": datetime.now(UTC),
            }
        )
    except AlreadyExists:
        # Session already exists for this day. Enrich language/ui_lang if the
        # session was created on a paramless first hit and now we have values;
        # verb_viewed only ever flips false -> true, never back.
        update: dict = {}
        if clean_language:
            update["language"] = clean_language
        if clean_ui_lang:
            update["ui_lang"] = clean_ui_lang
        if verb_viewed:
            update["verb_viewed"] = True
        if update:
            try:
                get_db().collection(COLLECTION).document(doc_id).set(update, merge=True)
            except Exception:
                logger.exception("Failed to enrich analytics session")
    except Exception:
        logger.exception("Failed to write analytics session")


async def start_session(
    fingerprint: str, date: str, device_type: str, language: str, ui_lang: str, verb_viewed: bool = False
) -> None:
    task = asyncio.create_task(
        asyncio.to_thread(_create_session, fingerprint, date, device_type, language, ui_lang, verb_viewed)
    )
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _enrich_lang(fingerprint: str, date: str, language: str, ui_lang: str) -> None:
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    update: dict = {}
    if language:
        update["language"] = language
    if ui_lang:
        update["ui_lang"] = ui_lang
    try:
        get_db().collection(COLLECTION).document(doc_id).set(update, merge=True)
    except Exception:
        logger.exception("Failed to enrich session lang")


async def enrich_lang(fingerprint: str, date: str, language: str, ui_lang: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_enrich_lang, fingerprint, date, language, ui_lang))
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


def delete_sessions_for_uid(uid: str) -> None:
    """Delete every analytics_sessions doc attached to this uid.

    Sessions are keyed by (ip, ua, date) fingerprint, not uid, so there's no
    direct doc-ID path -- this is a query, unlike every other uid-keyed
    deletion in this codebase. Synchronous (account deletion is a one-off,
    not a hot request path), unlike the fire-and-forget writer functions
    above.
    """
    from core.storage.firestore_db import get_db

    docs = get_db().collection(COLLECTION).where("uid", "==", uid).stream()
    for doc in docs:
        doc.reference.delete()
