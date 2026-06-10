from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.analytics.session_tracker import attach_uid, get_fingerprint_sid
from core.auth.firebase_auth import get_optional_auth_user

router = APIRouter()


@router.post("/api/analytics/session")
async def record_session_uid(request: Request) -> JSONResponse:
    user = get_optional_auth_user(request)
    if user is None:
        return JSONResponse({"ok": False}, status_code=401)

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    fingerprint = get_fingerprint_sid(request, date)
    await attach_uid(fingerprint, date, user.uid)
    return JSONResponse({"ok": True})
