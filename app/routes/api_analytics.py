from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.analytics.session_tracker import _SID_COOKIE, attach_uid
from core.auth.firebase_auth import get_optional_auth_user

router = APIRouter()


@router.post("/api/analytics/session")
async def record_session_uid(request: Request) -> JSONResponse:
    user = get_optional_auth_user(request)
    if user is None:
        return JSONResponse({"ok": False}, status_code=401)

    sid = request.cookies.get(_SID_COOKIE)
    if not sid:
        return JSONResponse({"ok": False}, status_code=400)

    date = datetime.now(UTC).strftime("%Y-%m-%d")
    await attach_uid(sid, date, user.uid)
    return JSONResponse({"ok": True})
