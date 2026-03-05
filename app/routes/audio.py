from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse, PlainTextResponse

router = APIRouter()


@router.get("/audio/{language}/{verb_id}/{voice}/{form_key}.mp3")
def get_audio(language: str, verb_id: str, voice: str, form_key: str):
    path = Path("audio_cache") / language / verb_id / voice / f"{form_key}.mp3"
    if not path.exists():
        return PlainTextResponse("Audio not found", status_code=404)
    return FileResponse(path, media_type="audio/mpeg")
