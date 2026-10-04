"""
Backfill conditional, present subjunctive and imperfect subjunctive for existing Spanish verbs.

Reads every Spanish verb from Firestore, asks Claude for ONLY the missing tense(s), and
merges them into `forms` (existing forms and examples are never touched). The verb's
present/imperfect/future are sent as context so the conditional agrees with the future stem.

Usage (project root, needs GCP auth + ANTHROPIC_API_KEY in .env):

    python -m tools.backfill_es_modes --dry-run
    python -m tools.backfill_es_modes
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import anthropic
from dotenv import load_dotenv
from google.cloud import firestore

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TARGET_TENSES = ("conditional", "subjunctive_present", "subjunctive_imperfect")
SLOTS = ("yo", "tu", "el", "nos", "vosotros", "ellos")
MODEL = "claude-sonnet-4-6"

SYSTEM = """\
You are a Spanish (Spain) conjugation generator. Return raw valid JSON only, no markdown, no prose.
Begin with `{`.

Schema (only the tenses listed under "Generate:"):
{
  "conditional":           { "yo": "...", "tu": "...", "el": "...", "nos": "...", "vosotros": "...", "ellos": "..." },
  "subjunctive_present":   { "yo": "...", "tu": "...", "el": "...", "nos": "...", "vosotros": "...", "ellos": "..." },
  "subjunctive_imperfect": { "yo": "...", "tu": "...", "el": "...", "nos": "...", "vosotros": "...", "ellos": "..." }
}

Rules:
- Bare verb forms, same shape as the given "present" (no subject pronoun, no "que", no "si").
- conditional = the verb's FUTURE stem + -ía, -ías, -ía, -íamos, -íais, -ían; it must agree with the
  given "future" (tener -> tendría, hacer -> haría, poder -> podría, querer -> querría). Never copy the imperfect.
- subjunctive_present: derive from the yo form of the present (tengo -> tenga), keep stem changes
  (poder -> pueda ... podamos, podáis ... puedan; pedir -> pida ... pidamos); irregulars: ser (sea, seas, sea,
  seamos, seáis, sean), estar (esté, estés, esté, estemos, estéis, estén), ir (vaya ...), saber (sepa ...),
  haber (haya ...), dar (dé, des, dé, demos, deis, den). Never copy the indicative present.
- subjunctive_imperfect: the -ra form, built from the ellos form of the preterite (hacer -> hiciera;
  ser/ir -> fuera, fueras, fuera, fuéramos, fuerais, fueran; tener -> tuviera; poder -> pudiera). Write the
  accent on nosotros (compráramos). Never copy the preterite or the imperfect.
- Reflexive verbs keep their pronoun per person (me/te/se/nos/os/se), as the given "present" does.
- Impersonal verbs fill only "el" and leave other slots empty strings.
- Only return the tenses listed under "Generate:"."""


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


def _valid(tense: Any) -> bool:
    return isinstance(tense, dict) and any(isinstance(tense.get(s), str) and tense[s].strip() for s in SLOTS)


def run(project: str, api_key: str, dry_run: bool) -> None:
    db = firestore.Client(project=project)
    docs = list(db.collection("verbs").where("language", "==", "es").stream())
    todo = [d for d in docs if any(not (d.to_dict().get("forms") or {}).get(t) for t in TARGET_TENSES)]
    logger.info("%d Spanish verbs, %d need backfill", len(docs), len(todo))
    if dry_run:
        for d in todo:
            logger.info("  %s", d.id)
        logger.info("DRY RUN -- no API calls or Firestore writes.")
        return

    client = anthropic.Anthropic(api_key=api_key)
    saved = failed = 0
    for doc in todo:
        data = doc.to_dict()
        forms = data.get("forms") or {}
        missing = [t for t in TARGET_TENSES if not forms.get(t)]
        context = {k: forms.get(k) for k in ("present", "preterite", "imperfect", "future")}
        prompt = (
            f"Verb (infinitive): {data.get('lemma') or doc.id}\n"
            f"Existing forms: {json.dumps(context, ensure_ascii=False)}\n"
            f"Generate: {', '.join(missing)}"
        )
        try:
            reply = client.messages.create(
                model=MODEL,
                max_tokens=1024,
                temperature=0,
                system=SYSTEM,
                messages=[{"role": "user", "content": prompt}],
            )
            generated = _parse_json(reply.content[0].text)
        except Exception as exc:
            logger.warning("FAIL %-24s %s", doc.id, exc)
            failed += 1
            continue

        payload: dict[str, Any] = {}
        for tense in missing:
            if _valid(generated.get(tense)):
                payload[f"forms.{tense}"] = {s: generated[tense].get(s, "") for s in SLOTS}
        if not payload:
            logger.warning("EMPTY %-24s nothing usable returned", doc.id)
            failed += 1
            continue
        payload["updated_at"] = datetime.now(UTC).isoformat()
        db.collection("verbs").document(doc.id).update(payload)
        logger.info("SAVED %-24s %s", doc.id, [k.split(".", 1)[1] for k in payload if k.startswith("forms.")])
        saved += 1
    logger.info("Done: %d saved, %d failed", saved, failed)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not args.project or (not api_key and not args.dry_run):
        logger.error("GOOGLE_CLOUD_PROJECT and (unless --dry-run) ANTHROPIC_API_KEY are required")
        return
    run(args.project, api_key, args.dry_run)


if __name__ == "__main__":
    main()
