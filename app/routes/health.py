from __future__ import annotations

import os

from fastapi import APIRouter, Request

from core.lexicon import lexicon_store

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, object]:
    settings = request.app.state.settings

    return {
        "status": "ok",
        "environment": settings.environment,
        "K_SERVICE": os.getenv("K_SERVICE"),
        "verb_data_source": settings.verb_data_source,
        "audio_backend": settings.audio_backend,
        "audio_bucket": settings.audio_bucket,
        "port": settings.port,
        "loaded_languages": lexicon_store.loaded_languages(),
    }
