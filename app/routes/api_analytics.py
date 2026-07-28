from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.admin_auth import update_session_claims
from core.analytics.daily_counters import _clean_lang
from core.analytics.session_tracker import attach_uid, enrich_lang, get_fingerprint_sid
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

    response = JSONResponse({"ok": True})
    # Identifies this signed-in user's uid on plain page-load GETs (a browser
    # navigation never sends the Authorization: Bearer header). Merge, not
    # clobber: an admin "role" claim already on __session (site owner also
    # logged into /admin) must survive this write.
    update_session_claims(request, response, uid=user.uid)
    return response


@router.post("/api/analytics/session/clear")
async def clear_session_uid(request: Request) -> JSONResponse:
    """Remove the uid claim from __session on sign-out. Preserves an admin
    "role" claim, if present -- signing out of the regular-user session must
    not log the site owner out of /admin."""
    response = JSONResponse({"ok": True})
    update_session_claims(request, response, uid=None)
    return response


@router.post("/api/analytics/enrich")
async def enrich_session(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)
    language = _clean_lang(str(body.get("language") or ""))
    ui_lang = _clean_lang(str(body.get("ui_lang") or ""))
    if not language and not ui_lang:
        return JSONResponse({"ok": False})
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    fingerprint = get_fingerprint_sid(request, date)
    await enrich_lang(fingerprint, date, language, ui_lang)
    return JSONResponse({"ok": True})
