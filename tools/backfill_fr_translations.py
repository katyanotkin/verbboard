"""One-off script: backfill inline translations (examples + lemma) for every
French verb currently in Firestore, using the same translate_examples()/
translate_lemma() pipeline app/routes/admin_candidates.py calls on generate.

Modeled on tools/backfill_it_translations.py.

Usage:
    .venv/bin/python -m tools.backfill_fr_translations
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.settings import _load_anthropic_api_key, load_settings  # noqa: E402
from core.storage.verb_repository import list_verbs, upsert_verb  # noqa: E402
from core.translation_service import translate_examples, translate_lemma  # noqa: E402

LANGUAGE = "fr"


async def _backfill_one(verb_data: dict, project: str, api_key: str) -> None:
    verb_id = verb_data["verb_id"]
    lemma = verb_data["lemma"]
    print(f"  {verb_id}...", flush=True)

    translated_examples, lemma_translations = await asyncio.gather(
        asyncio.to_thread(
            translate_examples,
            verb_lang=LANGUAGE,
            lemma=lemma,
            examples=verb_data.get("examples", []),
            project=project,
            api_key=api_key,
        ),
        asyncio.to_thread(
            translate_lemma,
            verb_lang=LANGUAGE,
            lemma=lemma,
            project=project,
            api_key=api_key,
        ),
    )

    update: dict = {}
    if translated_examples is not verb_data.get("examples"):
        update["examples"] = translated_examples
    if lemma_translations:
        update["lemma_translations"] = lemma_translations

    if not update:
        print(f"  {verb_id} -- no translations returned, skipped")
        return

    upsert_verb(verb_id, {**verb_data, **update})
    print(f"  {verb_id} done ({len(lemma_translations or {})} lemma langs)")


async def main() -> None:
    settings = load_settings()
    api_key = _load_anthropic_api_key()

    verbs = list_verbs(LANGUAGE)
    print(f"Backfilling translations for {len(verbs)} French verbs...")

    for verb_data in verbs:
        await _backfill_one(verb_data, settings.google_cloud_project, api_key)

    print("All done.")


if __name__ == "__main__":
    asyncio.run(main())
