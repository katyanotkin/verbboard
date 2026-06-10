from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.routes.admin_auth import router as admin_auth_router
from app.routes.admin_candidates import router as admin_candidates_router
from app.routes.admin_feedback import router as admin_feedback_router
from app.routes.admin_signals import router as admin_signals_router
from app.routes.admin_utils import ADMIN_PREFIX, require_admin_page

templates = Jinja2Templates(directory="app/templates")

logger = logging.getLogger(__name__)

router = APIRouter(prefix=ADMIN_PREFIX)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    redirect_response = require_admin_page(request)
    if redirect_response is not None:
        return redirect_response

    return templates.TemplateResponse(
        "admin.html", {"request": request, "admin_prefix": ADMIN_PREFIX}
    )


router.include_router(admin_auth_router)
router.include_router(admin_feedback_router)
router.include_router(admin_signals_router)
router.include_router(admin_candidates_router)
