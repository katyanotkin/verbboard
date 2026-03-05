from __future__ import annotations

from fastapi import FastAPI

from app.routes.home import router as home_router
from app.routes.learn import router as learn_router
from app.routes.audio import router as audio_router

from core.registry import register, LanguagePlugin
from core.languages.en.plugin import build_board as build_en
from core.languages.ru.plugin import build_board as build_ru
from core.languages.he.plugin import build_board as build_he

app = FastAPI()

# Register plugins
register(LanguagePlugin(language="en", display_name="English", build_board=build_en))
register(LanguagePlugin(language="ru", display_name="Russian", build_board=build_ru))
register(LanguagePlugin(language="he", display_name="Hebrew", build_board=build_he))

# Routes
app.include_router(home_router)
app.include_router(learn_router)
app.include_router(audio_router)
