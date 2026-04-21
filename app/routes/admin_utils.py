from __future__ import annotations

import logging
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from core.admin_auth import ADMIN_SESSION_COOKIE, verify_admin_session_token
from core.settings import load_settings

logger = logging.getLogger(__name__)

_SETTINGS = load_settings()
ADMIN_PREFIX = "/admin"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

VERBS_COLLECTION = "verbs"
CANDIDATES_COLLECTION = "verb_candidates"

CANDIDATE_STATUSES = {
    "needs_generation",
    "pending",
    "to_be_fixed",
    "duplicate",
    "promoted",
}


def signal_collections() -> tuple[str, str]:
    return _SETTINGS.verb_signals_collection, _SETTINGS.verb_signal_labels_collection


def require_admin_page(request: Request) -> RedirectResponse | None:
    token = request.cookies.get(ADMIN_SESSION_COOKIE, "")
    if token and verify_admin_session_token(token):
        return None

    return RedirectResponse(url=f"{ADMIN_PREFIX}/login", status_code=303)


def require_admin_api(request: Request) -> None:
    token = request.cookies.get(ADMIN_SESSION_COOKIE, "")
    if token and verify_admin_session_token(token):
        return

    raise HTTPException(status_code=401, detail="Unauthorized")
