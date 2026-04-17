from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import anthropic
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse

from core.settings import load_settings
from core.storage.firestore_db import get_db

_SETTINGS = load_settings()
_ADMIN_SECRET = _SETTINGS.admin_secret
_TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

VERBS_COLLECTION = "verbs"
CANDIDATES_COLLECTION = "verb_candidates"

CANDIDATE_STATUSES = {"needs_generation", "pending", "to_be_fixed", "promoted"}

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
    return _SETTINGS.verb_signals_collection, _SETTINGS.verb_signal_labels_collection


@router.get("/api/signals")
async def list_signals(
    language: str | None = None,
    include_processed: bool = False,
    status: str | None = None,
    sort_by: str = "ts",
    sort_dir: str = "desc",
) -> JSONResponse:
    db = get_db()
    sig_col, _ = _cols()

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

    # When marked as candidate, create a stub in verb_candidates (needs_generation)
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
    sig_col, lbl_col = _cols()

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
    sig_col, lbl_col = _cols()

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


# ---------------------------------------------------------------------------
# Verb candidates
# ---------------------------------------------------------------------------

_GENERATION_SYSTEM_PROMPT = """\
You are a linguistic data generator for a language-learning app.
You receive a raw search query (which may be any inflected form, e.g. "went", "growing", "был")
and a language code. First identify the dictionary lemma, then generate full conjugation data.
Output ONLY a valid JSON object — no markdown, no backticks, no explanation.

Output shape:
{
  "lemma": "<dictionary base form>",
  "forms": { <conjugated forms — see rules below> },
  "examples": [ {"dst": "<sentence>"}, ... ],
  "search_extract": [ "<form1>", "<form2>", ... ]
}

ENGLISH (en):
  lemma: infinitive base form (e.g. "went" → "go", "growing" → "grow")
  forms keys: base, past, past_participle, present_3sg, gerund
  examples: exactly 5 sentences:
    1. simple present first person  e.g. "I grow vegetables at home."
    2. simple present third person  e.g. "She grows tomatoes every year."
    3. simple past                  e.g. "They grew up in a small town."
    4. present perfect              e.g. "He has grown a lot this year."
    5. present continuous           e.g. "We are growing herbs on the balcony."

RUSSIAN (ru):
  lemma: infinitive form (e.g. "шёл" → "идти")
  forms keys: infinitive, present_1sg, present_2sg, present_3sg,
              present_1pl, present_2pl, present_3pl,
              past_m, past_f, past_n, past_pl,
              imperative_sg, imperative_pl, aspect, pair
  examples: 5 sentences in Russian covering same tenses

SPANISH (es):
  lemma: infinitive form (e.g. "fui" → "ir")
  forms keys: infinitive, present_yo, present_tu, present_el,
              present_nosotros, present_vosotros, present_ellos,
              preterite_yo, preterite_el, preterite_nosotros,
              imperfect_yo, future_yo, gerund, past_participle
  examples: 5 sentences in Spanish covering same tenses

HEBREW (he):
  lemma: infinitive form
  forms keys: infinitive, present_ms, present_fs, present_mp, present_fp,
              past_1sg, past_3ms, past_3fs, past_3pl,
              future_1sg, future_3ms, future_3fs, future_3pl,
              imperative_ms, imperative_fs, binyan
  examples: 5 sentences in Hebrew script covering same tenses

search_extract: deduplicated flat list of all unique surface form strings.
"""


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


def _find_in_set(language: str, query: str) -> str | None:
    """Return verb_id if query matches any search_extract in the live verbs collection."""
    db = get_db()
    docs = db.collection(VERBS_COLLECTION).where("language", "==", language).stream()
    q = query.strip().casefold()
    for doc in docs:
        data = doc.to_dict()
        for term in data.get("search_extract") or []:
            if isinstance(term, str) and term.casefold() == q:
                return data.get("verb_id", doc.id)
    return None


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
    results.sort(key=lambda r: (r["language"], r["query"]))
    return JSONResponse({"candidates": results})


def _call_claude(language: str, query: str) -> dict[str, Any]:
    """Call Claude to identify lemma + generate forms/examples for a raw query."""
    from core.settings import _load_anthropic_api_key

    api_key = _load_anthropic_api_key()
    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
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
        raise HTTPException(
            status_code=502,
            detail=f"Generation returned invalid JSON for '{query}': {raw[:200]}",
        ) from exc


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

    # Check if query already exists in live verbs
    in_set_id = _find_in_set(language, query)
    if in_set_id:
        raise HTTPException(
            status_code=409,
            detail=f"'{query}' is already in the live verb set as '{in_set_id}'",
        )

    generated = _call_claude(language, query)
    lemma = generated.get("lemma") or query
    new_id = f"{language}_{lemma}"
    now = datetime.now(UTC).isoformat()

    # Check if resolved lemma already exists in live verbs
    if new_id != verb_id:
        existing_verb = db.collection(VERBS_COLLECTION).document(new_id).get()
        if existing_verb.exists:
            raise HTTPException(
                status_code=409,
                detail=f"Resolves to '{new_id}' which already exists in live verbs",
            )
        # Check if another candidate already has this lemma
        existing_cand = db.collection(CANDIDATES_COLLECTION).document(new_id).get()
        if existing_cand.exists:
            raise HTTPException(
                status_code=409,
                detail=f"Resolves to '{new_id}' which already exists as a candidate",
            )

    rank = _get_max_rank(language) + 1

    updated = {
        **data,
        "verb_id": new_id,
        "lemma": lemma,
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
        raise HTTPException(
            status_code=409,
            detail=f"'{verb_id}' already exists in the verbs collection",
        )

    now = datetime.now(UTC).isoformat()
    verb_doc = {k: v for k, v in data.items() if k != "status"}
    verb_doc["created_at"] = now
    verb_doc["updated_at"] = now

    db.collection(VERBS_COLLECTION).document(verb_id).set(verb_doc)
    candidate_ref.update({"status": "promoted", "updated_at": now})

    return JSONResponse(
        {"verb_id": verb_id, "promoted": True, "rank": data.get("rank")}
    )
