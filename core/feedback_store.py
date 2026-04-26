from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore

FEEDBACK_COLLECTION = "feedback"


def save_feedback(
    *,
    comment: str | None,
    poll_id: str | None = None,
    poll_question: str | None = None,
    poll_answer: str | None = None,
    page: str,
    language: str | None = None,
    verb_id: str | None = None,
    path: str | None = None,
    source: str = "preview",
    user_agent: str | None = None,
) -> str:
    cleaned_comment = (comment or "").strip()
    cleaned_poll_answer = (poll_answer or "").strip()

    if not cleaned_comment and not cleaned_poll_answer:
        raise ValueError("Empty feedback")

    client = firestore.Client()
    doc_ref = client.collection(FEEDBACK_COLLECTION).document()

    payload: dict[str, Any] = {
        "comment": cleaned_comment,
        "poll_id": poll_id or "",
        "poll_question": poll_question or "",
        "poll_answer": cleaned_poll_answer,
        "page": page,
        "language": language or "",
        "verb_id": verb_id or "",
        "path": path or "",
        "source": source,
        "user_agent": user_agent or "",
        "created_at": datetime.now(UTC),
        "hidden": False,
    }

    doc_ref.set(payload)
    return doc_ref.id


def load_feedback() -> list[dict[str, Any]]:
    client = firestore.Client()
    documents = client.collection(FEEDBACK_COLLECTION).stream()

    feedback_rows: list[dict[str, Any]] = []

    for document in documents:
        payload = document.to_dict() or {}

        feedback_rows.append(
            {
                "id": document.id,
                "comment": str(payload.get("comment") or ""),
                "poll_answer": payload.get("poll_answer"),
                "page": str(payload.get("page") or ""),
                "language": str(payload.get("language") or ""),
                "verb_id": str(payload.get("verb_id") or ""),
                "path": str(payload.get("path") or ""),
                "source": str(payload.get("source") or ""),
                "user_agent": str(payload.get("user_agent") or ""),
                "created_at": payload.get("created_at"),
                "hidden": bool(payload.get("hidden", False)),
            }
        )

    return feedback_rows


def hide_feedback(feedback_id: str) -> bool:
    client = firestore.Client()
    doc_ref = client.collection(FEEDBACK_COLLECTION).document(feedback_id)
    snapshot = doc_ref.get()

    if not snapshot.exists:
        return False

    doc_ref.update({"hidden": True})
    return True
