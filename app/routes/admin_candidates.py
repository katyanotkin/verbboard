from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ValidationError

from app.routes.admin_utils import (
    CANDIDATE_STATUSES,
    CANDIDATES_COLLECTION,
    VERBS_COLLECTION,
    logger,
    require_admin_api,
)
from core.admin_logging import resolve_signal_label
from core.search_utils import normalize_text
from core.settings import _load_anthropic_api_key
from core.settings_ai import (
    _MAX_TOKENS,
    _MAX_TOKENS_DEFAULT,
    _MODEL,
    _MODEL_DEFAULT,
    get_anthropic_client,
    get_cached_system,
)
from core.storage.firestore_db import get_db
from core.storage.verb_document import (
    build_search_extract_from_entry,
    build_storage_verb_id,
)
from core.storage.verb_repository import find_verb_by_search_extract
from core.translation_service import translate_examples, translate_lemma
from core.utils import json_safe

_GCP_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")


class _ClaudeVerbResponse(BaseModel):
    lemma: str | None = None
    morph: str | dict[str, Any] | None = None
    forms: dict[str, Any] = {}
    examples: list[Any] = []
    pronoun_forms: dict[str, Any] | None = None
    tts_forms: dict[str, Any] | None = None


_NO_AUDIO_ROW_KEYS: frozenset[str] = frozenset({"aspect", "pair", "binyan", "root"})


async def _warm_verb_audio(audio_backend, language: str, verb_data: dict) -> None:
    """Pre-generate audio for all form rows and examples in both voices."""
    from core.audio_service import build_hashed_audio_key, ensure_audio
    from core.models import Example, VerbEntry
    from core.registry import get as get_plugin
    from core.tts import VOICES

    if language not in VOICES:
        return

    plugin = get_plugin(language)
    examples = [
        Example(
            dst=ex["dst"],
            translations={
                k: v for k, v in ex.get("translations", {}).items() if isinstance(k, str) and isinstance(v, str)
            },
        )
        for ex in verb_data.get("examples", [])
        if isinstance(ex, dict) and isinstance(ex.get("dst"), str)
    ]
    verb = VerbEntry(
        id=verb_data["verb_id"],
        rank=int(verb_data.get("rank") or 999999),
        lemma=verb_data["lemma"],
        forms=verb_data.get("forms", {}),
        examples=examples,
        morph=verb_data.get("morph"),
        tags=verb_data.get("tags"),
        display_lemma=verb_data.get("display_lemma"),
        display_forms=verb_data.get("display_forms"),
        tts_forms=verb_data.get("tts_forms"),
    )

    tasks = []
    for voice_key, voice_meta in VOICES[language].items():
        board = plugin.build_board(verb, voice_key, voice_meta.label)
        for section in board.sections:
            for row in section["rows"]:
                base_key = str(row["key"])
                if base_key in _NO_AUDIO_ROW_KEYS:
                    continue
                text = str(row["text"] or "").strip()
                if not text:
                    continue
                tts_text = str(row.get("tts_text") or "").strip() or text
                form_key = build_hashed_audio_key(base_key, tts_text)
                tasks.append(
                    ensure_audio(
                        audio_backend=audio_backend,
                        text=tts_text,
                        language=language,
                        verb_id=verb.id,
                        voice=voice_key,
                        form_key=form_key,
                        voice_edge_id=voice_meta.edge_id,
                    )
                )
        for idx, example in enumerate(board.verb.examples, start=1):
            text = example.dst.strip()
            if not text:
                continue
            form_key = build_hashed_audio_key(f"example_{idx}", text)
            tasks.append(
                ensure_audio(
                    audio_backend=audio_backend,
                    text=text,
                    language=language,
                    verb_id=verb.id,
                    voice=voice_key,
                    form_key=form_key,
                    voice_edge_id=voice_meta.edge_id,
                )
            )

    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Audio pre-generation error %s/%s: %s", language, verb.id, r)


router = APIRouter()


def _get_max_rank(language: str) -> int:
    # Concurrent generations can both read the same max before either writes,
    # so duplicate ranks are possible. Rank is a loose ordering hint, not a unique key.
    db = get_db()
    result = db.collection(VERBS_COLLECTION).where("language", "==", language).count().get()
    return result[0][0].value


