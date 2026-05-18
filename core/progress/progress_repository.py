from __future__ import annotations

from typing import Any

from google.cloud import firestore

from core.progress.models import PracticeProgress, VerbProgress
from core.storage.firestore_db import get_db

USERS_COLLECTION = "users"
USER_PROGRESS_COLLECTION = "user_progress"
VERBS_SUBCOLLECTION = "verbs"
USER_PRACTICE_COLLECTION = "user_practice"
LANGUAGES_SUBCOLLECTION = "languages"


def _progress_doc_ref(user_id: str, verb_id: str):
    db = get_db()
    return (
        db.collection(USER_PROGRESS_COLLECTION)
        .document(user_id)
        .collection(VERBS_SUBCOLLECTION)
        .document(verb_id)
    )


def _practice_doc_ref(user_id: str, language: str):
    db = get_db()
    return (
        db.collection(USER_PRACTICE_COLLECTION)
        .document(user_id)
        .collection(LANGUAGES_SUBCOLLECTION)
        .document(language)
    )


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


def mark_seen(
    *,
    user_id: str,
    language: str,
    verb_id: str,
) -> None:
    doc_ref = _progress_doc_ref(user_id, verb_id)

    doc_ref.set(
        {
            "language": language,
            "verb_id": verb_id,
            "seen": True,
            "seen_updated_at": firestore.SERVER_TIMESTAMP,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )


def set_known(
    *,
    user_id: str,
    language: str,
    verb_id: str,
    known: bool,
) -> None:
    doc_ref = _progress_doc_ref(user_id, verb_id)

    doc_ref.set(
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

    docs = (
        db.collection(USER_PROGRESS_COLLECTION)
        .document(user_id)
        .collection(VERBS_SUBCOLLECTION)
        .where("language", "==", language)
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
    _practice_doc_ref(user_id, language).set(
        {
            "language": language,
            "badges": badges,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
