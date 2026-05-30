from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.safe_return import safe_return_to
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/auth/signin", response_class=HTMLResponse, include_in_schema=False)
def auth_signin_page(request: Request, return_to: str = "") -> HTMLResponse:
    settings = load_settings()
    # Re-serialize through json.loads/dumps to guarantee well-formed JSON with no
    # </script> injection risk, even if the raw secret value is malformed.
    try:
        firebase_cfg_json = json.dumps(
            json.loads(settings.firebase_web_config_json or "null")
        )
    except (TypeError, ValueError):
        firebase_cfg_json = "null"

    safe_return_json = json.dumps(safe_return_to(return_to, fallback=""))

    return templates.TemplateResponse(
        request,
        "signin.html",
        {
            "firebase_cfg_json": firebase_cfg_json,
            "safe_return_json": safe_return_json,
        },
    )
