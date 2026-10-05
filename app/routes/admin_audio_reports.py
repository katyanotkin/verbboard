from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.routes.admin_utils import ADMIN_PREFIX, require_admin_api, require_admin_page
from core.audio_report_service import (
    REPORT_STATUSES,
    ReportTransitionError,
    list_audio_reports,
    transition_audio_report,
)
from core.languages.config import ALL_STUDY_LANGUAGES

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_ACTIONS = ("confirm", "unconfirm", "resolve")


@router.get("/audio-reports", response_class=HTMLResponse)
async def audio_reports_page(request: Request) -> HTMLResponse:
    redirect_response = require_admin_page(request)
    if redirect_response is not None:
        return redirect_response
    return templates.TemplateResponse(
        request,
        "admin_audio_reports.html",
        {"admin_prefix": ADMIN_PREFIX, "languages": list(ALL_STUDY_LANGUAGES)},
    )


@router.get("/api/audio-reports")
async def audio_reports_api(request: Request, status: str = Query("open"), language: str = Query("")) -> JSONResponse:
    require_admin_api(request)
    if status not in REPORT_STATUSES:
        raise HTTPException(status_code=400, detail="Unknown status")
    if language and language not in ALL_STUDY_LANGUAGES:
        raise HTTPException(status_code=400, detail="Unknown language")
    return JSONResponse({"reports": await asyncio.to_thread(list_audio_reports, status, language)})


@router.post("/api/audio-reports/{report_id}/{action}")
async def audio_report_action_api(request: Request, report_id: str, action: str) -> JSONResponse:
    require_admin_api(request)
    if action not in _ACTIONS:
        raise HTTPException(status_code=404, detail="Unknown action")
    try:
        await asyncio.to_thread(transition_audio_report, report_id, action)
    except ReportTransitionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return JSONResponse({"ok": True})
