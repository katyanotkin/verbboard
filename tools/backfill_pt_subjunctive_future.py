"""
Backfill the pt-BR futuro do subjuntivo (`forms.subjunctive_future`) plus one example for existing verbs.

The four forms are derived deterministically from each verb's stored preterite "eles" form (drop -am,
then +"", +"", +"mos", +"em": falaram -> falar/falar/falarmos/falarem, fizeram -> fizer..., foram -> for...,
"se levantaram" -> me levantar/se levantar/nos levantarmos/se levantarem). One example sentence with
en/es/ru/he translations comes from Gemini (Vertex), is hint-tagged against the new forms and appended
to `examples`. Existing forms and examples are never changed. Idempotent: a verb that already has
`subjunctive_future` is skipped. Dry run by default.

Usage (project root, needs GCP auth):

    PYTHONPATH=. .venv/bin/python -m tools.backfill_pt_subjunctive_future            # dry run
    PYTHONPATH=. .venv/bin/python -m tools.backfill_pt_subjunctive_future --execute
    PYTHONPATH=. .venv/bin/python -m tools.backfill_pt_subjunctive_future --verb-id pt_falar
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any

from google.api_core.exceptions import FailedPrecondition

from core.example_targets import tag_from_hint
from core.gemini_client import generate_gemini_text
from core.storage.firestore_db import get_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL = "gemini-2.5-flash"
_CLITICS = {"eu": "me", "ele": "se", "nos": "nos", "eles": "se"}

_PROMPT = """\
You write one example sentence for a Brazilian Portuguese (pt-BR) learner app.
Verb: {lemma}. Use EXACTLY ONE of these futuro do subjuntivo forms, spelled exactly like this:
  eu: {eu} | ele/ela/você: {ele} | nós: {nos} | eles/elas/vocês: {eles}
The sentence must be a natural pt-BR sentence where the form follows "quando", "se" or "assim que"
(e.g. "Quando eu puder, ligo para você."). The form must appear in the sentence exactly once as a
whole word. Use "você", never "tu". Keep it under 14 words. The sentence must make real-world sense
for this verb: choose a concrete, specific situation for it, and never use "me avise", "me diga" or "me ligue".
Return raw JSON only: {{"dst": "<sentence>", "form": "subjunctive_future.<eu|ele|nos|eles>",
"answer": "<the form as written in the sentence>", "translations": {{"en": "...", "es": "...", "ru": "...", "he": "..."}}}}
"""


def derive_forms(preterite_eles: str) -> dict[str, str] | None:
    """Deterministic futuro do subjuntivo from the preterite eles form; None if it does not fit."""
    parts = (preterite_eles or "").split()
    if not parts or not parts[-1].endswith("am") or len(parts[-1]) < 4:
        return None
    clitic = parts[:-1]
    if clitic not in ([], ["se"]):
        return None
    base = parts[-1][:-2]
    reflexive = clitic == ["se"]

    def with_clitic(slot: str, word: str) -> str:
        return f"{_CLITICS[slot]} {word}" if reflexive else word

    return {
        "eu": with_clitic("eu", base),
        "ele": with_clitic("ele", base),
        "nos": with_clitic("nos", base + "mos"),
        "eles": with_clitic("eles", base + "em"),
    }


def _generate_example(lemma: str, forms: dict[str, str]) -> dict[str, Any] | None:
    prompt = _PROMPT.format(lemma=lemma, **forms)
    for _attempt in range(2):
        try:
            data = json.loads(generate_gemini_text(MODEL, prompt, json_output=True))
        except Exception:
            logger.exception("generation failed for %s", lemma)
            time.sleep(2)
            continue
        if (
            isinstance(data, dict)
            and isinstance(data.get("translations"), dict)
            and isinstance(data.get("dst"), str)
            and isinstance(data.get("form"), str)
            and isinstance(data.get("answer"), str)
        ):
            return data
    return None


def build_example(lemma: str, verb_forms: dict[str, Any], new_forms: dict[str, str]) -> dict[str, Any] | None:
    raw = _generate_example(lemma, new_forms)
    if raw is None:
        return None
    merged = {**verb_forms, "subjunctive_future": new_forms}
    target = tag_from_hint("pt", raw.get("dst", ""), merged, raw.get("form", ""), raw.get("answer", ""))
    if target is None:
        return None
    translations = {
        k: v for k, v in raw["translations"].items() if k in ("en", "es", "ru", "he") and isinstance(v, str)
    }
    if set(translations) != {"en", "es", "ru", "he"}:
        return None
    return {"dst": raw["dst"], "translations": translations, "target": target}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--verb-id", default="")
    args = parser.parse_args()

    db = get_db()
    snapshots = [s for s in db.collection("verbs").where("language", "==", "pt").stream()]
    done = skipped = failed = 0
    for snap in sorted(snapshots, key=lambda s: s.to_dict().get("rank") or 0):
        data = snap.to_dict()
        if args.verb_id and snap.id != args.verb_id:
            continue
        forms = data.get("forms") or {}
        if not data.get("lemma"):
            logger.warning("%s: no lemma, skipped", snap.id)
            failed += 1
            continue
        if forms.get("subjunctive_future"):
            skipped += 1
            continue
        new_forms = derive_forms((forms.get("preterite") or {}).get("eles", ""))
        if new_forms is None:
            logger.warning(
                "%s: cannot derive from preterite.eles=%r", snap.id, (forms.get("preterite") or {}).get("eles")
            )
            failed += 1
            continue
        example = build_example(str(data.get("lemma")), forms, new_forms)
        logger.info("%s %s | %s", snap.id, new_forms, example["dst"] if example else "NO EXAMPLE")
        if example is None:
            failed += 1
            continue
        if args.execute:
            try:
                # Only this field of `forms`, and fail if the doc changed since it was read (admin regen,
                # example-target backfill): the examples array cannot be merged field-wise.
                snap.reference.update(
                    {
                        "forms.subjunctive_future": new_forms,
                        "examples": [*(data.get("examples") or []), example],
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    option=db.write_option(last_update_time=snap.update_time),
                )
            except FailedPrecondition:
                logger.warning("%s changed while generating; skipped, rerun to pick it up", snap.id)
                failed += 1
                continue
        done += 1
    print(f"{'written' if args.execute else 'dry run'}: ok={done} skipped={skipped} failed={failed}")


if __name__ == "__main__":
    main()
