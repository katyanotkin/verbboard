from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from core.admin_auth import update_session_claims
from core.analytics.daily_counters import _clean_lang, _clean_ui_lang
from core.analytics.session_tracker import (
    attach_uid,
    enrich_lang,
    get_fingerprint_sid,
    record_practice_completed,
    record_practice_gate_shown,
    record_practice_started,
    record_sign_in_tap,
    record_ui_lang_selected,
    record_votd_clicked,
)
from core.auth.firebase_auth import get_optional_auth_user

router = APIRouter()

_VALID_PRACTICE_EVENTS = {"started", "completed", "gate_shown"}


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


@router.post("/api/analytics/sign_in_tapped")
async def record_sign_in_tapped(request: Request) -> JSONResponse:
    """Diagnostic-only: records which signIn() branch (standalone/mobile/desktop)
    a user tapped, to help issue #28 check whether sign-in friction differs by
    branch. No auth required (fired at the moment of tapping sign-in, before
    any credential exists) -- same unauthenticated, fail-open shape as /enrich."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    branch = str(body.get("branch") or "")
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    fingerprint = get_fingerprint_sid(request, date)
    await record_sign_in_tap(fingerprint, date, branch)
    return JSONResponse({"ok": True})


@router.post("/api/analytics/practice_event")
async def record_practice_event(request: Request) -> JSONResponse:
    """Diagnostic-only (issue #48): auth-independent practice engagement signal
    on analytics_sessions. practice_loop.js is localStorage-first with no auth
    gate, so the uid-keyed user_practice collection misses the ~99.6% of
    sessions that never sign in. No auth required, same unauthenticated,
    fail-open shape as /enrich and /sign_in_tapped."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    event = str(body.get("event") or "")
    if event not in _VALID_PRACTICE_EVENTS:
        return JSONResponse({"ok": False})
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    fingerprint = get_fingerprint_sid(request, date)
    if event == "started":
        await record_practice_started(fingerprint, date)
    elif event == "gate_shown":
        await record_practice_gate_shown(fingerprint, date)
    else:
        await record_practice_completed(fingerprint, date)
    return JSONResponse({"ok": True})


@router.post("/api/analytics/votd_clicked")
async def record_votd_click(request: Request) -> JSONResponse:
    """Diagnostic-only: the visitor clicked the Verb of the Day hero on the home
    page. No auth and no body -- same unauthenticated, fail-open shape as
    /practice_event; the click is attributed to the day's fingerprint session."""
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    fingerprint = get_fingerprint_sid(request, date)
    await record_votd_clicked(fingerprint, date)
    return JSONResponse({"ok": True})


@router.post("/api/analytics/ui_lang_selected")
async def record_ui_lang_selection(request: Request) -> JSONResponse:
    """Diagnostic-only: the visitor picked a UI language in the dropdown. No auth,
    fail-open, same shape as /votd_clicked; the value is validated against the
    UI-language allowlist server-side."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    fingerprint = get_fingerprint_sid(request, date)
    await record_ui_lang_selected(fingerprint, date, str(body.get("ui_lang") or ""))
    return JSONResponse({"ok": True})


@router.post("/api/analytics/enrich")
async def enrich_session(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)
    if not isinstance(body, dict):
        return JSONResponse({"ok": False}, status_code=400)
    language = _clean_lang(str(body.get("language") or ""))
    ui_lang = _clean_ui_lang(str(body.get("ui_lang") or ""))
    if not language and not ui_lang:
        return JSONResponse({"ok": False})
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    fingerprint = get_fingerprint_sid(request, date)
    await enrich_lang(fingerprint, date, language, ui_lang)
    return JSONResponse({"ok": True})
