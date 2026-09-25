from __future__ import annotations

import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from fastapi import Request

from core.analytics.daily_counters import _clean_lang, _clean_ui_lang

logger = logging.getLogger(__name__)

COLLECTION = "analytics_sessions"

# Referrers can carry arbitrarily long query strings (e.g. ad click IDs);
# bound the stored length defensively -- this is a diagnostic field, not
# something that needs full fidelity.
_MAX_REFERRER_LEN = 500

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
    fingerprint: str,
    date: str,
    device_type: str,
    language: str,
    ui_lang: str,
    verb_viewed: bool = False,
    referrer: str = "",
    home_viewed: bool = False,
) -> None:
    from google.api_core.exceptions import AlreadyExists

    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    clean_language = _clean_lang(language)
    clean_ui_lang = _clean_ui_lang(ui_lang)
    clean_referrer = (referrer or "").strip()[:_MAX_REFERRER_LEN]
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
                "home_viewed": home_viewed,
                "referrer": clean_referrer,
                "created_at": datetime.now(UTC),
            }
        )
    except AlreadyExists:
        # Session already exists for this day. Enrich language/ui_lang if the
        # session was created on a paramless first hit and now we have values;
        # verb_viewed and home_viewed only ever flip false -> true, never back. referrer is
        # only meaningful for the very first hit that started the session (it
        # identifies the traffic source), so it is deliberately not re-set here
        # -- same set-once-on-create treatment as device_type.
        update: dict = {}
        if clean_language:
            update["language"] = clean_language
        if clean_ui_lang:
            update["ui_lang"] = clean_ui_lang
        if verb_viewed:
            update["verb_viewed"] = True
        if home_viewed:
            update["home_viewed"] = True
        if update:
            try:
                get_db().collection(COLLECTION).document(doc_id).set(update, merge=True)
            except Exception:
                logger.exception("Failed to enrich analytics session")
    except Exception:
        logger.exception("Failed to write analytics session")


async def start_session(
    fingerprint: str,
    date: str,
    device_type: str,
    language: str,
    ui_lang: str,
    verb_viewed: bool = False,
    referrer: str = "",
    home_viewed: bool = False,
) -> None:
    task = asyncio.create_task(
        asyncio.to_thread(
            _create_session, fingerprint, date, device_type, language, ui_lang, verb_viewed, referrer, home_viewed
        )
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


_VALID_SIGN_IN_BRANCHES = {"standalone", "mobile", "desktop"}


def _record_sign_in_tap(fingerprint: str, date: str, branch: str) -> None:
    """Record which signIn() branch (standalone/mobile/desktop) a user tapped.

    Diagnostic only (issue #28: is sign-in friction losing people). Set-once
    like device_type -- only the first tap of the day's session is recorded,
    so a retry tap (e.g. after dismissing a popup) doesn't overwrite the
    original branch.
    """
    if branch not in _VALID_SIGN_IN_BRANCHES:
        return

    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        doc_ref = get_db().collection(COLLECTION).document(doc_id)
        snapshot = doc_ref.get()
        if snapshot.exists and snapshot.to_dict().get("sign_in_tapped_branch"):
            return
        doc_ref.set(
            {
                "sign_in_tapped_branch": branch,
                "sign_in_tapped_at": datetime.now(UTC),
            },
            merge=True,
        )
    except Exception:
        logger.exception("Failed to record sign-in tap")


async def record_sign_in_tap(fingerprint: str, date: str, branch: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_record_sign_in_tap, fingerprint, date, branch))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _record_practice_started(fingerprint: str, date: str) -> None:
    """Record that a practice session was started this session-day (issue #48).

    practice_loop.js has no auth gate anywhere -- an anonymous visitor can run
    full practice sessions leaving zero trace in the uid-keyed user_practice
    collection. This is a parallel, auth-independent engagement signal on
    analytics_sessions instead. Set-once like sign_in_tapped_branch -- only
    the first start of the day's session is recorded.
    """
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        doc_ref = get_db().collection(COLLECTION).document(doc_id)
        snapshot = doc_ref.get()
        if snapshot.exists and snapshot.to_dict().get("practice_started"):
            return
        doc_ref.set({"practice_started": True}, merge=True)
    except Exception:
        logger.exception("Failed to record practice started")


