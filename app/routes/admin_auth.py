from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.admin_auth import (
    ADMIN_SESSION_COOKIE,
    ADMIN_SESSION_MAX_AGE_SECONDS,
    create_admin_session_token,
    verify_admin_password,
)
from core.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter()
settings = load_settings()
ADMIN_PREFIX = "/admin"
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
async def admin_login_page(request: Request, error: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        "admin_login.html",
        {"request": request, "admin_prefix": ADMIN_PREFIX, "error": error == "1"},
    )


@router.post("/login")
async def admin_login(password: str = Form(...)) -> HTMLResponse:
    if not verify_admin_password(password):
        return RedirectResponse(url=f"{ADMIN_PREFIX}/login?error=1", status_code=303)

    token = create_admin_session_token()
    response = HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}/login-callback');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        status_code=200,
    )
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        path="/",
    )
    return response


@router.get("/login-callback")
async def admin_login_callback() -> HTMLResponse:
    return HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store"},
        status_code=200,
    )


@router.post("/logout")
async def admin_logout() -> HTMLResponse:
    response = HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}/login');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store"},
        status_code=200,
    )
    response.delete_cookie(
        key=ADMIN_SESSION_COOKIE, path="/", secure=True, samesite="lax"
    )
    return response