async def _call_claude_single_example(language: str, lemma: str, existing_examples: list, index: int) -> dict[str, Any]:
    client = get_anthropic_client()
    existing_texts = [
        # regen-format examples: src = native sentence, dst = English translation
        # old-format examples:   only dst = native sentence
        ex.get("src") or ex.get("dst", "")
        for i, ex in enumerate(existing_examples)
        if i != index and isinstance(ex, dict) and (ex.get("src") or ex.get("dst"))
    ]
    avoid_note = (
        "Avoid repeating these existing examples:\n" + "\n".join(f"- {t}" for t in existing_texts)
        if existing_texts
        else ""
    )
    original_ex = existing_examples[index] if 0 <= index < len(existing_examples) else {}
    original_native = original_ex.get("src") or original_ex.get("dst", "") if isinstance(original_ex, dict) else ""
    form_note = (
        f"Replace this example: {original_native!r}\n"
        "Use the SAME grammatical form (same person, number, tense, aspect) but completely different content.\n"
        if original_native
        else ""
    )
    prompt = (
        f'Generate ONE new example sentence for the {language} verb "{lemma}".\n'
        f"{form_note}"
        f"{avoid_note}\n\n"
        "Return ONLY a JSON object:\n"
        '{"src": "<sentence in target language>", "dst": "<English translation>"}'
    )
    message = await client.messages.create(
        model=_MODEL.get(language, _MODEL_DEFAULT),
        max_tokens=512,
        temperature=0,
        system=get_cached_system(language),
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=502, detail="Example generation returned invalid JSON") from exc
    if not isinstance(result.get("src"), str) or not isinstance(result.get("dst"), str):
        raise HTTPException(status_code=502, detail="Example generation returned unexpected format")
    return {"src": result["src"], "dst": result["dst"]}


async def _call_claude(language: str, query: str) -> dict[str, Any]:
    client = get_anthropic_client()

    message = await client.messages.create(
        model=_MODEL.get(language, _MODEL_DEFAULT),
        max_tokens=_MAX_TOKENS.get(language, _MAX_TOKENS_DEFAULT),
        temperature=0,
        system=get_cached_system(language),
        messages=[
            {
                "role": "user",
                "content": (f"language: {language}\nraw query (may be any inflected form): {query}"),
            },
        ],
    )
    raw = message.content[0].text.strip()
    # Strip markdown fences if present (e.g. ```json ... ```)
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw).strip()

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
async def list_candidates(request: Request, language: str | None = None) -> JSONResponse:
    require_admin_api(request)
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
async def generate_candidate(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)
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
        ref.delete()
        raise HTTPException(
            status_code=409,
            detail=f"'{query}' is already in the live verb set",
        )

    existing_by_id = db.collection(VERBS_COLLECTION).document(verb_id).get()
    if existing_by_id.exists:
        ref.delete()
        raise HTTPException(
            status_code=409,
            detail=f"'{verb_id}' already exists in the live verb set",
        )

    generated = await _call_claude(language, query)
    try:
        _ClaudeVerbResponse.model_validate(generated)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail=f"Generation returned unexpected shape: {exc.error_count()} field errors"
        ) from exc

    lemma = generated.get("lemma") or query
    new_id = build_storage_verb_id(language=language, lemma=lemma)
    now = datetime.now(UTC).isoformat()

    if new_id != verb_id:
        existing_verb = db.collection(VERBS_COLLECTION).document(new_id).get()
        if existing_verb.exists:
            ref.delete()
            raise HTTPException(
                status_code=409,
                detail=f"Resolves to '{new_id}' which already exists in live verbs",
            )

        existing_cand = db.collection(CANDIDATES_COLLECTION).document(new_id).get()
        if existing_cand.exists:
            ref.delete()
            raise HTTPException(
                status_code=409,
                detail=f"Resolves to '{new_id}' which already exists as a candidate",
            )

    rank = await asyncio.to_thread(_get_max_rank, language) + 1

    updated = {
        **data,
        "verb_id": new_id,
        "lemma": lemma,
        "morph": generated.get("morph") or None,
        "rank": rank,
        "status": "pending",
        "forms": generated.get("forms", {}),
        "examples": generated.get("examples", []),
        # search_extract built locally — no LLM tokens spent
        "search_extract": build_search_extract_from_entry(language=language, entry=generated),
        "updated_at": now,
    }
    if generated.get("pronoun_forms"):
        updated["pronoun_forms"] = generated["pronoun_forms"]
    if generated.get("tts_forms"):
        updated["tts_forms"] = generated["tts_forms"]

    if new_id != verb_id:
        db.collection(CANDIDATES_COLLECTION).document(new_id).set(updated)
        ref.delete()
    else:
        ref.set(updated)

    api_key = _load_anthropic_api_key()
    translated_examples, lemma_translations = await asyncio.gather(
        asyncio.to_thread(
            translate_examples,
            verb_lang=language,
            lemma=lemma,
            examples=updated["examples"],
            project=_GCP_PROJECT,
            api_key=api_key,
        ),
        asyncio.to_thread(
            translate_lemma,
            verb_lang=language,
            lemma=lemma,
            project=_GCP_PROJECT,
            api_key=api_key,
        ),
    )
    translation_update: dict[str, Any] = {}
    if translated_examples is not updated["examples"]:
        translation_update["examples"] = translated_examples
        updated["examples"] = translated_examples
    if lemma_translations:
        translation_update["lemma_translations"] = lemma_translations
        updated["lemma_translations"] = lemma_translations
    if translation_update:
        translation_update["updated_at"] = datetime.now(UTC).isoformat()
        db.collection(CANDIDATES_COLLECTION).document(new_id).update(translation_update)

    asyncio.create_task(
        _warm_verb_audio(
            audio_backend=request.app.state.audio_backend,
            language=language,
            verb_data=updated,
        )
    )

    return JSONResponse({"old_id": verb_id, **updated})


