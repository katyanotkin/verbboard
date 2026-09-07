"""One-off script: replace fr_connaitre's weakest example sentence with a
genuine imperative-mood example (fixes GitHub issue #14). The verb has valid
`imperatif` forms but none of its stored examples actually demonstrated the
mood -- the closest one ("Connaissez-vous un bon restaurant...?") is a
présent-indicatif question, not a command.

Sibling issue fr_devoir is NOT fixed here: a linguist-agent review found no
example can honestly demonstrate devoir's imperative, since ordering someone
to "obligate themselves" is pragmatically near-unusable in real French (see
the note added to _PROMPT_FR in core/settings_ai.py). Forcing a contrived
sentence there would teach the wrong register more actively than the current
gap, so fr_devoir's examples are left untouched.

Usage:
    .venv/bin/python -m tools.fix_fr_connaitre_imperative_example
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.storage.firestore_db import get_db  # noqa: E402

VERB_ID = "fr_connaitre"

NEW_EXAMPLE = {
    "dst": "Connaissez vos droits avant de signer un contrat de location.",
    "translations": {
        "en": "Know your rights before signing a rental agreement.",
        "es": "Conozca sus derechos antes de firmar un contrato de alquiler.",
        "he": "הכירו את זכויותיכם לפני חתימה על חוזה שכירות.",
        "ru": "Знайте свои права перед подписанием договора аренды.",
    },
}


def main() -> None:
    db = get_db()
    doc_ref = db.collection("verbs").document(VERB_ID)
    doc = doc_ref.get()
    if not doc.exists:
        print(f"{VERB_ID} -- NOT FOUND")
        return

    existing = doc.to_dict()
    examples = list(existing.get("examples") or [])

    # Index 4 is the présent-indicatif question this script replaces --
    # verified against live data before writing this script.
    target_index = 4
    if target_index >= len(examples):
        print(f"  SKIPPED -- expected an example at index {target_index}, found {len(examples)}")
        return

    before = examples[target_index].get("dst")
    examples[target_index] = NEW_EXAMPLE
    print(f"  examples[{target_index}]: {before!r} -> {NEW_EXAMPLE['dst']!r}")

    doc_ref.update({"examples": examples, "updated_at": datetime.now(UTC).isoformat()})
    print("  OK -- updated")


if __name__ == "__main__":
    main()
