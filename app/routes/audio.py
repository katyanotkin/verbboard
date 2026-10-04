from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse, Response

from core.admin_auth import get_session_uid
from core.audio_service import (
    build_audio_key,
    ensure_audio,
    find_clip_text,
    read_audio_bytes,
)
from core.entitlements import can_study
from core.tts import VOICES

logger = logging.getLogger(__name__)

router = APIRouter()


async def _generate_on_demand(
    request: Request,
    audio_backend,
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
) -> bytes | None:
    from core.registry import get as get_plugin
    from core.verb_loader import load_entry_by_id

    voice_meta = VOICES[language][voice]

    verb = await asyncio.to_thread(load_entry_by_id, language=language, verb_id=verb_id)
    if verb is None:
        verb = await asyncio.to_thread(load_entry_by_id, language=language, verb_id=verb_id, source="candidate")
    if verb is None:
        return None

    plugin = get_plugin(language)
    board = plugin.build_board(verb, voice, voice_meta.label)

    clip = find_clip_text(board, form_key)
    if clip is None:
        return None
    text = clip[0]

    await ensure_audio(
        audio_backend=audio_backend,
        text=text,
        language=language,
        verb_id=verb_id,
        voice=voice,
        form_key=form_key,
        voice_edge_id=voice_meta.edge_id,
    )
    key = build_audio_key(language=language, verb_id=verb_id, voice=voice, form_key=form_key)
    return await asyncio.to_thread(audio_backend.read_bytes, key)


@router.get("/audio/{language}/{verb_id}/{voice}/{form_key}.mp3")
async def get_audio(
    request: Request,
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
):
    logger.debug("audio request: %s %s %s %s", language, verb_id, voice, form_key)

    if not can_study(language, get_session_uid(request)):
        # API-style endpoint serving raw audio bytes -- 403, not a redirect.
        return PlainTextResponse("Forbidden", status_code=403)

    audio_backend = request.app.state.audio_backend

    audio_bytes = await asyncio.to_thread(
        read_audio_bytes,
        audio_backend=audio_backend,
        language=language,
        verb_id=verb_id,
        voice=voice,
        form_key=form_key,
    )

    if audio_bytes is None and language in VOICES and voice in VOICES[language]:
        try:
            audio_bytes = await _generate_on_demand(
                request=request,
                audio_backend=audio_backend,
                language=language,
                verb_id=verb_id,
                voice=voice,
                form_key=form_key,
            )
        except Exception:
            logger.exception(
                "On-demand audio generation failed language=%s verb_id=%s voice=%s form_key=%s",
                language,
                verb_id,
                voice,
                form_key,
            )
            return None

    if audio_bytes is None:
        return PlainTextResponse("Audio not found", status_code=404)

    return Response(
        content=audio_bytes,
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