@router.patch("/api/candidates/{verb_id}/status")
async def set_candidate_status(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)
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
async def promote_candidate(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)
    db = get_db()
    candidate_ref = db.collection(CANDIDATES_COLLECTION).document(verb_id)
    candidate_doc = candidate_ref.get()

    if not candidate_doc.exists:
        raise HTTPException(status_code=404, detail="Candidate not found")

    data = candidate_doc.to_dict()

    if data.get("status") != "pending":
        raise HTTPException(
            status_code=422,
            detail=f"Cannot promote: only 'pending' candidates can be promoted, got '{data.get('status')}'",
        )

    existing_verb = db.collection(VERBS_COLLECTION).document(verb_id).get()
    if existing_verb.exists:
        candidate_ref.update({"status": "duplicate", "updated_at": datetime.now(UTC).isoformat()})
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
    resolve_signal_label(language=data.get("language", ""), query=data.get("query", ""))

    return JSONResponse({"verb_id": verb_id, "promoted": True, "rank": data.get("rank")})


@router.get("/api/verbs")
async def search_live_verbs(request: Request, query: str = "", language: str = "") -> JSONResponse:
    require_admin_api(request)
    normalized = normalize_text(query)
    if not normalized:
        raise HTTPException(status_code=400, detail="query parameter is required")

    db = get_db()
    q = db.collection(VERBS_COLLECTION).where("search_extract", "array_contains", normalized)
    if language:
        q = q.where("language", "==", language)

    results = [json_safe(doc.to_dict()) for doc in q.stream()]
    results.sort(key=lambda v: (v.get("language", ""), v.get("rank") or 9999))
    return JSONResponse({"verbs": results})


@router.get("/api/verbs/{verb_id}")
async def get_live_verb(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)
    db = get_db()
    doc = db.collection(VERBS_COLLECTION).document(verb_id).get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Verb not found in live verbs collection")
    return JSONResponse(json_safe(doc.to_dict()))


@router.post("/api/verbs/{verb_id}/regenerate")
async def regenerate_verb(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)
    db = get_db()
    doc_ref = db.collection(VERBS_COLLECTION).document(verb_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Verb not found in live verbs collection")

    existing = doc.to_dict()
    language = existing.get("language", "")
    lemma = existing.get("lemma", "")
    if not language or not lemma:
        raise HTTPException(status_code=422, detail="Verb document is missing language or lemma")

    generated = await _call_claude(language, lemma)
    try:
        _ClaudeVerbResponse.model_validate(generated)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail=f"Regeneration returned unexpected shape: {exc.error_count()} field errors"
        ) from exc

    now = datetime.now(UTC).isoformat()
    payload: dict[str, Any] = {
        "verb_id": verb_id,
        "language": language,
        "lemma": lemma,
        "rank": existing.get("rank"),
        "morph": generated.get("morph") or None,
        "forms": generated.get("forms", {}),
        "examples": generated.get("examples", []),
        "search_extract": build_search_extract_from_entry(language=language, entry=generated),
        "display_lemma": existing.get("display_lemma"),
        "display_forms": existing.get("display_forms"),
        "created_at": existing.get("created_at"),
        "updated_at": now,
    }
    pronoun_forms = generated.get("pronoun_forms")
    if pronoun_forms:
        payload["pronoun_forms"] = pronoun_forms
    # tts_forms intentionally omitted: forms now carry nikud directly

    doc_ref.set(payload)

    api_key = _load_anthropic_api_key()
    translated_examples, lemma_translations = await asyncio.gather(
        asyncio.to_thread(
            translate_examples,
            verb_lang=language,
            lemma=lemma,
            examples=payload["examples"],
            project=_GCP_PROJECT,
            api_key=api_key,
        ),
        asyncio.to_thread(
            translate_lemma,
            verb_lang=language,
            lemma=lemma,
            existing_translations=existing.get("lemma_translations"),
            project=_GCP_PROJECT,
            api_key=api_key,
        ),
    )
    translation_update: dict[str, Any] = {}
    if translated_examples is not payload["examples"]:
        translation_update["examples"] = translated_examples
        payload["examples"] = translated_examples
    if lemma_translations:
        translation_update["lemma_translations"] = lemma_translations
        payload["lemma_translations"] = lemma_translations
    if translation_update:
        translation_update["updated_at"] = datetime.now(UTC).isoformat()
        doc_ref.update(translation_update)

    asyncio.create_task(
        _warm_verb_audio(
            audio_backend=request.app.state.audio_backend,
            language=language,
            verb_data=payload,
        )
    )

    return JSONResponse({"verb_id": verb_id, "regenerated": True, "lemma": lemma, "updated_at": now})


