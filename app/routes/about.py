from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.i18n import get_strings, resolve_ui_language
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request) -> HTMLResponse:
    lang = resolve_ui_language(request)
    ui = get_strings(lang)
    settings = load_settings()

    response = templates.TemplateResponse(
        request,
        "about.html",
        {
            "lang": lang,
            "html_dir": "rtl" if lang == "he" else "ltr",
            "title": ui.get("about.title", "About VerbBoard"),
            "back_label": ui.get("about.back", "Back"),
            "feedback_label": ui.get("about.feedback", "Feedback"),
            "firebase_web_config_json": settings.firebase_web_config_json,
            "auth_login": ui.get("auth.login", "Login"),
            "auth_logout": ui.get("auth.logout", "Logout"),
        },
    )
    response.set_cookie("ui_language", lang, httponly=False, samesite="lax")
    return response
