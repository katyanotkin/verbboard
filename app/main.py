from __future__ import annotations

from fastapi import FastAPI

from app.routes.audio import router as audio_router
from app.routes.home import router as home_router
from app.routes.learn import router as learn_router
from core.audio_backend.factory import create_audio_backend
from core.settings import load_settings

# Import plugins so they self-register on module import.
import core.languages.en.plugin  # noqa: F401
import core.languages.he.plugin  # noqa: F401
import core.languages.ru.plugin  # noqa: F401

settings = load_settings()
audio_backend = create_audio_backend(settings)

app = FastAPI(title="VerbBoard")
app.state.settings = settings
app.state.audio_backend = audio_backend

app.include_router(home_router)
app.include_router(learn_router)
app.include_router(audio_router)


@app.get("/health")
def health() -> dict[str, str | int]:
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "audio_backend": settings.audio_backend,
        "port": settings.port,
    }
