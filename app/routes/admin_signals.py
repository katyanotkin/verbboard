from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.storage.firestore_db import get_db

from app.routes.admin_utils import CANDIDATES_COLLECTION, signal_collections

router = APIRouter()


@router.get("/api/signals")
async def list_signals(
    language: str | None = None,
    include_processed: bool = False,
    status: str | None = None,
    sort_by: str = "ts",
    sort_dir: str = "desc",
) -> JSONResponse:
    db = get_db()
    sig_col, _ = signal_collections()

    query_ref = db.collection(sig_col)

    if language:
        query_ref = query_ref.where("language", "==", language)

    if status is not None:
        normalized_status = status.strip().lower()
        if normalized_status in {"", "none", "unprocessed", "raw"}:
            query_ref = query_ref.where("status", "==", None)
        else:
            query_ref = query_ref.where("status", "==", normalized_status)
    elif not include_processed:
        query_ref = query_ref.where("status", "==", None)

    docs = query_ref.limit(2000).stream()

    results: list[dict[str, Any]] = []
    for doc in docs:
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

    allowed_sort_fields = {"ts", "language", "query", "status"}
    if sort_by not in allowed_sort_fields:
        raise HTTPException(
            status_code=400,
            detail=f"sort_by must be one of {sorted(allowed_sort_fields)}",
        )

    if sort_dir not in {"asc", "desc"}:
        raise HTTPException(status_code=400, detail="sort_dir must be 'asc' or 'desc'")

    reverse_sort = sort_dir == "desc"

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        value = item.get(sort_by)
        if value is None:
            return (1, "")
        return (0, str(value).casefold())

    results.sort(key=sort_key, reverse=reverse_sort)
    return JSONResponse({"signals": results})


@router.delete("/api/signals/{doc_id}")
async def delete_signal(doc_id: str) -> JSONResponse:
    db = get_db()
    sig_col, _ = signal_collections()

    ref = db.collection(sig_col).document(doc_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Signal not found")

    ref.delete()
    return JSONResponse({"deleted": doc_id})


@router.get("/api/signal_labels")
async def list_signal_labels() -> JSONResponse:
    db = get_db()
    _, lbl_col = signal_collections()

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
            status_code=400,
            detail="status must be 'candidate' or 'garbage'",
        )

    # When marked as candidate, create a stub candidate document if missing.
    if status == "candidate":
        db_ref = get_db()
        stub_id = f"{language}_{query}"
        existing = db_ref.collection(CANDIDATES_COLLECTION).document(stub_id).get()
        if not existing.exists:
            now = datetime.now(UTC).isoformat()
            db_ref.collection(CANDIDATES_COLLECTION).document(stub_id).set(
                {
                    "verb_id": stub_id,
                    "language": language,
                    "query": query,
                    "lemma": None,
                    "display_lemma": None,
                    "display_forms": None,
                    "morph": None,
                    "rank": None,
                    "status": "needs_generation",
                    "forms": {},
                    "examples": [],
                    "search_extract": [],
                    "created_at": now,
                    "updated_at": now,
                }
            )

    db = get_db()
    sig_col, lbl_col = signal_collections()

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

    raw_docs = (
        db.collection(sig_col)
        .where("language", "==", language)
        .where("query", "==", query)
        .stream()
    )

    batch = db.batch()
    batch_size = 0
    for doc in raw_docs:
        batch.update(doc.reference, {"status": status})
        batch_size += 1
        if batch_size == 500:
            batch.commit()
            batch = db.batch()
            batch_size = 0

    if batch_size:
        batch.commit()

    return JSONResponse({"id": label_id, "status": status, "processed": batch_size})


@router.delete("/api/signal_labels/{label_id}")
async def delete_signal_label(label_id: str) -> JSONResponse:
    db = get_db()
    sig_col, lbl_col = signal_collections()

    ref = db.collection(lbl_col).document(label_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Label not found")

    data = doc.to_dict()
    query = data.get("query", "")
    language = data.get("language", "")
    label_status = data.get("status")

    ref.delete()

    raw_docs = (
        db.collection(sig_col)
        .where("language", "==", language)
        .where("query", "==", query)
        .where("status", "==", label_status)
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
