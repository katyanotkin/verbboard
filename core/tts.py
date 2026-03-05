from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

import edge_tts


@dataclass(frozen=True)
class Voice:
    key: str
    label: str
    edge_id: str


# You can adjust voices later. These are placeholders that worked for your Hebrew tests.
VOICES = {
    "en": {
        "female": Voice("female", "Female", "en-US-JennyNeural"),
        "male": Voice("male", "Male", "en-US-GuyNeural"),
    },
    "ru": {
        "female": Voice("female", "Female", "ru-RU-SvetlanaNeural"),
        "male": Voice("male", "Male", "ru-RU-DmitryNeural"),
    },
    "he": {
        "female": Voice("female", "Female", "he-IL-HilaNeural"),
        "male": Voice("male", "Male", "he-IL-AvriNeural"),
    },
}

RATE = "-10%"

# Avoid flakiness under parallel requests
_SEMAPHORE = asyncio.Semaphore(2)


async def tts_to_mp3(text: str, out_path: Path, voice_edge_id: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 2000:
        return

    async with _SEMAPHORE:
        communicate = edge_tts.Communicate(text=text, voice=voice_edge_id, rate=RATE)
        await communicate.save(str(out_path))
