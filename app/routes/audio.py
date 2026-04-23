from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from core.audio_service import read_audio_bytes

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/audio/{language}/{verb_id}/{voice}/{form_key}.mp3")
def get_audio(
    request: Request,
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
):
    logger.warning("AUDIO REQUEST: %s %s %s %s", language, verb_id, voice, form_key)
    audio_backend = request.app.state.audio_backend
    audio_bytes = read_audio_bytes(
        audio_backend=audio_backend,
        language=language,
        verb_id=verb_id,
        voice=voice,
        form_key=form_key,
    )

    if audio_bytes is None:
        return PlainTextResponse("Audio not found", status_code=404)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
