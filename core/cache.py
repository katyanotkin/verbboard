from __future__ import annotations

from pathlib import Path

AUDIO_CACHE_DIR = Path("audio_cache")


def audio_path(language: str, verb_id: str, voice_key: str, form_key: str) -> Path:
    # voice_key: "male" | "female"
    return AUDIO_CACHE_DIR / language / verb_id / voice_key / f"{form_key}.mp3"
