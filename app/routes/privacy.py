from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.i18n import get_strings, resolve_ui_language
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page(request: Request) -> HTMLResponse:
    lang = resolve_ui_language(request)
    ui = get_strings(lang)
    settings = load_settings()

    return templates.TemplateResponse(
        request,
        "privacy.html",
        {
            "lang": lang,
            "html_dir": "rtl" if lang == "he" else "ltr",
            "firebase_web_config_json": settings.firebase_web_config_json,
            "auth_login": ui.get("auth.login", "Login"),
            "auth_logout": ui.get("auth.logout", "Logout"),
            "delete_account_button": ui.get("privacy.delete_account_button", "Delete my account and data"),
            "delete_account_confirm": ui.get(
                "privacy.delete_account_confirm",
                "This will permanently delete your account and all data (progress, practice history). "
                "This cannot be undone. Continue?",
            ),
            "delete_account_success": ui.get(
                "privacy.delete_account_success", "Your account and data have been deleted."
            ),
            "delete_account_error": ui.get(
                "privacy.delete_account_error", "Something went wrong. Please try again, or email us."
            ),
            "terms_label": ui.get("about.terms", "Terms of Use"),
            "contact_return_to": f"/privacy?ui_language={lang}",
        },
    )
