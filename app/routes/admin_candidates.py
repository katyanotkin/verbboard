from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import anthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from core.settings import _load_anthropic_api_key, _GENERATION_SYSTEM_PROMPT
from core.storage.firestore_db import get_db
from core.storage.verb_repository import find_verb_by_search_extract
from core.storage.verb_document import build_storage_verb_id


from app.routes.admin_utils import (
    CANDIDATES_COLLECTION,
    CANDIDATE_STATUSES,
    VERBS_COLLECTION,
    logger,
)

router = APIRouter()


def _get_max_rank(language: str) -> int:
    db = get_db()
    docs = db.collection(VERBS_COLLECTION).where("language", "==", language).stream()

    max_rank = 0
    for doc in docs:
        data = doc.to_dict()
        rank = data.get("rank")
        if isinstance(rank, (int, float)) and rank > max_rank:
            max_rank = int(rank)

    return max_rank


def _call_claude(language: str, query: str) -> dict[str, Any]:
    api_key = _load_anthropic_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-sonnet-4-6",  # was claude-opus-4-5
        max_tokens=2048,
        system=_GENERATION_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"language: {language}\n"
                    f"raw query (may be any inflected form): {query}"
                ),
            }
        ],
    )
    raw = message.content[0].text.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Claude returned invalid JSON for %s/%s: %s",
            language,
            query,
            raw[:2000],
        )
        raise HTTPException(
            status_code=502,
            detail=f"Generation returned invalid JSON for '{query}'",
        ) from exc


@router.get("/api/candidates")
async def list_candidates(language: str | None = None) -> JSONResponse:
    db = get_db()
    col = db.collection(CANDIDATES_COLLECTION)
    if language:
        col = col.where("language", "==", language)

    results: list[dict[str, Any]] = []
    for doc in col.stream():
        data = doc.to_dict()
        results.append(
            {
                "verb_id": data.get("verb_id", doc.id),
                "language": data.get("language", ""),
                "query": data.get("query", ""),
                "lemma": data.get("lemma") or "",
                "status": data.get("status", "needs_generation"),
                "rank": data.get("rank"),
                "forms": data.get("forms", {}),
                "examples": data.get("examples", []),
                "search_extract": data.get("search_extract", []),
                "created_at": data.get("created_at", ""),
                "updated_at": data.get("updated_at", ""),
            }
        )

    results.sort(key=lambda row: (row["language"], row["query"]))
    return JSONResponse({"candidates": results})


@router.post("/api/candidates/{verb_id}/generate")
async def generate_candidate(verb_id: str) -> JSONResponse:
    db = get_db()
    ref = db.collection(CANDIDATES_COLLECTION).document(verb_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Candidate not found")

    data = doc.to_dict()
    language = data.get("language", "")
    query = data.get("query", "")

    existing = find_verb_by_search_extract(language, query)
    if existing is not None:
        ref.update(
            {
                "status": "duplicate",
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        raise HTTPException(
            status_code=409,
            detail=f"'{query}' is already in the live verb set",
        )

    generated = _call_claude(language, query)

    lemma = generated.get("lemma") or query
    new_id = build_storage_verb_id(language=language, lemma=lemma)
    now = datetime.now(UTC).isoformat()

    if new_id != verb_id:
        existing_verb = db.collection(VERBS_COLLECTION).document(new_id).get()
        if existing_verb.exists:
            ref.update({"status": "duplicate", "updated_at": now})
            raise HTTPException(
                status_code=409,
                detail=f"Resolves to '{new_id}' which already exists in live verbs",
            )

        existing_cand = db.collection(CANDIDATES_COLLECTION).document(new_id).get()
        if existing_cand.exists:
            ref.update({"status": "duplicate", "updated_at": now})
            raise HTTPException(
                status_code=409,
                detail=f"Resolves to '{new_id}' which already exists as a candidate",
            )

    rank = _get_max_rank(language) + 1

    updated = {
        **data,
        "verb_id": new_id,
        "lemma": lemma,
        "morph": generated.get("morph") or None,
        "rank": rank,
        "status": "pending",
        "forms": generated.get("forms", {}),
        "examples": generated.get("examples", []),
        "search_extract": generated.get("search_extract", []),
        "updated_at": now,
    }

    if new_id != verb_id:
        db.collection(CANDIDATES_COLLECTION).document(new_id).set(updated)
        ref.delete()
    else:
        ref.set(updated)

    return JSONResponse({"old_id": verb_id, **updated})


@router.patch("/api/candidates/{verb_id}/status")
async def set_candidate_status(verb_id: str, request: Request) -> JSONResponse:
    body = await request.json()
    status = body.get("status", "").strip()
    if status not in CANDIDATE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"status must be one of {sorted(CANDIDATE_STATUSES)}",
        )

    db = get_db()
    ref = db.collection(CANDIDATES_COLLECTION).document(verb_id)
    if not ref.get().exists:
        raise HTTPException(status_code=404, detail="Candidate not found")

    ref.update({"status": status, "updated_at": datetime.now(UTC).isoformat()})
    return JSONResponse({"verb_id": verb_id, "status": status})


@router.post("/api/candidates/{verb_id}/promote")
async def promote_candidate(verb_id: str) -> JSONResponse:
    db = get_db()
    candidate_ref = db.collection(CANDIDATES_COLLECTION).document(verb_id)
    candidate_doc = candidate_ref.get()

    if not candidate_doc.exists:
        raise HTTPException(status_code=404, detail="Candidate not found")

    data = candidate_doc.to_dict()

    existing_verb = db.collection(VERBS_COLLECTION).document(verb_id).get()
    if existing_verb.exists:
        candidate_ref.update(
            {"status": "duplicate", "updated_at": datetime.now(UTC).isoformat()}
        )
        raise HTTPException(
            status_code=409,
            detail=f"'{verb_id}' already exists in the verbs collection",
        )

    now = datetime.now(UTC).isoformat()
    verb_doc = {key: value for key, value in data.items() if key != "status"}
    verb_doc["created_at"] = now
    verb_doc["updated_at"] = now

    db.collection(VERBS_COLLECTION).document(verb_id).set(verb_doc)
    candidate_ref.update({"status": "promoted", "updated_at": now})

    return JSONResponse(
        {"verb_id": verb_id, "promoted": True, "rank": data.get("rank")}
    )
