from __future__ import annotations

import re
from datetime import date

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator, model_validator

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
_ISO_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class SeenRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=80)


class KnownRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=80)
    known: bool


class PracticeProgressRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    badges: list[int]
    streak_last_day: str | None = Field(default=None, min_length=10, max_length=10)
    streak_len: int | None = Field(default=None, ge=1, le=36600)

    @field_validator("badges")
    @classmethod
    def badges_must_be_valid_sizes(cls, v: list[int]) -> list[int]:
        invalid = [b for b in v if b not in _VALID_BADGE_SIZES]
        if invalid:
            raise ValueError(f"badges contains invalid sizes {invalid}; allowed: {sorted(_VALID_BADGE_SIZES)}")
        return v

    @field_validator("streak_last_day")
    @classmethod
    def streak_last_day_must_be_valid_iso_date(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _ISO_DAY_RE.match(v):
            raise ValueError("streak_last_day must match YYYY-MM-DD")
        try:
            date.fromisoformat(v)
        except ValueError as exc:
            raise ValueError("streak_last_day must be a valid calendar date") from exc
        return v

    @model_validator(mode="after")
    def streak_fields_both_or_neither(self) -> "PracticeProgressRequest":
        if (self.streak_last_day is None) != (self.streak_len is None):
            raise ValueError("streak_last_day and streak_len must both be provided or both omitted")
        return self


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

    streak = (
        {"last_day": progress.streak_last_day, "len": progress.streak_len}
        if progress.streak_last_day and progress.streak_len
        else None
    )

    return {
        "badges": progress.badges,
        "streak": streak,
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

    stored_streak = record_practice_progress(
        user=user,
        language=payload.language,
        badges=payload.badges,
        streak_last_day=payload.streak_last_day,
        streak_len=payload.streak_len,
    )

    streak = {"last_day": stored_streak["last_day"], "len": stored_streak["len"]} if stored_streak else None

    return {"ok": True, "streak": streak}
