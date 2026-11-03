"""Plus access requests, stored on the user doc: users/{uid}.plus_requests.<language>.

Entry shape: {requested_at, status: "open"|"granted", ui_language}. The account
email is written to users/{uid}.email from the verified token, never from a form.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from core.languages.config import PLUS_EXTRA_STUDY_LANGUAGES
from core.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"
_MAX_ADMIN_ROWS = 200


def is_requestable_language(language: str) -> bool:
    return language in PLUS_EXTRA_STUDY_LANGUAGES


def _user_doc(uid: str):
    return get_db().collection(USERS_COLLECTION).document(uid)


def _existing_entry(uid: str, language: str) -> dict[str, Any] | None:
    snapshot = _user_doc(uid).get()
    if not snapshot.exists:
        return None
    entry = ((snapshot.to_dict() or {}).get("plus_requests") or {}).get(language)
    return entry if isinstance(entry, dict) else None


def request_plus(*, uid: str, email: str, language: str, ui_language: str) -> bool:
    """Record the request. Returns False (and writes nothing) when one already exists.

    The check-then-write is not transactional on purpose: two simultaneous taps both write the same
    open entry, and a grant cannot land before the first request exists.
    """
    if _existing_entry(uid, language) is not None:
        return False
    _user_doc(uid).set(
        {
            "email": email,
            "plus_requests": {
                language: {
                    "requested_at": datetime.now(UTC),
                    "status": "open",
                    "ui_language": ui_language,
                }
            },
        },
        merge=True,
    )
    return True


def get_request_status(uid: str, language: str) -> str | None:
    """ "open", "granted", or None when this user never asked for this language."""
    entry = _existing_entry(uid, language)
    return str(entry.get("status") or "open") if entry else None


def mark_requests_granted(uid: str) -> None:
    """Flag this user's open requests as granted once an entitlement is made active. Best effort."""
    try:
        snapshot = _user_doc(uid).get()
        requests = ((snapshot.to_dict() or {}).get("plus_requests") or {}) if snapshot.exists else {}
        now = datetime.now(UTC)
        updates = {
            language: {"status": "granted", "granted_at": now}
            for language, entry in requests.items()
            if isinstance(entry, dict) and entry.get("status") == "open"
        }
        if updates:
            _user_doc(uid).set({"plus_requests": updates}, merge=True)
    except Exception:
        logger.warning("mark_requests_granted failed for uid=%s", uid, exc_info=True)


def list_open_requests() -> list[dict[str, Any]]:
    """Open requests across requestable languages, oldest first, for the admin page."""
    rows: list[dict[str, Any]] = []
    for language in PLUS_EXTRA_STUDY_LANGUAGES:
        query = get_db().collection(USERS_COLLECTION).where(f"plus_requests.{language}.status", "==", "open")
        for doc in query.limit(_MAX_ADMIN_ROWS).stream():
            data = doc.to_dict() or {}
            entry = (data.get("plus_requests") or {}).get(language) or {}
            requested_at: Any = entry.get("requested_at")
            rows.append(
                {
                    "uid": doc.id,
                    "email": str(data.get("email") or ""),
                    "language": language,
                    "requested_at": requested_at,
                    "requested_at_label": requested_at.strftime("%Y-%m-%d %H:%M")
                    if hasattr(requested_at, "strftime")
                    else "",
                }
            )
    rows.sort(
        key=lambda row: (
            row["requested_at"] if hasattr(row["requested_at"], "timestamp") else datetime.min.replace(tzinfo=UTC)
        )
    )
    return rows
