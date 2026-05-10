from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from app.routes.about import router as about_router
from app.routes.admin import router as admin_router
from app.routes.audio import router as audio_router
from app.routes.feedback import router as feedback_router
from app.routes.health import router as health_router
from app.routes.home import router as home_router
from app.routes.learn import router as learn_router
from app.routes.verbs import router as verbs_router
from core.audio_backend.factory import create_audio_backend
from core.settings import load_settings

# Import plugins so they self-register on module import.
import core.languages.en.plugin  # noqa: F401
import core.languages.es.plugin  # noqa: F401
import core.languages.he.plugin  # noqa: F401
import core.languages.ru.plugin  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    audio_backend = create_audio_backend(settings)

    app.state.settings = settings
    app.state.audio_backend = audio_backend

    yield


class _CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "public, max-age=3600"
        return response


app = FastAPI(lifespan=lifespan, title="VerbBoard")
app.mount("/static", _CachedStaticFiles(directory="app/static"), name="static")

app.include_router(about_router)
app.include_router(admin_router)
app.include_router(audio_router)
app.include_router(feedback_router)
app.include_router(health_router)
app.include_router(home_router)
app.include_router(learn_router)
app.include_router(verbs_router)
