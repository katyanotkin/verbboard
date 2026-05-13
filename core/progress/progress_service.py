from __future__ import annotations

from core.auth.models import AuthUser
from core.progress.models import VerbProgress
from core.progress.progress_repository import (
    list_progress_for_language,
    mark_seen,
    set_known,
    upsert_user_profile,
)


def sync_user_profile(user: AuthUser) -> None:
    upsert_user_profile(
        user_id=user.uid,
        email=user.email,
        name=user.name,
        picture=user.picture,
    )


def record_seen(
    *,
    user: AuthUser,
    language: str,
    verb_id: str,
) -> None:
    sync_user_profile(user)
    mark_seen(user_id=user.uid, language=language, verb_id=verb_id)


def record_known(
    *,
    user: AuthUser,
    language: str,
    verb_id: str,
    known: bool,
) -> None:
    sync_user_profile(user)
    set_known(user_id=user.uid, language=language, verb_id=verb_id, known=known)


def get_language_progress(
    *,
    user: AuthUser,
    language: str,
) -> list[VerbProgress]:
    sync_user_profile(user)
    return list_progress_for_language(user_id=user.uid, language=language)
