from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.safe_return import safe_return_to
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _html_safe_json(value: object) -> str:
    """Serialize to JSON with <, >, & unicode-escaped for safe inline <script> use."""
    return (
        json.dumps(value)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


@router.get("/auth/signin", response_class=HTMLResponse, include_in_schema=False)
def auth_signin_page(request: Request, return_to: str = "") -> HTMLResponse:
    settings = load_settings()
    # Re-serialize to guarantee well-formed JSON, then unicode-escape <, >, & so
    # the value is safe inside an HTML <script> block (json.dumps alone does not
    # escape these, and a value containing </script> would break the block).
    try:
        firebase_cfg_json = _html_safe_json(
            json.loads(settings.firebase_web_config_json or "null")
        )
    except (TypeError, ValueError):
        firebase_cfg_json = "null"

    safe_return_json = _html_safe_json(safe_return_to(return_to, fallback=""))

    return templates.TemplateResponse(
        request,
        "signin.html",
        {
            "firebase_cfg_json": firebase_cfg_json,
            "safe_return_json": safe_return_json,
        },
    )
