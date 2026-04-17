from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.storage.firestore_db import get_db

router = APIRouter()


@router.get("/api/feedback")
async def list_feedback() -> JSONResponse:
    db = get_db()
    docs = (
        db.collection("feedback")
        .order_by("created_at", direction="DESCENDING")
        .limit(200)
        .stream()
    )

    results: list[dict[str, Any]] = []
    for doc in docs:
        data = doc.to_dict()
        results.append(
            {
                "id": doc.id,
                "comment": data.get("comment", ""),
                "language": data.get("language", ""),
                "page": data.get("page", ""),
                "source": data.get("source", ""),
                "verb_id": data.get("verb_id", ""),
                "created_at": data["created_at"].isoformat()
                if data.get("created_at")
                else "",
            }
        )

    return JSONResponse({"feedback": results})


@router.delete("/api/feedback/{doc_id}")
async def delete_feedback(doc_id: str) -> JSONResponse:
    db = get_db()
    ref = db.collection("feedback").document(doc_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Document not found")

    ref.delete()
    return JSONResponse({"deleted": doc_id})
