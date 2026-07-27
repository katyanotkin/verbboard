from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from core.auth.firebase_auth import get_optional_auth_user
from core.editions import is_study_language
from core.languages.config import UI_LANGUAGES
from core.progress.models import PracticeSessionSize
from core.progress.progress_repository import (
    get_preferences,
    set_preferences,
)

router = APIRouter(prefix="/api/preferences")

_VALID_UI_LANGUAGES = set(UI_LANGUAGES)


_VALID_MIN_PLAYS = {1, 3, 5, 8, "all"}


class PreferencesPayload(BaseModel):
    ui_language: str | None = None
    learning_language: str | None = None
    practice_session_size: int | None = None
    practice_min_plays: int | str | None = None


def _require_user(request: Request):
    user = get_optional_auth_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("")
def get_prefs(request: Request):
    user = _require_user(request)
    return get_preferences(user_id=user.uid)


@router.post("")
def set_prefs(request: Request, payload: PreferencesPayload):
    user = _require_user(request)
    if payload.ui_language is not None and payload.ui_language not in _VALID_UI_LANGUAGES:
        raise HTTPException(status_code=422, detail="Invalid ui_language")
    if payload.learning_language is not None and not is_study_language(payload.learning_language):
        raise HTTPException(status_code=422, detail="Invalid learning_language")
    if payload.practice_session_size is not None and not any(
        payload.practice_session_size == s for s in PracticeSessionSize
    ):
        raise HTTPException(status_code=422, detail="Invalid practice_session_size")
    if payload.practice_min_plays is not None and payload.practice_min_plays not in _VALID_MIN_PLAYS:
        raise HTTPException(status_code=422, detail="Invalid practice_min_plays")
    set_preferences(user_id=user.uid, prefs=payload.model_dump(exclude_none=True))
    return {"ok": True}