@router.post("/api/verbs/{verb_id}/regen_examples")
async def regen_verb_examples(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)
    db = get_db()
    doc_ref = db.collection(VERBS_COLLECTION).document(verb_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Verb not found in live verbs collection")

    existing = doc.to_dict()
    language = existing.get("language", "")
    lemma = existing.get("lemma", "")
    if not language or not lemma:
        raise HTTPException(status_code=422, detail="Verb document is missing language or lemma")

    generated = await _call_claude(language, lemma)
    new_examples = generated.get("examples", [])

    translated = await asyncio.to_thread(
        translate_examples,
        verb_lang=language,
        lemma=lemma,
        examples=new_examples,
        project=_GCP_PROJECT,
        api_key=_load_anthropic_api_key(),
    )

    now = datetime.now(UTC).isoformat()
    doc_ref.update({"examples": translated, "updated_at": now})

    return JSONResponse({"verb_id": verb_id, "examples_count": len(translated), "updated_at": now})


@router.post("/api/verbs/{verb_id}/regen_forms")
async def regen_verb_forms(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)
    db = get_db()
    doc_ref = db.collection(VERBS_COLLECTION).document(verb_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Verb not found in live verbs collection")

    existing = doc.to_dict()
    language = existing.get("language", "")
    lemma = existing.get("lemma", "")
    if not language or not lemma:
        raise HTTPException(status_code=422, detail="Verb document is missing language or lemma")

    generated = await _call_claude(language, lemma)
    try:
        _ClaudeVerbResponse.model_validate(generated)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502, detail=f"Regeneration returned unexpected shape: {exc.error_count()} field errors"
        ) from exc

    now = datetime.now(UTC).isoformat()
    update: dict[str, Any] = {
        "morph": generated.get("morph") or None,
        "forms": generated.get("forms", {}),
        "search_extract": build_search_extract_from_entry(language=language, entry=generated),
        "pronoun_forms": generated.get("pronoun_forms") or None,
        "tts_forms": None,  # forms now carry nikud directly; clear legacy tts_forms
        "updated_at": now,
    }
    doc_ref.update(update)

    updated_verb_data = {**existing, **update}
    asyncio.create_task(
        _warm_verb_audio(
            audio_backend=request.app.state.audio_backend,
            language=language,
            verb_data=updated_verb_data,
        )
    )

    return JSONResponse({"verb_id": verb_id, "regenerated": True, "updated_at": now})


@router.post("/api/candidates/{verb_id}/examples/{index}/regen")
async def regen_candidate_example(request: Request, verb_id: str, index: int) -> JSONResponse:
    require_admin_api(request)
    db = get_db()
    ref = db.collection(CANDIDATES_COLLECTION).document(verb_id)
    doc = ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="Candidate not found")

    data = doc.to_dict()
    language = data.get("language", "")
    lemma = data.get("lemma", "")
    if not language or not lemma:
        raise HTTPException(
            status_code=422,
            detail="Candidate is missing language or lemma (run Generate first)",
        )

    examples = list(data.get("examples", []))

    if index < 0 or index >= len(examples):
        raise HTTPException(
            status_code=400,
            detail=f"Example index {index} out of range (have {len(examples)})",
        )

    new_example = await _call_claude_single_example(language, lemma, examples, index)

    # translate_examples expects dst = native sentence; use src when present (regen format)
    native_sentence = new_example.get("src") or new_example.get("dst", "")
    translated = await asyncio.to_thread(
        translate_examples,
        verb_lang=language,
        lemma=lemma,
        examples=[{"dst": native_sentence}],
        project=_GCP_PROJECT,
        api_key=_load_anthropic_api_key(),
    )
    if translated:
        translations = translated[0].get("translations")
        if translations:
            new_example = {**new_example, "translations": translations}

    examples[index] = new_example
    now = datetime.now(UTC).isoformat()
    ref.update({"examples": examples, "updated_at": now})

    return JSONResponse({"index": index, "example": new_example, "updated_at": now})


@router.delete("/api/candidates/{verb_id}")
async def delete_candidate(request: Request, verb_id: str) -> JSONResponse:
    require_admin_api(request)

    db = get_db()
    ref = db.collection(CANDIDATES_COLLECTION).document(verb_id)
    doc = ref.get()

    if not doc.exists:
        raise HTTPException(status_code=404, detail="Candidate not found")

    ref.delete()
    return JSONResponse({"deleted": verb_id})
