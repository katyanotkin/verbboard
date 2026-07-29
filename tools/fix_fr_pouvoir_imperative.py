"""One-off script: regenerate forms (not examples) for fr_pouvoir, whose
imperatif was found fabricated by the linguist-agent audit (2026-07-28) --
pouvoir is grammatically defective in the imperative mood in standard French
(no genuine command form exists), but generation had copied the présent
forms ("peux"/"pouvons"/"pouvez") into imperatif as if they were valid.
Fixed by adding an explicit defective-imperative rule to _PROMPT_FR in
core/settings_ai.py; this script re-runs generation against the fixed prompt
for just this verb and re-warms its audio, mirroring
app/routes/admin_candidates.py's regen_verb_forms endpoint (examples/
translations are left untouched). Same pattern as
tools/fix_it_modal_imperative.py.

Usage:
    .venv/bin/python -m tools.fix_fr_pouvoir_imperative
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError  # noqa: E402

import core.languages.fr.plugin  # noqa: E402,F401  -- self-registers "fr"
from app.routes.admin_candidates import _call_claude, _ClaudeVerbResponse, _warm_verb_audio  # noqa: E402
from core.audio_backend.factory import create_audio_backend  # noqa: E402
from core.settings import load_settings  # noqa: E402
from core.storage.firestore_db import get_db  # noqa: E402
from core.storage.verb_document import build_search_extract_from_entry  # noqa: E402

LANGUAGE = "fr"
VERBS_COLLECTION = "verbs"
VERB_ID = "fr_pouvoir"


async def main() -> None:
    settings = load_settings()
    audio_backend = create_audio_backend(settings)
    db = get_db()

    doc_ref = db.collection(VERBS_COLLECTION).document(VERB_ID)
    doc = doc_ref.get()
    if not doc.exists:
        print(f"{VERB_ID} -- NOT FOUND")
        return

    existing = doc.to_dict()
    lemma = existing.get("lemma", "")
    print(f"{VERB_ID} ({lemma!r}) regenerating forms...", flush=True)

    generated = await _call_claude(LANGUAGE, lemma)
    try:
        _ClaudeVerbResponse.model_validate(generated)
    except ValidationError as exc:
        print(f"  SKIPPED -- unexpected shape: {exc}")
        return

    before = (existing.get("forms") or {}).get("imperatif")
    after = (generated.get("forms") or {}).get("imperatif")
    print(f"  imperatif: {before!r} -> {after!r}")

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
    print("  OK -- updated + audio re-warmed")


if __name__ == "__main__":
    asyncio.run(main())
