from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from core.auth.firebase_auth import get_optional_auth_user
from core.languages.config import ALL_STUDY_LANGUAGES
from core.progress.progress_service import (
    get_language_progress,
    load_practice_progress,
    record_fill_practice_session,
    record_known,
    record_known_batch,
    record_practice_progress,
    record_review_result,
    record_seen,
)
from core.rate_limit import SlidingWindowRateLimiter
from core.rate_nudge_service import MAX_COUNT, sync_rate_nudge

router = APIRouter(prefix="/api/progress")

_VALID_BADGE_SIZES = {3, 6, 9}
_MAX_FILL_ANSWERS = 200
_FILL_SESSION_RATE_LIMITER = SlidingWindowRateLimiter(max_calls=60, window_seconds=600)
_RATE_NUDGE_RATE_LIMITER = SlidingWindowRateLimiter(max_calls=60, window_seconds=600)


class SeenRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=80)


class KnownRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=80)
    known: bool


class KnownBatchRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_ids: list[str] = Field(min_length=1, max_length=2000)

    @field_validator("verb_ids")
    @classmethod
    def verb_ids_must_be_reasonable(cls, v: list[str]) -> list[str]:
        for verb_id in v:
            if not (1 <= len(verb_id) <= 80):
                raise ValueError("each verb_id must be 1-80 characters")
        return v


class ReviewRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=80)
    recalled: bool


class PracticeProgressRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    badges: list[int]

    @field_validator("badges")
    @classmethod
    def badges_must_be_valid_sizes(cls, v: list[int]) -> list[int]:
        invalid = [b for b in v if b not in _VALID_BADGE_SIZES]
        if invalid:
            raise ValueError(f"badges contains invalid sizes {invalid}; allowed: {sorted(_VALID_BADGE_SIZES)}")
        return v


class RateNudgeRequest(BaseModel):
    # Absolute values (never increments). Range checks live in the handler so bad bodies answer 400.
    votd_opens: int
    votd_opens_at_last_ask: int
    completed: int
    asks: int
    last_at: int
    tapped: bool


class FillSessionRequest(BaseModel):
    # Range checks live in the handler so a bad body answers 400 like the language check.
    language: str = Field(max_length=16)
    answers: int
    correct: int
    completed: bool
    # "practice" = a /practice/fill round; "inline" = answers typed into /learn's fill mode
    # (adds answers/correct only; no started/completed counts).
    mode: Literal["practice", "inline"] = "practice"


def _require_user(request: Request):
    user = get_optional_auth_user(request)

    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    return user


@router.get("")
def get_progress(
    request: Request,
    language: str = Query(..., min_length=2, max_length=3),
):
    user = _require_user(request)

    rows = get_language_progress(
        user=user,
        language=language,
    )

    return {
        "verbs": {
            row.verb_id: {
                "seen": row.seen,
                "known": row.known,
                **(
                    {
                        "srs_box": row.srs_box,
                        "srs_due_at": row.srs_due_at.isoformat() if row.srs_due_at else None,
                        "srs_reviewed_at": row.srs_reviewed_at.isoformat() if row.srs_reviewed_at else None,
                    }
                    if row.srs_box
                    else {}
                ),
            }
            for row in rows
        }
    }


@router.get("/practice")
def get_practice_progress_route(
    request: Request,
    language: str = Query(..., min_length=2, max_length=3),
):
    user = _require_user(request)

    progress = load_practice_progress(
        user=user,
        language=language,
    )

    return {
        "badges": progress.badges,
    }


@router.post("/seen")
def mark_progress_seen(
    request: Request,
    payload: SeenRequest,
):
    user = _require_user(request)

    record_seen(
        user=user,
        language=payload.language,
        verb_id=payload.verb_id,
    )

    return {"ok": True}


@router.post("/known")
def set_progress_known(
    request: Request,
    payload: KnownRequest,
):
    user = _require_user(request)

    record_known(
        user=user,
        language=payload.language,
        verb_id=payload.verb_id,
        known=payload.known,
    )

    return {"ok": True}


@router.post("/known/batch")
def set_progress_known_batch(
    request: Request,
    payload: KnownBatchRequest,
):
    user = _require_user(request)

    record_known_batch(
        user=user,
        language=payload.language,
        verb_ids=payload.verb_ids,
    )

    return {"ok": True, "count": len(payload.verb_ids)}


@router.post("/review")
def record_progress_review(
    request: Request,
    payload: ReviewRequest,
):
    user = _require_user(request)

    result = record_review_result(
        user=user,
        language=payload.language,
        verb_id=payload.verb_id,
        recalled=payload.recalled,
    )

    return {
        "box": result["box"],
        "due_at": result["due_at"].isoformat(),
    }


@router.post("/practice")
def set_practice_progress(
    request: Request,
    payload: PracticeProgressRequest,
):
    user = _require_user(request)

    record_practice_progress(
        user=user,
        language=payload.language,
        badges=payload.badges,
    )

    return {"ok": True}


@router.post("/fill_session")
def post_fill_session(
    request: Request,
    payload: FillSessionRequest,
):
    user = _require_user(request)

    if payload.language not in ALL_STUDY_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unknown language")
    if not 0 <= payload.correct <= payload.answers <= _MAX_FILL_ANSWERS:
        raise HTTPException(status_code=400, detail="Invalid answer counts")
    if not _FILL_SESSION_RATE_LIMITER.allow(user.uid):
        raise HTTPException(status_code=429, detail="Too many requests")

    record_fill_practice_session(
        user=user,
        language=payload.language,
        answers=payload.answers,
        correct=payload.correct,
        completed=payload.completed,
        inline=payload.mode == "inline",
    )

    return {"ok": True}


@router.post("/rate_nudge")
def post_rate_nudge(
    request: Request,
    payload: RateNudgeRequest,
):
    user = _require_user(request)

    counts = (payload.votd_opens, payload.votd_opens_at_last_ask, payload.completed, payload.asks)
    if not all(0 <= value <= MAX_COUNT for value in counts):
        raise HTTPException(status_code=400, detail="Invalid rate nudge counts")
    if payload.last_at < 0:
        raise HTTPException(status_code=400, detail="Invalid rate nudge timestamp")
    if not _RATE_NUDGE_RATE_LIMITER.allow(user.uid):
        raise HTTPException(status_code=429, detail="Too many requests")

    return sync_rate_nudge(user.uid, payload.model_dump())
