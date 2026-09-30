"""One-off script: generate the 10 most common Turkish verbs through the same
pipeline a search miss uses (Claude generation -> example + lemma translations
-> live `verbs` doc + `verb_candidates` audit doc -> audio pre-warm).

Safe to re-run: a verb that already exists is skipped. AUDIO_BUCKET is read from
Settings (env var / .env); Firestore is shared across environments but audio
buckets are per-environment, so run once per bucket to warm both (verbs that
already exist are skipped for generation, so use tools/prewarm_*_audio.py-style
warming for the second bucket, or just let audio generate on first play).

Usage:
    AUDIO_BUCKET=verbboard-audio-stage .venv/bin/python -m tools.seed_tr_verbs
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.languages.tr.plugin  # noqa: E402,F401  -- self-registers "tr"
from core.audio_backend.factory import create_audio_backend  # noqa: E402
from core.settings import load_settings  # noqa: E402
from core.storage.verb_repository import list_verbs  # noqa: E402
from core.verb_autogen import autogenerate_missing_verb  # noqa: E402

LANGUAGE = "tr"

# Most common Turkish verbs by everyday frequency, in rank order.
LEMMAS = [
    "olmak",  # to be / become
    "yapmak",  # to do / make
    "etmek",  # to do (light verb)
    "gitmek",  # to go
    "gelmek",  # to come
    "görmek",  # to see
    "bilmek",  # to know
    "istemek",  # to want
    "vermek",  # to give
    "almak",  # to take / get
]


async def main() -> None:
    settings = load_settings()
    audio_backend = create_audio_backend(settings)
    print(f"Generating {len(LEMMAS)} Turkish verbs (audio bucket {settings.audio_bucket!r})...")

    for lemma in LEMMAS:
        print(f"  {lemma}...", flush=True)
        await autogenerate_missing_verb(language=LANGUAGE, query=lemma, audio_backend=audio_backend)

    verbs = list_verbs(LANGUAGE)
    print(f"Done. {len(verbs)} Turkish verbs live:")
    for verb in sorted(verbs, key=lambda item: item.get("rank") or 0):
        examples = verb.get("examples") or []
        translated = sum(1 for example in examples if example.get("translations"))
        print(
            f"  #{verb.get('rank')} {verb['verb_id']}: {len(examples)} examples "
            f"({translated} translated), lemma translations: {sorted((verb.get('lemma_translations') or {}))}"
        )


if __name__ == "__main__":
    asyncio.run(main())
