from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import vertexai
from fastapi import FastAPI, Request
from starlette.staticfiles import StaticFiles
from starlette.types import ASGIApp, Receive, Scope, Send

# Import plugins so they self-register on module import.
import core.languages.en.plugin  # noqa: F401
import core.languages.es.plugin  # noqa: F401
import core.languages.he.plugin  # noqa: F401
import core.languages.ru.plugin  # noqa: F401
from app.routes.about import router as about_router
from app.routes.admin import router as admin_router
from app.routes.api_analytics import router as api_analytics_router
from app.routes.api_preferences import router as api_preferences_router
from app.routes.api_progress import router as api_progress_router
from app.routes.audio import router as audio_router
from app.routes.auth_pages import router as auth_pages_router
from app.routes.feedback import router as feedback_router
from app.routes.health import router as health_router
from app.routes.home import router as home_router
from app.routes.learn import router as learn_router
from app.routes.privacy import router as privacy_router
from app.routes.terms import router as terms_router
from app.routes.verbs import router as verbs_router
from app.routes.well_known import router as well_known_router
from core.audio_backend.factory import create_audio_backend
from core.settings import load_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = load_settings()
    audio_backend = create_audio_backend(settings)
    vertexai.init(project=settings.google_cloud_project, location=settings.gcp_region)

    app.state.settings = settings
    app.state.audio_backend = audio_backend

    yield


class _CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: Scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


class _PageViewMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request = Request(scope, receive)

        if request.method != "GET":
            await self._app(scope, receive, send)
            return

        from datetime import UTC, datetime

        from core.analytics.client_context import detect_device_type
        from core.analytics.session_tracker import get_fingerprint_sid, start_session
        from core.i18n import resolve_ui_language

        if request.url.path not in {"/", "/verbs", "/learn", "/feedback"}:
            await self._app(scope, receive, send)
            return

        language = request.query_params.get("language", "")
        ui_lang = resolve_ui_language(request)
        user_agent = request.headers.get("user-agent")
        date = datetime.now(UTC).strftime("%Y-%m-%d")

        fingerprint = get_fingerprint_sid(request, date)
        await start_session(fingerprint, date, detect_device_type(user_agent), language, ui_lang)

        await self._app(scope, receive, send)


app = FastAPI(lifespan=lifespan, title="VerbBoard")
app.add_middleware(_PageViewMiddleware)  # pure ASGI — preserves all route-handler headers
app.mount("/static", _CachedStaticFiles(directory="app/static"), name="static")

app.include_router(about_router)
app.include_router(auth_pages_router)
app.include_router(privacy_router)
app.include_router(terms_router)
app.include_router(well_known_router)
app.include_router(admin_router)
app.include_router(api_analytics_router)
app.include_router(audio_router)
app.include_router(feedback_router)
app.include_router(health_router)
app.include_router(home_router)
app.include_router(learn_router)
app.include_router(verbs_router)
app.include_router(api_preferences_router)
app.include_router(api_progress_router)
