from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from core.storage.firestore_db import get_db

_ADMIN_SECRET = os.getenv("ADMIN_SECRET", "admin-change-me")
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

router = APIRouter(prefix=f"/{_ADMIN_SECRET}")


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    html = (_TEMPLATES_DIR / "admin.html").read_text(encoding="utf-8")
    html = html.replace("__ADMIN_ROOT__", f"/{_ADMIN_SECRET}")
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Verb demand signals
# ---------------------------------------------------------------------------


def _cols() -> tuple[str, str]:
    """Return (signals_collection, labels_collection)."""
    from core.settings import load_settings

    s = load_settings()
    return s.verb_signals_collection, s.verb_signal_labels_collection


@router.get("/api/signals")
async def list_signals(
    language: str | None = None,
    include_processed: bool = False,
) -> JSONResponse:
    db = get_db()
    sig_col, _ = _cols()
    q = db.collection(sig_col).order_by("ts", direction="DESCENDING").limit(2000)
    if not include_processed:
        q = q.where("status", "==", None)
    if language:
        q = q.where("language", "==", language)
    results: list[dict[str, Any]] = []
    for doc in q.stream():
        data = doc.to_dict()
        results.append(
            {
                "id": doc.id,
                "ts": data.get("ts", ""),
                "language": data.get("language", ""),
                "query": data.get("query", ""),
                "status": data.get("status", None),
            }
        )
    return JSONResponse({"signals": results})


@router.delete("/api/signals/{doc_id}")
async def delete_signal(doc_id: str) -> JSONResponse:
    db = get_db()
    sig_col, _ = _cols()
    ref = db.collection(sig_col).document(doc_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Signal not found")
    ref.delete()
    return JSONResponse({"deleted": doc_id})


# ---------------------------------------------------------------------------
# Signal labels  (candidate / garbage — one doc per query+language)
# ---------------------------------------------------------------------------


@router.get("/api/signal_labels")
async def list_signal_labels() -> JSONResponse:
    db = get_db()
    _, lbl_col = _cols()
    results: list[dict[str, Any]] = []
    for doc in db.collection(lbl_col).stream():
        data = doc.to_dict()
        results.append(
            {
                "id": doc.id,
                "query": data.get("query", ""),
                "language": data.get("language", ""),
                "status": data.get("status", ""),
                "count": data.get("count", 0),
                "last_ts": data.get("last_ts", ""),
                "updated_at": data.get("updated_at", ""),
            }
        )
    return JSONResponse({"labels": results})


@router.post("/api/signal_labels")
async def classify_signal_group(request: Request) -> JSONResponse:
    """
    Write a label doc for query+language, then mark all matching raw
    signal docs as status='processed' in a batch.
    """
    body = await request.json()
    query = body.get("query", "").strip()
    language = body.get("language", "").strip()
    status = body.get("status")
    count = body.get("count", 0)
    last_ts = body.get("last_ts", "")

    if not query or not language:
        raise HTTPException(status_code=400, detail="query and language are required")
    if status not in {"candidate", "garbage"}:
        raise HTTPException(
            status_code=400, detail="status must be 'candidate' or 'garbage'"
        )

    db = get_db()
    sig_col, lbl_col = _cols()

    # upsert label doc
    label_id = f"{language}_{query}"
    db.collection(lbl_col).document(label_id).set(
        {
            "query": query,
            "language": language,
            "status": status,
            "count": count,
            "last_ts": last_ts,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    )

    # batch-mark matching raw signals as processed
    raw_docs = (
        db.collection(sig_col)
        .where("language", "==", language)
        .where("query", "==", query)
        .stream()
    )
    batch = db.batch()
    batch_size = 0
    for doc in raw_docs:
        batch.update(doc.reference, {"status": "processed"})
        batch_size += 1
        if batch_size == 500:  # Firestore batch limit
            batch.commit()
            batch = db.batch()
            batch_size = 0
    if batch_size:
        batch.commit()

    return JSONResponse({"id": label_id, "status": status, "processed": batch_size})


@router.delete("/api/signal_labels/{label_id}")
async def delete_signal_label(label_id: str) -> JSONResponse:
    """
    Remove a label and un-mark the corresponding raw signals (restore to null).
    """
    db = get_db()
    sig_col, lbl_col = _cols()

    ref = db.collection(lbl_col).document(label_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Label not found")

    data = doc.to_dict()
    query = data.get("query", "")
    language = data.get("language", "")

    ref.delete()

    # restore raw signals to unclassified
    raw_docs = (
        db.collection(sig_col)
        .where("language", "==", language)
        .where("query", "==", query)
        .where("status", "==", "processed")
        .stream()
    )
    batch = db.batch()
    batch_size = 0
    for doc in raw_docs:
        batch.update(doc.reference, {"status": None})
        batch_size += 1
        if batch_size == 500:
            batch.commit()
            batch = db.batch()
            batch_size = 0
    if batch_size:
        batch.commit()

    return JSONResponse({"deleted": label_id, "restored": batch_size})


# ---------------------------------------------------------------------------
# Verbs — search extracts for in-set classification
# ---------------------------------------------------------------------------


@router.get("/api/verbs/search_extracts")
async def get_search_extracts(language: str) -> JSONResponse:
    db = get_db()
    docs = db.collection("verbs").where("language", "==", language).stream()
    extracts: set[str] = set()
    for doc in docs:
        data = doc.to_dict()
        for term in data.get("search_extract") or []:
            if isinstance(term, str):
                extracts.add(term.casefold())
    return JSONResponse({"language": language, "extracts": sorted(extracts)})
