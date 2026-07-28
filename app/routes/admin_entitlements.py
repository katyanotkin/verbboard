from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.routes.admin_utils import ADMIN_PREFIX, require_admin_page
from core.entitlements import get_entitlement, list_entitlements, lookup_uid_by_email, set_entitlement

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

_VALID_STATUSES = {"active", "expired", "revoked", "none"}


def _resolve_uid(identifier: str) -> tuple[str | None, str | None, str | None]:
    """Resolve an admin-entered identifier to a Firebase Auth uid.

    Accepts either an email address (looked up via firebase_admin) or a raw
    uid pasted directly. Returns (uid, email, error_message) -- email is the
    identifier itself when it was an email, None for a raw-uid lookup (we
    have no email to display-cache in that case).
    """
    identifier = identifier.strip()
    if not identifier:
        return None, None, "Enter an email or uid."
    if "@" in identifier:
        uid, error = lookup_uid_by_email(identifier)
        if uid is None:
            return None, None, error or f"No Firebase Auth account found for {identifier!r}."
        return uid, identifier, None
    return identifier, None, None


def _render(
    request: Request,
    *,
    q: str,
    uid: str | None,
    error: str | None,
    entitlement: dict | None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin_entitlements.html",
        {
            "admin_prefix": ADMIN_PREFIX,
            "q": q,
            "uid": uid,
            "error": error,
            "entitlement": entitlement,
            "records": list_entitlements(),
        },
    )


@router.get("/entitlements", response_class=HTMLResponse)
async def admin_entitlements_page(request: Request, q: str = "") -> HTMLResponse:
    redirect_response = require_admin_page(request)
    if redirect_response is not None:
        return redirect_response

    uid: str | None = None
    error: str | None = None
    entitlement: dict | None = None

    if q:
        uid, _email, error = _resolve_uid(q)
        if uid is not None:
            entitlement = get_entitlement(uid)

    return _render(request, q=q, uid=uid, error=error, entitlement=entitlement)


@router.post("/entitlements", response_class=HTMLResponse)
async def admin_entitlements_update(
    request: Request,
    identifier: str = Form(...),
    status: str = Form(...),
    note: str = Form(""),
) -> HTMLResponse:
    redirect_response = require_admin_page(request)
    if redirect_response is not None:
        return redirect_response

    uid, email, error = _resolve_uid(identifier)
    if uid is None:
        return _render(request, q=identifier, uid=None, error=error, entitlement=None)

    if status not in _VALID_STATUSES:
        return _render(
            request,
            q=identifier,
            uid=uid,
            error=f"Unsupported status: {status!r}",
            entitlement=get_entitlement(uid),
        )

    set_entitlement(uid=uid, status=status, note=note.strip(), email=email)
    logger.info("admin_entitlements: uid=%s status=%s", uid, status)

    return RedirectResponse(
        url=f"{ADMIN_PREFIX}/entitlements?q={quote(identifier, safe='')}",
        status_code=303,
    )
