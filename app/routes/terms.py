from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.i18n import get_strings, resolve_ui_language
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/terms", response_class=HTMLResponse)
def terms_page(request: Request) -> HTMLResponse:
    lang = resolve_ui_language(request)
    ui = get_strings(lang)
    settings = load_settings()

    return templates.TemplateResponse(
        request,
        "terms.html",
        {
            "lang": lang,
            "html_dir": "rtl" if lang == "he" else "ltr",
            "firebase_web_config_json": settings.firebase_web_config_json,
            "auth_login": ui.get("auth.login", "Login"),
            "auth_logout": ui.get("auth.logout", "Logout"),
            "privacy_label": ui.get("about.privacy", "Privacy Policy"),
            "contact_return_to": f"/terms?ui_language={lang}",
        },
    )
