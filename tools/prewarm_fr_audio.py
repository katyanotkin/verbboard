"""One-off script: pre-generate TTS audio (both voices) for every French
verb currently in Firestore, using the same _warm_verb_audio() pipeline the
admin candidate flow uses on verb add/regenerate.

Modeled on tools/prewarm_it_audio.py. AUDIO_BUCKET is read from Settings
(env var / .env) -- run once with AUDIO_BUCKET=verbboard-audio-stage and
once with AUDIO_BUCKET=verbboard-audio-prod to warm both environments,
since Firestore verb data is shared but audio buckets are per-environment.

Usage:
    AUDIO_BUCKET=verbboard-audio-stage .venv/bin/python -m tools.prewarm_fr_audio
    AUDIO_BUCKET=verbboard-audio-prod  .venv/bin/python -m tools.prewarm_fr_audio
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.languages.fr.plugin  # noqa: E402,F401  -- self-registers "fr"
from app.routes.admin_candidates import _warm_verb_audio  # noqa: E402
from core.audio_backend.factory import create_audio_backend  # noqa: E402
from core.settings import load_settings  # noqa: E402
from core.storage.verb_repository import list_verbs  # noqa: E402

LANGUAGE = "fr"


async def main() -> None:
    settings = load_settings()
    audio_backend = create_audio_backend(settings)

    verbs = list_verbs(LANGUAGE)
    print(f"Pre-warming audio for {len(verbs)} French verbs into bucket {settings.audio_bucket!r}...")

    for verb_data in verbs:
        verb_id = verb_data["verb_id"]
        print(f"  {verb_id}...", flush=True)
        await _warm_verb_audio(audio_backend, LANGUAGE, verb_data)
        print(f"  {verb_id} done")

    print("All done.")


if __name__ == "__main__":
    asyncio.run(main())
