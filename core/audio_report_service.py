"""Audio problem reports (issue #71): a signed-in learner flags one clip on /learn.

Two collections. `audio_report_votes/{uid}_{hash}` is the per-user dedupe marker
and is the only place a uid is stored. `audio_reports/{language}_{verb_id}_{voice}_{form_key}`
is the aggregate the admin sees (counts, reason breakdown, a few comments, status),
with no uid. The exact TTS text is resolved server-side from the verb's board, never
taken from the client.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from google.api_core.exceptions import AlreadyExists
from google.cloud import firestore

from core.audio_service import find_clip_text
from core.languages.config import ALL_STUDY_LANGUAGES, UI_LANGUAGES
from core.rate_limit import SlidingWindowRateLimiter
from core.storage.firestore_db import get_db
from core.tts import VOICES

VOTES_COLLECTION = "audio_report_votes"
REPORTS_COLLECTION = "audio_reports"

VALID_VOICES = ("female", "male")
VALID_REASONS = ("wrong_form", "stress", "glitch", "other")
MAX_COMMENT_LENGTH = 200
MAX_OPEN_REPORTS_LISTED = 500
MAX_COMMENTS_STORED = 5
_MAX_ID_LENGTH = 80

# Per-uid soft limit (per Cloud Run instance, like core/rate_limit.py's other users).
_rate_limiter = SlidingWindowRateLimiter(max_calls=20, window_seconds=600)
# Reads are cheap and happen once per /learn page load, so the cap is far more generous.
_mine_rate_limiter = SlidingWindowRateLimiter(max_calls=120, window_seconds=600)


class AudioReportError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def clean_comment(comment: str | None) -> str:
    """Plain text only: control characters become spaces, whitespace collapses, 200 chars max."""
    if not comment:
        return ""
    printable = "".join(ch if ch.isprintable() else " " for ch in comment)
    return " ".join(printable.split())[:MAX_COMMENT_LENGTH]


def _report_doc_id(language: str, verb_id: str, voice: str, form_key: str) -> str:
    return f"{language}_{verb_id}_{voice}_{form_key}"


def _vote_doc_id(uid: str, language: str, verb_id: str, voice: str, form_key: str) -> str:
    digest = hashlib.sha1(f"{language}|{verb_id}|{voice}|{form_key}".encode()).hexdigest()[:16]
    return f"{uid}_{digest}"


def _load_board(language: str, verb_id: str, voice: str):
    from core.registry import get as get_plugin
    from core.verb_loader import load_entry_by_id

    verb = load_entry_by_id(language=language, verb_id=verb_id)
    if verb is None:
        return None
    return get_plugin(language).build_board(verb, voice, VOICES[language][voice].label)


def submit_audio_report(
    *,
    uid: str,
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
    reason: str,
    comment: str | None,
    ui_language: str | None,
) -> dict[str, Any]:
    if language not in ALL_STUDY_LANGUAGES or language not in VOICES:
        raise AudioReportError(400, "Unknown language")
    if voice not in VALID_VOICES or voice not in VOICES[language]:
        raise AudioReportError(400, "Unknown voice")
    if reason not in VALID_REASONS:
        raise AudioReportError(400, "Unknown reason")
    if not (1 <= len(verb_id) <= _MAX_ID_LENGTH) or not (1 <= len(form_key) <= _MAX_ID_LENGTH):
        raise AudioReportError(400, "Invalid clip")
    if "/" in verb_id or "/" in form_key:
        raise AudioReportError(400, "Invalid clip")

    if not _rate_limiter.allow(uid):
        raise AudioReportError(429, "Too many reports")

    board = _load_board(language, verb_id, voice)
    clip = find_clip_text(board, form_key) if board is not None else None
    if clip is None:
        raise AudioReportError(404, "Clip not found")
    text, row_kind = clip

    db = get_db()
    vote_ref = db.collection(VOTES_COLLECTION).document(_vote_doc_id(uid, language, verb_id, voice, form_key))
    now = datetime.now(UTC)
    try:
        vote_ref.create(
            {"uid": uid, "language": language, "verb_id": verb_id, "voice": voice, "form_key": form_key, "at": now}
        )
    except AlreadyExists:
        return {"ok": True, "duplicate": True}

    try:
        report_ref = db.collection(REPORTS_COLLECTION).document(_report_doc_id(language, verb_id, voice, form_key))
        existing = report_ref.get().to_dict()
        payload: dict[str, Any] = {
            "language": language,
            "verb_id": verb_id,
            "voice": voice,
            "form_key": form_key,
            "text": text,
            "row_kind": row_kind,
            "count": firestore.Increment(1),
            "reasons": {reason: firestore.Increment(1)},
            "last_at": now,
            "status": "open",
        }
        if ui_language in UI_LANGUAGES:
            payload["ui_langs"] = {ui_language: firestore.Increment(1)}
        if existing is None:
            payload["first_at"] = now
        cleaned_comment = clean_comment(comment)
        if cleaned_comment and len((existing or {}).get("comments") or []) < MAX_COMMENTS_STORED:
            payload["comments"] = firestore.ArrayUnion([cleaned_comment])
        report_ref.set(payload, merge=True)
    except Exception:
        # The vote doc was created first; release it so the user's retry is not reported as a duplicate.
        vote_ref.delete()
        raise
    return {"ok": True, "duplicate": False}


async def submit_audio_report_async(**kwargs: Any) -> dict[str, Any]:
    return await asyncio.to_thread(submit_audio_report, **kwargs)


def mine_for_verb(uid: str, language: str, verb_id: str) -> list[dict[str, str]]:
    """Clips on this verb that `uid` has already reported (both voices).

    One equality query on the vote docs (uid, language, verb_id): it reads only real votes, needs no
    composite index, and can only return this uid's own rows. Votes written before the `uid` field
    existed are not returned.
    """
    if language not in ALL_STUDY_LANGUAGES or language not in VOICES:
        raise AudioReportError(400, "Unknown language")
    if not (1 <= len(verb_id) <= _MAX_ID_LENGTH) or "/" in verb_id:
        raise AudioReportError(400, "Invalid verb")
    if not _mine_rate_limiter.allow(uid):
        raise AudioReportError(429, "Too many requests")

    votes = (
        get_db()
        .collection(VOTES_COLLECTION)
        .where("uid", "==", uid)
        .where("language", "==", language)
        .where("verb_id", "==", verb_id)
        .stream()
    )
    reported: list[dict[str, str]] = []
    for snapshot in votes:
        data = snapshot.to_dict() or {}
        voice, form_key = str(data.get("voice", "")), str(data.get("form_key", ""))
        if voice in VALID_VOICES and form_key:
            reported.append({"voice": voice, "form_key": form_key})
    return reported


async def mine_for_verb_async(**kwargs: Any) -> list[dict[str, str]]:
    return await asyncio.to_thread(mine_for_verb, **kwargs)


# ── admin view ────────────────────────────────────────────────────────────────


def _iso(value: Any) -> str:
    return value.isoformat() if isinstance(value, datetime) else ""


def list_open_audio_reports() -> list[dict[str, Any]]:
    """Open reports, most-reported first. Sorted here (not by Firestore) to avoid a composite index."""
    snapshots = (
        get_db().collection(REPORTS_COLLECTION).where("status", "==", "open").limit(MAX_OPEN_REPORTS_LISTED).stream()
    )
    rows: list[dict[str, Any]] = []
    for snapshot in snapshots:
        data = snapshot.to_dict() or {}
        language = str(data.get("language", ""))
        verb_id = str(data.get("verb_id", ""))
        voice = str(data.get("voice", ""))
        rows.append(
            {
                "id": snapshot.id,
                "language": language,
                "verb_id": verb_id,
                "voice": voice,
                "text": str(data.get("text", "")),
                "row_kind": str(data.get("row_kind", "")),
                "count": int(data.get("count", 0) or 0),
                "reasons": dict(data.get("reasons") or {}),
                "comments": [str(c) for c in (data.get("comments") or [])],
                "last_at": _iso(data.get("last_at")),
                "learn_url": "/learn?"
                + urlencode({"language": language, "verb_id": verb_id, "voice": voice, "ui_language": "en"}),
            }
        )
    rows.sort(key=lambda row: row["last_at"], reverse=True)
    rows.sort(key=lambda row: row["count"], reverse=True)  # stable: ties stay newest first
    return rows


def resolve_audio_report(report_id: str) -> bool:
    """Mark a report resolved and release the users' votes for that clip.

    Releasing the votes lets a user report the clip again if it is still wrong (a new report reopens it)
    and clears their "reported" flag on their next page load. The counters restart from zero so the admin
    ranking reflects only reports made after the fix; the old total is kept as `resolved_count`.
    """
    if not report_id or "/" in report_id:
        return False
    db = get_db()
    ref = db.collection(REPORTS_COLLECTION).document(report_id)
    snapshot = ref.get()
    if not snapshot.exists:
        return False
    data = snapshot.to_dict() or {}
    votes = (
        db.collection(VOTES_COLLECTION)
        .where("language", "==", data.get("language"))
        .where("verb_id", "==", data.get("verb_id"))
        .where("voice", "==", data.get("voice"))
        .where("form_key", "==", data.get("form_key"))
        .stream()
    )
    for vote in votes:
        vote.reference.delete()
    ref.update(
        {
            "status": "resolved",
            "resolved_at": datetime.now(UTC),
            "resolved_count": int(data.get("count", 0) or 0),
            "count": 0,
            "reasons": {},
            "ui_langs": {},
            "comments": [],
        }
    )
    return True
