from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from google.cloud import firestore

from core.progress.models import (
    LEITNER_INTERVAL_DAYS,
    PracticeProgress,
    PracticeSessionSize,
    VerbProgress,
    leitner_next_box,
)
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
        db.collection(USER_PROGRESS_COLLECTION).document(user_id).collection(LANGUAGES_SUBCOLLECTION).document(language)
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
        db.collection(USER_PRACTICE_COLLECTION).document(user_id).collection(LANGUAGES_SUBCOLLECTION).document(language)
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
    doc_ref = db.collection(USERS_COLLECTION).document(user_id)
    data: dict[str, Any] = {
        "email": email,
        "name": name,
        "picture": picture,
        "last_seen_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }
    existing = doc_ref.get()
    if not existing.exists or not (existing.to_dict() or {}).get("created_at"):
        data["created_at"] = firestore.SERVER_TIMESTAMP
    doc_ref.set(data, merge=True)


def get_preferences(*, user_id: str) -> dict:
    db = get_db()
    doc = db.collection(USERS_COLLECTION).document(user_id).get()
    payload = (doc.to_dict() or {}) if doc.exists else {}
    raw_size = payload.get("practice_session_size")
    try:
        practice_session_size = PracticeSessionSize(raw_size).value if raw_size is not None else None
    except ValueError:
        practice_session_size = None

    raw_min_plays = payload.get("practice_min_plays")
    if raw_min_plays == "all":
        practice_min_plays: int | str | None = "all"
    elif raw_min_plays in (1, 3, 5, 8):
        practice_min_plays = raw_min_plays
    else:
        practice_min_plays = None

    return {
        "ui_language": payload.get("ui_language") or None,
        "learning_language": payload.get("learning_language") or None,
        "practice_session_size": practice_session_size,
        "practice_min_plays": practice_min_plays,
    }


def set_preferences(*, user_id: str, prefs: dict) -> None:
    db = get_db()
    data = {k: v for k, v in prefs.items() if v is not None}
    data["updated_at"] = firestore.SERVER_TIMESTAMP
    db.collection(USERS_COLLECTION).document(user_id).set(data, merge=True)


# ---------------------------------------------------------------------------
# Verb progress  (user_progress/{uid}/languages/{lang}/verbs/{verb_id})
# ---------------------------------------------------------------------------


def _leitner_due_at(box: int, *, from_time: datetime | None = None) -> datetime:
    if not 1 <= box <= len(LEITNER_INTERVAL_DAYS):
        raise ValueError(f"box must be between 1 and {len(LEITNER_INTERVAL_DAYS)}, got {box}")
    base = from_time or datetime.now(timezone.utc)
    days = LEITNER_INTERVAL_DAYS[box - 1]
    return base + timedelta(days=days)


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

    doc_ref = _progress_verb_ref(user_id, language, verb_id)

    payload: dict[str, Any] = {
        "language": language,
        "verb_id": verb_id,
        "known": known,
        "known_updated_at": firestore.SERVER_TIMESTAMP,
        "updated_at": firestore.SERVER_TIMESTAMP,
    }

    # "known" is the entry point into the spaced-repetition review ladder --
    # a verb the user marks known starts its review clock. Unmarking known
    # does not remove it from the ladder (rare edge case, not worth the extra
    # write-path complexity); only marking known (re-)enters it, and only if
    # it isn't already in the ladder, so re-toggling known doesn't reset a
    # verb's box/due date.
    if known:
        existing_payload: dict[str, Any] = doc_ref.get().to_dict() or {}
        if not existing_payload.get("srs_box"):
            now = datetime.now(timezone.utc)
            payload["srs_box"] = 1
            payload["srs_due_at"] = _leitner_due_at(1, from_time=now)
            payload["srs_reviewed_at"] = now

    doc_ref.set(payload, merge=True)


def record_review(
    *,
    user_id: str,
    language: str,
    verb_id: str,
    recalled: bool,
) -> dict[str, Any]:
    """Advance a verb's Leitner box after a practice-loop review.

    Recalled -> promote one box (capped at LEITNER_MAX_BOX). Not recalled ->
    demote to box 1 (not box 0 -- the verb stays in the ladder, it just
    resurfaces sooner). A verb with no prior box (srs_box 0, e.g. reviewed
    before ever being marked known through the normal path) starts at box 1
    either way, since a review action is itself evidence the verb is being
    actively studied.
    """
    _upsert_language_doc(user_id, language)

    doc_ref = _progress_verb_ref(user_id, language, verb_id)
    existing_payload: dict[str, Any] = doc_ref.get().to_dict() or {}
    current_box = int(existing_payload.get("srs_box") or 0)

    next_box = leitner_next_box(current_box, recalled)

    now = datetime.now(timezone.utc)
    due_at = _leitner_due_at(next_box, from_time=now)

    doc_ref.set(
        {
            "language": language,
            "verb_id": verb_id,
            "known": True,
            "srs_box": next_box,
            "srs_due_at": due_at,
            "srs_reviewed_at": now,
            "updated_at": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )

    return {"box": next_box, "due_at": due_at}


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
        srs_due_at = payload.get("srs_due_at")
        srs_reviewed_at = payload.get("srs_reviewed_at")
        progress_rows.append(
            VerbProgress(
                language=str(payload.get("language") or language),
                verb_id=verb_id,
                seen=bool(payload.get("seen", False)),
                known=bool(payload.get("known", False)),
                srs_box=int(payload.get("srs_box") or 0),
                srs_due_at=srs_due_at if isinstance(srs_due_at, datetime) else None,
                srs_reviewed_at=srs_reviewed_at if isinstance(srs_reviewed_at, datetime) else None,
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

    existing = doc_ref.get()
    existing_payload: dict[str, Any] = existing.to_dict() or {}

    if not existing.exists or not existing_payload.get("started_at"):
        data["started_at"] = firestore.SERVER_TIMESTAMP

    doc_ref.set(data, merge=True)


# ---------------------------------------------------------------------------
# Full account deletion
# ---------------------------------------------------------------------------


def delete_all_progress_data(user_id: str) -> None:
    """Delete every uid-keyed doc this module owns: users/{uid},
    user_progress/{uid}/languages/{lang}/verbs/{verb_id} (+ parents), and
    user_practice/{uid}/languages/{lang} (+ parent).

    Enumerates the actual `languages` subcollections rather than iterating
    over the currently-configured language list -- that list only describes
    languages supported *today*, not every language a long-lived account may
    have data under.
    """
    db = get_db()

    progress_ref = db.collection(USER_PROGRESS_COLLECTION).document(user_id)
    for language_doc in progress_ref.collection(LANGUAGES_SUBCOLLECTION).stream():
        for verb_doc in language_doc.reference.collection(VERBS_SUBCOLLECTION).stream():
            verb_doc.reference.delete()
        language_doc.reference.delete()
    progress_ref.delete()

    practice_ref = db.collection(USER_PRACTICE_COLLECTION).document(user_id)
    for language_doc in practice_ref.collection(LANGUAGES_SUBCOLLECTION).stream():
        language_doc.reference.delete()
    practice_ref.delete()

    db.collection(USERS_COLLECTION).document(user_id).delete()
