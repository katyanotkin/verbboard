from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.routes.admin_candidates import router as admin_candidates_router
from app.routes.admin_feedback import router as admin_feedback_router
from app.routes.admin_signals import router as admin_signals_router
from app.routes.admin_utils import ADMIN_PREFIX, TEMPLATES_DIR

router = APIRouter(prefix=ADMIN_PREFIX)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def admin_page(request: Request) -> HTMLResponse:
    html = (TEMPLATES_DIR / "admin.html").read_text(encoding="utf-8")
    html = html.replace("__ADMIN_ROOT__", ADMIN_PREFIX)
    return HTMLResponse(content=html)


router.include_router(admin_feedback_router)
router.include_router(admin_signals_router)
router.include_router(admin_candidates_router)
