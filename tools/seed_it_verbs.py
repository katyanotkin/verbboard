"""One-off seeding script: generate the 20 most common Italian verbs via the
real AI-generation pipeline and write them straight into the live `verbs`
Firestore collection, bypassing the admin candidate-review queue.

This exists to stand up real Plus-only content for testing the entitlement
gate end to end (Phase 1), not as a repeatable production tool -- the normal
path for adding verbs is the admin candidate review flow in
app/routes/admin_candidates.py.

Usage:
    .venv/bin/python -m tools.seed_it_verbs
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

import core.languages.it.plugin  # noqa: E402,F401  -- self-registers "it" in the plugin registry
from app.routes.admin_candidates import _call_claude, _ClaudeVerbResponse  # noqa: E402
from core.storage.firestore_db import get_db  # noqa: E402
from core.storage.verb_document import (  # noqa: E402
    build_search_extract_from_entry,
    build_storage_verb_id,
    build_verb_document,
)
from core.storage.verb_repository import upsert_verb  # noqa: E402

LANGUAGE = "it"
VERBS_COLLECTION = "verbs"

# 20 most common Italian verbs for a beginner learner, in rough frequency order.
LEMMAS = [
    "essere",
    "avere",
    "fare",
    "andare",
    "dire",
    "potere",
    "volere",
    "dovere",
    "sapere",
    "vedere",
    "dare",
    "stare",
    "venire",
    "parlare",
    "mangiare",
    "bere",
    "lavorare",
    "vivere",
    "credere",
    "prendere",
]


def _get_max_rank(language: str) -> int:
    db = get_db()
    result = db.collection(VERBS_COLLECTION).where("language", "==", language).count().get()
    return result[0][0].value


async def _seed_one(lemma: str, rank: int) -> None:
    print(f"[{rank:>2}] generating {lemma!r}...", flush=True)
    generated = await _call_claude(LANGUAGE, lemma)
    try:
        _ClaudeVerbResponse.model_validate(generated)
    except ValidationError as exc:
        print(f"    SKIPPED -- generation returned unexpected shape: {exc}")
        return

    resolved_lemma = generated.get("lemma") or lemma
    if not resolved_lemma:
        print(f"    SKIPPED -- Claude returned no lemma for query {lemma!r} (not recognized as a verb)")
        return

    verb_id = build_storage_verb_id(language=LANGUAGE, lemma=resolved_lemma)
    search_extract = build_search_extract_from_entry(language=LANGUAGE, entry=generated)

    doc = build_verb_document(
        language=LANGUAGE,
        verb_id=verb_id,
        lemma=resolved_lemma,
        rank=rank,
        forms=generated.get("forms", {}),
        examples=generated.get("examples", []),
        display_lemma=None,
        display_forms=None,
        morph=generated.get("morph") or None,
        search_extract=search_extract,
    )
    upsert_verb(verb_id, doc)
    print(f"    OK -- wrote {verb_id} (rank={rank}, {len(doc['examples'])} examples)")


async def main() -> None:
    start_rank = _get_max_rank(LANGUAGE) + 1
    for offset, lemma in enumerate(LEMMAS):
        await _seed_one(lemma, start_rank + offset)


if __name__ == "__main__":
    asyncio.run(main())
