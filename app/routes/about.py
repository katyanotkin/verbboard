from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from core.i18n import get_strings

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

ABOUT_TITLES = {
    "en": "About VerbBoard",
    "ru": "О приложении VerbBoard",
    "es": "Sobre VerbBoard",
    "he": "אודות VerbBoard",
}


@router.get("/about", response_class=HTMLResponse)
def about_page(request: Request) -> HTMLResponse:
    lang = request.query_params.get("lang", "en")
    if lang not in {"en", "ru", "es", "he"}:
        lang = "en"

    ui = get_strings(lang)

    return templates.TemplateResponse(
        request,
        "about.html",
        {
            "lang": lang,
            "html_dir": "rtl" if lang == "he" else "ltr",
            "title": ABOUT_TITLES[lang],
            "about_titles": ABOUT_TITLES,
            "back_label": ui.get("about.back", "Back"),
            "feedback_label": ui.get("about.feedback", "Feedback"),
        },
    )
