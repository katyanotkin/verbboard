"""One-off script: regenerate forms (not examples) for the two Italian verbs
whose formal (Lei) imperative was found wrong by the linguist-agent audit
(2026-07-28) -- dovere/potere used presente indicativo ("deve"/"può") instead
of the grammatically correct congiuntivo presente ("debba"/"possa"). Fixed by
adding an explicit derivation rule to _PROMPT_IT in core/settings_ai.py; this
script re-runs generation against the fixed prompt for just these two verbs
and re-warms their audio, mirroring app/routes/admin_candidates.py's
regen_verb_forms endpoint (examples/translations are left untouched).

Usage:
    .venv/bin/python -m tools.fix_it_modal_imperative
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

import core.languages.it.plugin  # noqa: E402,F401  -- self-registers "it"
from app.routes.admin_candidates import _call_claude, _ClaudeVerbResponse, _warm_verb_audio  # noqa: E402
from core.audio_backend.factory import create_audio_backend  # noqa: E402
from core.settings import load_settings  # noqa: E402
from core.storage.firestore_db import get_db  # noqa: E402
from core.storage.verb_document import build_search_extract_from_entry  # noqa: E402

LANGUAGE = "it"
VERBS_COLLECTION = "verbs"
VERB_IDS = ["it_dovere", "it_potere"]


async def _fix_one(db, audio_backend, verb_id: str) -> None:
    doc_ref = db.collection(VERBS_COLLECTION).document(verb_id)
    doc = doc_ref.get()
    if not doc.exists:
        print(f"  {verb_id} -- NOT FOUND, skipped")
        return

    existing = doc.to_dict()
    lemma = existing.get("lemma", "")
    print(f"  {verb_id} ({lemma!r}) regenerating forms...", flush=True)

    generated = await _call_claude(LANGUAGE, lemma)
    try:
        _ClaudeVerbResponse.model_validate(generated)
    except ValidationError as exc:
        print(f"    SKIPPED -- unexpected shape: {exc}")
        return

    before = (existing.get("forms") or {}).get("imperativo", {}).get("lei")
    after = (generated.get("forms") or {}).get("imperativo", {}).get("lei")
    print(f"    imperativo.lei: {before!r} -> {after!r}")

    now = datetime.now(UTC).isoformat()
    update = {
        "morph": generated.get("morph") or None,
        "forms": generated.get("forms", {}),
        "search_extract": build_search_extract_from_entry(language=LANGUAGE, entry=generated),
        "updated_at": now,
    }
    doc_ref.update(update)

    updated_verb_data = {**existing, **update}
    await _warm_verb_audio(audio_backend, LANGUAGE, updated_verb_data)
    print("    OK -- updated + audio re-warmed")


async def main() -> None:
    settings = load_settings()
    audio_backend = create_audio_backend(settings)
    db = get_db()

    for verb_id in VERB_IDS:
        await _fix_one(db, audio_backend, verb_id)

    print("All done.")


if __name__ == "__main__":
    asyncio.run(main())
