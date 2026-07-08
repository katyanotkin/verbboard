from __future__ import annotations

from core.auth.models import AuthUser
from core.progress.models import PracticeProgress, VerbProgress
from core.progress.progress_repository import (
    get_practice_progress,
    list_progress_for_language,
    mark_seen,
    save_practice_progress,
    set_known,
    upsert_user_profile,
)
from core.progress.streak import StreakRecord


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

    set_known(
        user_id=user.uid,
        language=language,
        verb_id=verb_id,
        known=known,
    )


def get_language_progress(
    *,
    user: AuthUser,
    language: str,
) -> list[VerbProgress]:
    sync_user_profile(user)

    return list_progress_for_language(
        user_id=user.uid,
        language=language,
    )


def load_practice_progress(
    *,
    user: AuthUser,
    language: str,
) -> PracticeProgress:
    sync_user_profile(user)

    return get_practice_progress(
        user_id=user.uid,
        language=language,
    )


def record_practice_progress(
    *,
    user: AuthUser,
    language: str,
    badges: list[int],
    streak_last_day: str | None = None,
    streak_len: int | None = None,
) -> StreakRecord | None:
    sync_user_profile(user)

    return save_practice_progress(
        user_id=user.uid,
        language=language,
        badges=badges,
        streak_last_day=streak_last_day,
        streak_len=streak_len,
    )
