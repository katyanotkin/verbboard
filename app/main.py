from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.audio import router as audio_router
from app.routes.health import router as health_router
from app.routes.home import router as home_router
from app.routes.learn import router as learn_router
from app.routes.about import router as about_router
from app.routes.feedback import router as feedback_router
from core.audio_backend.factory import create_audio_backend
from core.lexicon import lexicon_store
from core.settings import load_settings

# Import plugins so they self-register on module import.
import core.languages.en.plugin  # noqa: F401
import core.languages.es.plugin  # noqa: F401
import core.languages.he.plugin  # noqa: F401
import core.languages.ru.plugin  # noqa: F401

settings = load_settings()
audio_backend = create_audio_backend(settings)

app = FastAPI(title="VerbBoard")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.state.settings = settings
app.state.audio_backend = audio_backend


@app.on_event("startup")
def preload_runtime_data() -> None:
    if settings.verb_data_source == "local":
        lexicon_store.preload_all()


app.include_router(home_router)
app.include_router(learn_router)
app.include_router(audio_router)
app.include_router(health_router)
app.include_router(about_router)
app.include_router(feedback_router)
