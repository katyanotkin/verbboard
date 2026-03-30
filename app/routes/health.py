from __future__ import annotations

from fastapi import APIRouter, Request

from core.lexicon import lexicon_store

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings

    return {
        "status": "ok",
        "app_env": settings.app_env,
        "environment": settings.environment,
        "verb_data_source": settings.verb_data_source,
        "verb_demand_bucket": settings.verb_demand_bucket,
        "audio_backend": settings.audio_backend,
        "port": settings.port,
        "loaded_languages": lexicon_store.loaded_languages(),
    }


@router.get("/health/data")
def health_data(request: Request) -> dict[str, object]:
    settings = request.app.state.settings

    return {
        "status": "ok",
        "verb_data_source": settings.verb_data_source,
        "loaded_languages": lexicon_store.loaded_languages(),
    }


@router.get("/health/audio")
def health_audio(request: Request) -> dict[str, object]:
    settings = request.app.state.settings

    return {
        "status": "ok",
        "audio_backend": settings.audio_backend,
    }
