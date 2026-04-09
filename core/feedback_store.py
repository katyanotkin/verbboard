from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.cloud import firestore


def save_feedback(
    *,
    comment: str,
    page: str,
    language: str | None = None,
    verb_id: str | None = None,
    path: str | None = None,
    source: str = "preview",
    user_agent: str | None = None,
) -> str:
    cleaned_comment = comment.strip()
    if not cleaned_comment:
        raise ValueError("Feedback comment is empty")

    client = firestore.Client()
    payload: dict[str, Any] = {
        "comment": cleaned_comment,
        "page": page,
        "language": language or "",
        "verb_id": verb_id or "",
        "path": path or "",
        "source": source,
        "user_agent": user_agent or "",
        "created_at": datetime.now(UTC),
    }

    doc_ref = client.collection("feedback").document()
    doc_ref.set(payload)
    return doc_ref.id
