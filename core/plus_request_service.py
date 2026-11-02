"""Plus access requests: signed-in users only, deduped per (uid, language)."""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from typing import Any

from google.api_core.exceptions import AlreadyExists

from core.languages.config import PLUS_EXTRA_STUDY_LANGUAGES
from core.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

PLUS_REQUESTS_COLLECTION = "plus_requests"
MAX_NOTE_LENGTH = 300
MAX_EMAIL_LENGTH = 200

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_valid_email(value: str) -> bool:
    return len(value) <= MAX_EMAIL_LENGTH and bool(_EMAIL_RE.match(value))


def is_requestable_language(language: str) -> bool:
    return language in PLUS_EXTRA_STUDY_LANGUAGES


def request_doc_id(uid: str, language: str) -> str:
    return hashlib.sha1(f"{uid}|{language}".encode()).hexdigest()[:16]


def create_plus_request(
    *, uid: str, email: str, contact_email: str, language: str, note: str, ui_language: str
) -> bool:
    """Write the request once. Returns False when this user already asked for this language."""
    doc_ref = get_db().collection(PLUS_REQUESTS_COLLECTION).document(request_doc_id(uid, language))
    try:
        doc_ref.create(
            {
                "uid": uid,
                "email": email,
                "contact_email": contact_email,
                "language": language,
                "note": note,
                "ui_language": ui_language,
                "created_at": datetime.now(UTC),
                "status": "open",
            }
        )
    except AlreadyExists:
        return False
    return True


def mark_requests_granted(uid: str) -> None:
    """Flag this user's open requests as granted once an entitlement is made active. Best effort."""
    try:
        docs = get_db().collection(PLUS_REQUESTS_COLLECTION).where("uid", "==", uid).stream()
        for doc in docs:
            data: dict[str, Any] = doc.to_dict() or {}
            if data.get("status") == "open":
                doc.reference.update({"status": "granted", "granted_at": datetime.now(UTC)})
    except Exception:
        logger.warning("mark_requests_granted failed for uid=%s", uid, exc_info=True)


def delete_plus_requests_for_uid(uid: str) -> None:
    """Account deletion: remove every Plus request this uid made."""
    for doc in get_db().collection(PLUS_REQUESTS_COLLECTION).where("uid", "==", uid).stream():
        doc.reference.delete()


def account_emails_by_request_ids(request_ids: set[str]) -> dict[str, str]:
    """Map plus_requests doc id -> verified account email, for the admin feedback list."""
    collection = get_db().collection(PLUS_REQUESTS_COLLECTION)
    found: dict[str, str] = {}
    for request_id in request_ids:
        snapshot = collection.document(request_id).get()
        email = (snapshot.to_dict() or {}).get("email") if snapshot.exists else None
        if email:
            found[request_id] = str(email)
    return found
