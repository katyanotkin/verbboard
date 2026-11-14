from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.editions import active_study_plugins, study_language_label
from core.i18n import get_strings, resolve_ui_language
from core.languages.config import PLUS_EXTRA_STUDY_LANGUAGES
from core.seo_meta import static_page_meta
from core.settings import load_settings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request) -> HTMLResponse:
    lang = resolve_ui_language(request)
    ui = get_strings(lang)
    settings = load_settings()
    plugins = active_study_plugins(settings)
    study_languages = ", ".join(study_language_label(code, plugins, ui) for code in plugins)
    study_languages = f"{study_languages}, {ui.get('about.etc', 'etc.')}"

    response = templates.TemplateResponse(
        request,
        "about.html",
        {
            "lang": lang,
            "html_dir": "rtl" if lang == "he" else "ltr",
            "study_languages": study_languages,
            "title": ui.get("about.title", "About VerbBoard"),
            **static_page_meta(ui, "seo.about", "/about", default_title=ui.get("about.title", "About VerbBoard")),
            "back_label": ui.get("about.back", "Back"),
            "plus_request_label": ui["plus.request_btn"],
            "plus_title": ui["plus.about_title"],
            "plus_body": ui["plus.about_body"],
            "plus_request_language": PLUS_EXTRA_STUDY_LANGUAGES[0] if PLUS_EXTRA_STUDY_LANGUAGES else "",
            "rate_line": ui["about.rate_line"],
            "rate_label": ui["rate.link_label"],
            "feedback_label": ui.get("about.feedback", "Feedback"),
            "privacy_label": ui.get("about.privacy", "Privacy Policy"),
            "terms_label": ui.get("about.terms", "Terms of Use"),
            "firebase_web_config_json": settings.firebase_web_config_json,
            "auth_login": ui.get("auth.login", "Login"),
            "auth_logout": ui.get("auth.logout", "Logout"),
        },
    )
    return response
