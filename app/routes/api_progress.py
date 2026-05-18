from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from core.auth.firebase_auth import get_optional_auth_user
from core.progress.progress_service import (
    get_language_progress,
    load_practice_progress,
    record_known,
    record_practice_progress,
    record_seen,
)

router = APIRouter(prefix="/api/progress")

_VALID_BADGE_SIZES = {3, 6, 9}


class SeenRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=120)


class KnownRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=120)
    known: bool


class PracticeProgressRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    badges: list[int]

    @field_validator("badges")
    @classmethod
    def badges_must_be_valid_sizes(cls, v: list[int]) -> list[int]:
        invalid = [b for b in v if b not in _VALID_BADGE_SIZES]
        if invalid:
            raise ValueError(
                f"badges contains invalid sizes {invalid}; "
                f"allowed: {sorted(_VALID_BADGE_SIZES)}"
            )
        return v


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
