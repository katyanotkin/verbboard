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
    "es": {
        "female": Voice("female", "Female", "es-ES-ElviraNeural"),
        "male": Voice("male", "Male", "es-ES-AlvaroNeural"),
    },
    "it": {
        "female": Voice("female", "Female", "it-IT-ElsaNeural"),
        "male": Voice("male", "Male", "it-IT-DiegoNeural"),
    },
    "fr": {
        "female": Voice("female", "Female", "fr-FR-DeniseNeural"),
        "male": Voice("male", "Male", "fr-FR-HenriNeural"),
    },
}

RATE = "-10%"

# Avoid flakiness under parallel requests
_SEMAPHORE = asyncio.Semaphore(2)

# Edge TTS is a free, unofficial API that intermittently drops/resets
# connections under the sustained bulk concurrency of _warm_verb_audio's
# per-verb, per-voice generation sweep. A failed call previously propagated
# straight up to be silently swallowed by the caller's asyncio.gather(...,
# return_exceptions=True) with no retry, so a single hiccup mid-batch could
# permanently drop one voice's audio for a verb (bit us: a verb would end up
# with a female-voice row but a missing male-voice row for the same form).
_MAX_TTS_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = (0.5, 1.5)


async def tts_to_mp3(text: str, out_path: Path, voice_edge_id: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 2000:
        return

    async with _SEMAPHORE:
        last_error: Exception | None = None
        for attempt in range(_MAX_TTS_ATTEMPTS):
            try:
                communicate = edge_tts.Communicate(text=text, voice=voice_edge_id, rate=RATE)
                await communicate.save(str(out_path))
                return
            except Exception as exc:
                last_error = exc
                # edge_tts.Communicate.save() writes directly to out_path with
                # no temp-file+atomic-rename, so a failure mid-stream can leave
                # a truncated file behind. A retry's fresh open() naturally
                # overwrites it, but on the *last* failed attempt nothing else
                # will -- and if that truncated file happens to exceed the
                # cache-hit threshold above, it would be served as complete
                # forever. Remove it so a future call regenerates instead.
                out_path.unlink(missing_ok=True)
                if attempt < _MAX_TTS_ATTEMPTS - 1:
                    await asyncio.sleep(_RETRY_BACKOFF_SECONDS[attempt])
        assert last_error is not None
        raise last_error
