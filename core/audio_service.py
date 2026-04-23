from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

from core.audio_backend.base import AudioBackend
from core.tts import tts_to_mp3

logger = logging.getLogger(__name__)


def build_hashed_audio_key(base_form_key: str, text: str) -> str:
    normalized_text = text.strip()
    text_hash = hashlib.sha1(normalized_text.encode("utf-8")).hexdigest()[:10]
    return f"{base_form_key}_{text_hash}"


def build_audio_key(
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
) -> str:
    return f"audio/{language}/{verb_id}/{voice}/{form_key}.mp3"


async def ensure_audio(
    audio_backend: AudioBackend,
    text: str,
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
    voice_edge_id: str,
) -> str:
    key = build_audio_key(
        language=language,
        verb_id=verb_id,
        voice=voice,
        form_key=form_key,
    )

    normalized_text = text.strip()
    logger.warning(
        "ENSURE AUDIO language=%s verb_id=%s voice=%s form_key=%s text=%r",
        language,
        verb_id,
        voice,
        form_key,
        normalized_text,
    )

    if audio_backend.exists(key):
        logger.info("Audio cache hit: %s", key)
        return key

    logger.info("Audio cache miss: %s", key)

    with TemporaryDirectory() as temporary_dir:
        output_path = Path(temporary_dir) / "audio.mp3"
        await tts_to_mp3(normalized_text, output_path, voice_edge_id)
        audio_bytes = output_path.read_bytes()

    audio_backend.write_bytes(key, audio_bytes)
    logger.info("Audio written: %s", key)

    return key


def read_audio_bytes(
    audio_backend: AudioBackend,
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
) -> bytes | None:
    key = build_audio_key(
        language=language,
        verb_id=verb_id,
        voice=voice,
        form_key=form_key,
    )

    logger.warning(
        "READ AUDIO language=%s verb_id=%s voice=%s form_key=%s key=%s",
        language,
        verb_id,
        voice,
        form_key,
        key,
    )

    if not audio_backend.exists(key):
        logger.info("Audio not found: %s", key)
        return None

    logger.info("Audio read: %s", key)
    return audio_backend.read_bytes(key)
