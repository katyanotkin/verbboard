from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.i18n import get_strings, resolve_ui_language
from core.safe_return import safe_return_to
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# English fallbacks double as the key list: every key here is sent to the page.
_SIGNIN_STRINGS = {
    "signin.title": "Sign in to VerbBoard",
    "signin.checking": "Checking sign-in status…",
    "signin.button": "Sign in with Google",
    "signin.tap_to_sign_in": "Tap the button to sign in to VerbBoard.",
    "signin.signing_in": "Signing in…",
    "signin.signing_you_in": "Signing you in…",
    "signin.signed_in": "Signed in!",
    "signin.close_tab": "You can close this tab and return to VerbBoard.",
    "signin.failed": "Sign-in failed.",
    "signin.not_configured": "Auth not configured.",
    "signin.unavailable": "Sign-in is temporarily unavailable.",
    "signin.unavailable_hint": "Could not load Google Sign-In. Check your connection or content blockers, then reload this page.",
}


def _html_safe_json(value: object) -> str:
    """Serialize to JSON with <, >, & unicode-escaped for safe inline <script> use."""
    return json.dumps(value).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


@router.get("/auth/signin", response_class=HTMLResponse, include_in_schema=False)
def auth_signin_page(request: Request, return_to: str = "") -> HTMLResponse:
    settings = load_settings()
    # load_settings() pre-escapes via _safe_firebase_config(); re-escape here as
    # defence-in-depth in case the value was set directly (e.g. in tests).
    try:
        firebase_cfg_json = _html_safe_json(json.loads(settings.firebase_web_config_json or "null"))
    except (TypeError, ValueError):
        firebase_cfg_json = "null"
    safe_return_json = _html_safe_json(safe_return_to(return_to, fallback=""))
    lang = resolve_ui_language(request)
    ui = get_strings(lang)
    strings = {key: ui.get(key, fallback) for key, fallback in _SIGNIN_STRINGS.items()}

    return templates.TemplateResponse(
        request,
        "signin.html",
        {
            "firebase_cfg_json": firebase_cfg_json,
            "safe_return_json": safe_return_json,
            "lang": lang,
            "html_dir": "rtl" if lang == "he" else "ltr",
            "strings": strings,
            "strings_json": _html_safe_json(strings),
        },
    )
