from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import Request

SUPPORTED_UI_LANGS = {"en", "ru", "he", "es"}
DEFAULT_UI_LANG = "en"

_I18N_DIR = Path(__file__).parent.parent / "app" / "i18n"


@lru_cache(maxsize=8)
def get_strings(ui_lang: str) -> dict[str, str]:
    path = _I18N_DIR / f"{ui_lang}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_ui_language(request: Request) -> str:
    lang = request.query_params.get("ui_language", "")
    if lang in SUPPORTED_UI_LANGS:
        return lang

    lang = request.cookies.get("ui_language", "")
    if lang in SUPPORTED_UI_LANGS:
        return lang

    accept = request.headers.get("accept-language", "")
    for part in accept.split(","):
        code = part.strip().split(";")[0].strip()[:2].lower()
        if code in SUPPORTED_UI_LANGS:
            return code

    return DEFAULT_UI_LANG
