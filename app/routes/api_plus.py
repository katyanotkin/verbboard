from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.auth.firebase_auth import get_optional_auth_user
from core.i18n import SUPPORTED_UI_LANGS
from core.plus_request_service import get_request_status, is_requestable_language, request_plus
from core.rate_limit import SlidingWindowRateLimiter

logger = logging.getLogger(__name__)
router = APIRouter()

_PLUS_REQUEST_RATE_LIMITER = SlidingWindowRateLimiter(max_calls=20, window_seconds=600)
# Status reads happen on every page load, so they get their own, higher budget.
_PLUS_STATUS_RATE_LIMITER = SlidingWindowRateLimiter(max_calls=120, window_seconds=600)


def _error(status_code: int, code: str) -> JSONResponse:
    return JSONResponse({"ok": False, "error": code}, status_code=status_code)


@router.get("/api/plus/request")
def get_plus_request(request: Request, language: str = "") -> JSONResponse:
    user = get_optional_auth_user(request)
    if user is None:
        return _error(401, "signin")
    if not is_requestable_language(language):
        return _error(400, "language")
    if not _PLUS_STATUS_RATE_LIMITER.allow(user.uid):
        return _error(429, "rate_limited")
    try:
        status = get_request_status(user.uid, language)
    except Exception:
        logger.warning("plus request status read failed", exc_info=True)
        return _error(500, "failed")
    return JSONResponse({"requested": status is not None, "status": status})


@router.post("/api/plus/request")
async def post_plus_request(request: Request) -> JSONResponse:
    user = get_optional_auth_user(request)
    if user is None or not user.email:
        return _error(401, "signin")
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    language = str(body.get("language") or "")
    ui_language = str(body.get("ui_language") or "")
    if ui_language not in SUPPORTED_UI_LANGS:
        ui_language = ""
    if not is_requestable_language(language):
        return _error(400, "language")
    if not _PLUS_REQUEST_RATE_LIMITER.allow(user.uid):
        return _error(429, "rate_limited")
    try:
        created = request_plus(uid=user.uid, email=user.email, language=language, ui_language=ui_language)
    except Exception:
        logger.warning("plus request write failed", exc_info=True)
        return _error(500, "failed")
    return JSONResponse({"ok": True, "duplicate": not created})