async def record_practice_started(fingerprint: str, date: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_record_practice_started, fingerprint, date))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _record_practice_completed(fingerprint: str, date: str) -> None:
    """Record that a practice session was completed this session-day (issue #48).

    Set-once, but deliberately does not depend on practice_started having
    landed first -- the started beacon could be lost (e.g. tab closed, flaky
    network) and completion is the more valuable of the two signals, so it
    must not be silently skipped just because the earlier write is missing.
    """
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        doc_ref = get_db().collection(COLLECTION).document(doc_id)
        snapshot = doc_ref.get()
        if snapshot.exists and snapshot.to_dict().get("practice_completed"):
            return
        doc_ref.set({"practice_completed": True}, merge=True)
    except Exception:
        logger.exception("Failed to record practice completed")


async def record_practice_completed(fingerprint: str, date: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_record_practice_completed, fingerprint, date))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _record_votd_clicked(fingerprint: str, date: str) -> None:
    """Record that the Verb of the Day hero on the home page was clicked this
    session-day (issue #33 follow-up: the hero was the dominant above-the-fold
    element but nothing measured whether anyone used it). Set-once like
    practice_started. Pair with `home_viewed` for a click-through rate.
    """
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        doc_ref = get_db().collection(COLLECTION).document(doc_id)
        snapshot = doc_ref.get()
        # No session doc means the click can't be paired with a home view (e.g.
        # it landed after a UTC date rollover); writing would create a stub
        # doc with no device_type/language that skews get_device_mix().
        if not snapshot.exists or snapshot.to_dict().get("votd_clicked"):
            return
        doc_ref.set({"votd_clicked": True}, merge=True)
    except Exception:
        logger.exception("Failed to record VOTD click")


async def record_votd_clicked(fingerprint: str, date: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_record_votd_clicked, fingerprint, date))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _record_ui_lang_selected(fingerprint: str, date: str, ui_lang: str) -> None:
    """Record that the visitor deliberately picked `ui_lang` in the UI-language
    dropdown (as opposed to getting it from the browser's Accept-Language or a
    saved preference). Lets the Hebrew UI review (issue #60) count real
    selections. The latest pick wins; a pick with no session doc is dropped
    rather than creating a stub doc."""
    clean = _clean_ui_lang(ui_lang)
    if not clean:
        return

    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        doc_ref = get_db().collection(COLLECTION).document(doc_id)
        if not doc_ref.get().exists:
            return
        doc_ref.set({"ui_lang_selected": clean}, merge=True)
    except Exception:
        logger.exception("Failed to record UI language selection")


async def record_ui_lang_selected(fingerprint: str, date: str, ui_lang: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_record_ui_lang_selected, fingerprint, date, ui_lang))
    _pending.add(task)
    task.add_done_callback(_pending.discard)


def _record_practice_gate_shown(fingerprint: str, date: str) -> None:
    """Record that this session-day was shown the sign-in gate when tapping Start
    on the practice panel (anonymous visitors must sign in to start practice).
    Set-once like practice_started. Pair with `uid` (attached when the same
    session later signs in) to read the gate's conversion. A gate shown with no
    existing session doc is dropped rather than creating a stub doc."""
    from core.storage.firestore_db import get_db

    doc_id = f"{date}_{fingerprint}"
    try:
        doc_ref = get_db().collection(COLLECTION).document(doc_id)
        snapshot = doc_ref.get()
        if not snapshot.exists or snapshot.to_dict().get("practice_gate_shown"):
            return
        doc_ref.set({"practice_gate_shown": True}, merge=True)
    except Exception:
        logger.exception("Failed to record practice gate shown")


async def record_practice_gate_shown(fingerprint: str, date: str) -> None:
    task = asyncio.create_task(asyncio.to_thread(_record_practice_gate_shown, fingerprint, date))
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
