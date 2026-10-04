from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.routes.admin_utils import ADMIN_PREFIX, require_admin_api, require_admin_page
from core.admin_report_service import build_report
from core.audio_report_service import list_open_audio_reports, resolve_audio_report

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/reports", response_class=HTMLResponse)
async def report_admin_page(request: Request) -> HTMLResponse:
    redirect_response = require_admin_page(request)
    if redirect_response is not None:
        return redirect_response

    today = datetime.now(UTC).date()
    return templates.TemplateResponse(
        request,
        "admin_report.html",
        {
            "admin_prefix": ADMIN_PREFIX,
            "default_date_to": today.isoformat(),
            "default_date_from": (today - timedelta(days=6)).isoformat(),
        },
    )


@router.get("/api/reports")
async def report_api(
    request: Request,
    date_from: str = Query(...),
    date_to: str = Query(...),
    compare: bool = Query(False),
) -> JSONResponse:
    require_admin_api(request)
    try:
        report = await asyncio.to_thread(build_report, date_from, date_to, compare)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return JSONResponse(report)


@router.get("/api/audio-reports")
async def audio_reports_api(request: Request) -> JSONResponse:
    require_admin_api(request)
    return JSONResponse({"reports": await asyncio.to_thread(list_open_audio_reports)})


@router.post("/api/audio-reports/{report_id}/resolve")
async def resolve_audio_report_api(request: Request, report_id: str) -> JSONResponse:
    require_admin_api(request)
    if not await asyncio.to_thread(resolve_audio_report, report_id):
        raise HTTPException(status_code=404, detail="Report not found")
    return JSONResponse({"ok": True})
