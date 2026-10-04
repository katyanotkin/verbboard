"""
Backfill condizionale and congiuntivo (presente, imperfetto) for existing Italian verbs.

Reads every Italian verb from Firestore, asks Gemini for ONLY the missing tense(s), and
merges them into `forms` (existing forms and examples are never touched). The verb's
presente/imperfetto/futuro are sent as context so the condizionale agrees with the futuro stem.

Usage (project root, needs GCP auth; uses Vertex AI Gemini, no Anthropic key):

    python -m tools.backfill_it_modes --dry-run
    python -m tools.backfill_it_modes
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import UTC, datetime
from typing import Any

import vertexai
from dotenv import load_dotenv
from google.cloud import firestore
from vertexai.generative_models import GenerationConfig, GenerativeModel

from core.settings import load_settings

load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

TARGET_TENSES = ("condizionale_presente", "congiuntivo_presente", "congiuntivo_imperfetto")
SLOTS = ("io", "tu", "lui", "noi", "voi", "loro")
MODEL = "gemini-2.5-flash"  # same model/provider as the Italian search-miss autogen path

SYSTEM = """\
You are an Italian conjugation generator. Return raw valid JSON only, no markdown, no prose.
Begin with `{`.

Schema (only the tenses listed under "Generate:"):
{
  "condizionale_presente":  { "io": "...", "tu": "...", "lui": "...", "noi": "...", "voi": "...", "loro": "..." },
  "congiuntivo_presente":   { "io": "...", "tu": "...", "lui": "...", "noi": "...", "voi": "...", "loro": "..." },
  "congiuntivo_imperfetto": { "io": "...", "tu": "...", "lui": "...", "noi": "...", "voi": "...", "loro": "..." }
}

Rules:
- Bare verb forms, same shape as the given "presente" (no subject pronoun, no "che", no "se").
- condizionale_presente = the verb's FUTURO stem + -ei, -esti, -ebbe, -emmo, -este, -ebbero; it must agree
  with the given "futuro" (essere -> sarei, avere -> avrei, andare -> andrei, potere -> potrei,
  volere -> vorrei). Never copy the imperfetto or the futuro.
- congiuntivo_presente: io, tu and lui are identical (sia, sia, sia; vada, vada, vada). Irregulars: essere
  (sia ... siamo, siate, siano), avere (abbia ... abbiamo, abbiate, abbiano), andare (vada ... andiamo,
  andiate, vadano), fare (faccia ... facciamo, facciate, facciano), potere (possa ... possiamo, possiate,
  possano), volere (voglia ... vogliamo, vogliate, vogliano), sapere (sappia), dare (dia ... diamo, diate,
  diano), stare (stia), dire (dica ... diciamo, diciate, dicano). Never copy the indicativo presente.
- congiuntivo_imperfetto: io and tu are identical. essere (fossi, fossi, fosse, fossimo, foste, fossero),
  avere (avessi ... aveste), andare (andassi ... andaste), fare (facessi ... faceste), dire (dicessi ...
  diceste), dare (dessi ... deste), stare (stessi ... steste); the voi form has a single s (-aste/-este/-iste).
  Never copy the indicativo imperfetto.
- If the given "imperativo" has a "lei" form, congiuntivo_presente.lui must equal it.
- Reflexive verbs keep the clitic per person (mi/ti/si/ci/vi/si), as the given "presente" does.
- Impersonal verbs fill only "lui" and leave other slots empty strings.
- Only return the tenses listed under "Generate:"."""


def _parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    return json.loads(text)


def _valid(tense: Any) -> bool:
    return isinstance(tense, dict) and any(isinstance(tense.get(s), str) and tense[s].strip() for s in SLOTS)


def run(project: str, dry_run: bool) -> None:
    db = firestore.Client(project=project)
    docs = list(db.collection("verbs").where("language", "==", "it").stream())
    todo = [d for d in docs if any(not (d.to_dict().get("forms") or {}).get(t) for t in TARGET_TENSES)]
    logger.info("%d Italian verbs, %d need backfill", len(docs), len(todo))
    if dry_run:
        for d in todo:
            logger.info("  %s", d.id)
        logger.info("DRY RUN -- no API calls or Firestore writes.")
        return

    vertexai.init(project=project, location=load_settings().gcp_region)
    model = GenerativeModel(MODEL)
    saved = failed = 0
    for doc in todo:
        data = doc.to_dict()
        forms = data.get("forms") or {}
        missing = [t for t in TARGET_TENSES if not forms.get(t)]
        context = {k: forms.get(k) for k in ("presente", "imperfetto", "futuro", "imperativo")}
        prompt = (
            f"Verb (infinitive): {data.get('lemma') or doc.id}\n"
            f"Existing forms: {json.dumps(context, ensure_ascii=False)}\n"
            f"Generate: {', '.join(missing)}"
        )
        try:
            reply = model.generate_content(
                f"{SYSTEM}\n\n{prompt}",
                generation_config=GenerationConfig(response_mime_type="application/json", temperature=0),
            )
            generated = _parse_json(reply.text)
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
    if not args.project:
        logger.error("GOOGLE_CLOUD_PROJECT is required")
        return
    run(args.project, args.dry_run)


if __name__ == "__main__":
    main()
