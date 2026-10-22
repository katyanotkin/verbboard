from __future__ import annotations

import logging

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from core.admin_auth import (
    update_session_claims,
    verify_admin_password,
)
from core.rate_limit import SlidingWindowRateLimiter, client_ip
from core.settings import load_settings

logger = logging.getLogger(__name__)

router = APIRouter()
settings = load_settings()
ADMIN_PREFIX = "/admin"
# Brute-force guard for the shared admin password: 5 attempts / 10 min per client IP
# (per Cloud Run instance, best effort). Every attempt counts, successful or not.
_LOGIN_LIMITER = SlidingWindowRateLimiter(max_calls=5, window_seconds=600)
templates = Jinja2Templates(directory="app/templates")


@router.get("/login")
async def admin_login_page(request: Request, error: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin_login.html",
        {"admin_prefix": ADMIN_PREFIX, "error": error == "1"},
    )


@router.post("/login")
async def admin_login(request: Request, password: str = Form(...)) -> HTMLResponse:
    login_key = client_ip(request)
    if _LOGIN_LIMITER.is_limited(login_key):
        return PlainTextResponse(
            "Too many login attempts. Try again later.",
            status_code=429,
            headers={"Retry-After": "600", "Cache-Control": "no-store"},
        )
    if not verify_admin_password(password):
        _LOGIN_LIMITER.allow(login_key)  # only failed attempts count toward the cap
        return RedirectResponse(url=f"{ADMIN_PREFIX}/login?error=1", status_code=303)

    response = HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}/login-callback');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        status_code=200,
    )
    # Merge, not clobber: if the browser already carries a "uid" claim (site
    # owner signed in as a regular user, then logs into /admin), it must
    # survive this write.
    update_session_claims(request, response, role="admin")
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
async def admin_logout(request: Request) -> HTMLResponse:
    response = HTMLResponse(
        content=(
            "<!doctype html><html><head></head><body><script>"
            f"window.location.replace('{ADMIN_PREFIX}/login');"
            "</script></body></html>"
        ),
        headers={"Cache-Control": "no-store"},
        status_code=200,
    )
    # Remove only the "role" claim -- a "uid" claim (regular user session),
    # if present, must survive an admin logout. write_session_claims deletes
    # the cookie outright only when the resulting claims dict is empty.
    update_session_claims(request, response, role=None)
    return response
