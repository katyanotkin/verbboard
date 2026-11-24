from __future__ import annotations

import asyncio
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from app.routes.admin_utils import ADMIN_PREFIX, require_admin_api, require_admin_page
from core.persona_review_service import banner_text as persona_review_banner
from core.persona_review_service import get_open_review_detail, list_reviews, mark_done
from core.persona_snapshot_service import build_evolution, list_snapshots
from core.provider_health import admin_banner_text

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_REVIEW_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _build_personas_payload() -> dict:
    snapshots = list_snapshots()
    return {
        "open_review": get_open_review_detail(),
        "snapshot": snapshots[-1] if snapshots else None,
        "evolution": build_evolution(snapshots),
        "reviews": list_reviews(),
    }


@router.get("/personas", response_class=HTMLResponse)
async def personas_admin_page(request: Request) -> HTMLResponse:
    redirect_response = require_admin_page(request)
    if redirect_response is not None:
        return redirect_response

    return templates.TemplateResponse(
        request,
        "admin_personas.html",
        {
            "admin_prefix": ADMIN_PREFIX,
            "provider_banner": admin_banner_text(),
            "persona_banner": await asyncio.to_thread(persona_review_banner),
        },
    )


@router.get("/api/personas")
async def personas_api(request: Request) -> JSONResponse:
    require_admin_api(request)
    return JSONResponse(await asyncio.to_thread(_build_personas_payload))


@router.post("/api/personas/reviews/{review_date}/done")
async def personas_review_done(request: Request, review_date: str) -> JSONResponse:
    require_admin_api(request)
    if not _REVIEW_DATE.match(review_date):
        raise HTTPException(status_code=400, detail="Invalid review date")
    if not await asyncio.to_thread(mark_done, review_date):
        raise HTTPException(status_code=404, detail="Unknown review")
    return JSONResponse({"ok": True})
