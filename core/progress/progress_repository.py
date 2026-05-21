from __future__ import annotations

from typing import Any

from google.cloud import firestore

from core.progress.models import PracticeProgress, VerbProgress
from core.storage.firestore_db import get_db

USERS_COLLECTION = "users"
USER_PROGRESS_COLLECTION = "user_progress"
LANGUAGES_SUBCOLLECTION = "languages"
VERBS_SUBCOLLECTION = "verbs"
USER_PRACTICE_COLLECTION = "user_practice"


# ---------------------------------------------------------------------------
# Internal path helpers
# ---------------------------------------------------------------------------


# user_progress/{uid}/languages/{lang}
def _progress_language_ref(user_id: str, language: str):
    db = get_db()
    return (
        db.collection(USER_PROGRESS_COLLECTION)
        .document(user_id)
        .collection(LANGUAGES_SUBCOLLECTION)
        .document(language)
    )


# user_progress/{uid}/languages/{lang}/verbs/{verb_id}
def _progress_verb_ref(user_id: str, language: str, verb_id: str):
    db = get_db()
    return (
        db.collection(USER_PROGRESS_COLLECTION)
        .document(user_id)
        .collection(LANGUAGES_SUBCOLLECTION)
        .document(language)
        .collection(VERBS_SUBCOLLECTION)
        .document(verb_id)
    )


# user_practice/{uid}/languages/{lang}
def _practice_doc_ref(user_id: str, language: str):
    db = get_db()
    return (
        db.collection(USER_PRACTICE_COLLECTION)
        .document(user_id)
        .collection(LANGUAGES_SUBCOLLECTION)
        .document(language)
    )


# ---------------------------------------------------------------------------
# User profile
# ---------------------------------------------------------------------------


def upsert_user_profile(
    *,
    user_id: str,
    email: str,
    name: str,
    picture: str,
) -> None:
    db = get_db()
    db.collection(USERS_COLLECTION).document(user_id).set(
        {
            "email": email,
            "name": name,
            "picture": picture,
            "last_seen_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )


def get_preferences(*, user_id: str) -> dict:
    db = get_db()
    doc = db.collection(USERS_COLLECTION).document(user_id).get()
    payload = (doc.to_dict() or {}) if doc.exists else {}
    return {
        "ui_language": payload.get("ui_language") or None,
        "learning_language": payload.get("learning_language") or None,
    }


def set_preferences(*, user_id: str, prefs: dict) -> None:
    db = get_db()
    data = {k: v for k, v in prefs.items() if v is not None}
    data["updated_at"] = firestore.SERVER_TIMESTAMP
    db.collection(USERS_COLLECTION).document(user_id).set(data, merge=True)


# ---------------------------------------------------------------------------
# Verb progress  (user_progress/{uid}/languages/{lang}/verbs/{verb_id})
# ---------------------------------------------------------------------------


def _upsert_language_doc(user_id: str, language: str) -> None:
    """Ensure the language container doc exists with a language field."""
    _progress_language_ref(user_id, language).set(
        {"language": language},
        merge=True,
    )


def mark_seen(
    *,
    user_id: str,
    language: str,
    verb_id: str,
) -> None:
    _upsert_language_doc(user_id, language)

    doc_ref = _progress_verb_ref(user_id, language, verb_id)
    existing = doc_ref.get()
    existing_payload: dict[str, Any] = existing.to_dict() or {}

    payload: dict[str, Any] = {
        "language": language,
        "verb_id": verb_id,
        "seen": True,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    # Preserve original first-seen timestamp.
    # Repeated syncs/page loads should not rewrite history.
    if not existing_payload.get("seen"):
        payload["first_seen_at"] = firestore.SERVER_TIMESTAMP

    doc_ref.set(
        payload,
        merge=True,
    )


def set_known(
    *,
    user_id: str,
    language: str,
    verb_id: str,
    known: bool,
) -> None:
    _upsert_language_doc(user_id, language)

    _progress_verb_ref(user_id, language, verb_id).set(
        {
            "language": language,
            "verb_id": verb_id,
            "known": known,
            "known_updated_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )


def list_progress_for_language(
    *,
    user_id: str,
    language: str,
) -> list[VerbProgress]:
    db = get_db()

    docs = list(
        db.collection(USER_PROGRESS_COLLECTION)
        .document(user_id)
        .collection(LANGUAGES_SUBCOLLECTION)
        .document(language)
        .collection(VERBS_SUBCOLLECTION)
        .stream()
    )

    progress_rows: list[VerbProgress] = []

    for doc in docs:
        payload: dict[str, Any] = doc.to_dict() or {}
        verb_id = str(payload.get("verb_id") or "")
        if not verb_id:
            continue
        progress_rows.append(
            VerbProgress(
                language=str(payload.get("language") or language),
                verb_id=verb_id,
                seen=bool(payload.get("seen", False)),
                known=bool(payload.get("known", False)),
            )
        )

    return progress_rows


# ---------------------------------------------------------------------------
# Practice progress  (user_practice/{uid}/languages/{lang})
# ---------------------------------------------------------------------------


def get_practice_progress(
    *,
    user_id: str,
    language: str,
) -> PracticeProgress:
    doc = _practice_doc_ref(user_id, language).get()

    payload: dict[str, Any] = doc.to_dict() or {}

    return PracticeProgress(
        language=language,
        badges=list(payload.get("badges", [])),
    )


def save_practice_progress(
    *,
    user_id: str,
    language: str,
    badges: list[int],
) -> None:
    doc_ref = _practice_doc_ref(user_id, language)

    data: dict[str, Any] = {
        "language": language,
        "badges": badges,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    # Set started_at only on the very first write (preserve original value afterwards).
    existing = doc_ref.get()
    if not existing.exists or not (existing.to_dict() or {}).get("started_at"):
        data["started_at"] = firestore.SERVER_TIMESTAMP

    doc_ref.set(data, merge=True)
