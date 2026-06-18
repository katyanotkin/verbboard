# tools/

Admin and maintenance scripts. Run from the project root unless noted. All
Firestore tools need GCP auth (`gcloud auth application-default login`).
Destructive operations default to dry-run; pass `--apply` or `--execute` to
write.

---

## Audit / Inspection

`check_nikud.py` — Audit Hebrew verbs in Firestore for nikud (vowel diacritics)
coverage in the `forms` field.
```
python -m tools.check_nikud
python -m tools.check_nikud --missing   # only verbs missing nikud
```

`check_plugins.py` — Verify all four language plugins (en/ru/he/es) register
correctly against `core/registry`.
```
python -m tools.check_plugins
```

`check_lexicon.py` — Validate a single lexicon JSON file against required
schema (keys, Hebrew binyanim, non-empty strings, etc.).
```
python -m tools.check_lexicon runtime/data/he/lexicon.json
```

`check_all_lexicons.py` — Run `check_lexicon` against every `runtime/data/*/lexicon.json`.
```
python tools/check_all_lexicons.py
```

`check_template.py` — Verify `app/templates/board.html` exposes all required
Jinja2 context variables.
```
python tools/check_template.py
```

`audit_audio.py` — Find missing GCS audio blobs and flag size anomalies using
a linear fit (size vs. text length) per language/voice.
```
python -m tools.audit_audio --language all
python -m tools.audit_audio --language he --suspects --no-missing
GOOGLE_CLOUD_PROJECT=knotmem26 AUDIO_BUCKET=verbboard-audio-prod \
    python -m tools.audit_audio --language ru --suspects --missing-csv out.csv
```

`audit_examples.py` — Inspect example sentence quality in lexicon JSON: banned
patterns, strategy-object mismatches, form presence.
```
python -m tools.audit_examples --language ru
python -m tools.audit_examples --language all --fail-on-warning
```

`audit_hebrew_transliterations.py` — Check that Hebrew Firestore document IDs
match the transliteration produced by `build_storage_verb_id`. Accepts
`--execute` to migrate mismatched IDs.
```
python -m tools.audit_hebrew_transliterations
python -m tools.audit_hebrew_transliterations --execute
```

`audit_ru_firestore_aspect_forms.py` — Report Russian verbs where aspect and
present/future form slots are inconsistent (e.g., perfective with a `present`
slot).
```
python -m tools.audit_ru_firestore_aspect_forms
```

`audit_verb_id_collisions.py` — Detect verbs whose generated storage ID
collides with another verb, or whose canonical lemma is duplicated.
```
python -m tools.audit_verb_id_collisions
```

---

## Generation / Import

`bulk_generate.py` — Generate multiple verbs via Anthropic Message Batches API.
Reads one lemma per line, skips existing verbs and candidates, stores results as
candidates. Requires `ANTHROPIC_API_KEY` in `.env`.
```
python -m tools.bulk_generate --language es --input es_verbs.txt
python -m tools.bulk_generate --language ru --input ru_verbs.txt --dry-run
```

`firestore_import.py` — Import lexicon JSON from `runtime/data/` into
Firestore. Use `--clear` to wipe the collection first.
```
python -m tools.firestore_import
python -m tools.firestore_import --language he --limit-per-language 10
python -m tools.firestore_import --clear
```

`generate_lexicon.py` — Build `runtime/data/{lang}/lexicon.json` from the
source catalog in `runtime/data_src/`. Used before `firestore_import` when
backfilling from source.
```
python -m tools.generate_lexicon --language ru
python -m tools.generate_lexicon --language all
```

`generate_icons.py` — Render PWA icons from `app/static/snail.svg` at all
required sizes (48/72/96/144/192/512px) plus a maskable 512px variant. Requires
`cairosvg`.
```
python tools/generate_icons.py
```

---

## Backfill / Migration

`regen_forms_bulk.py` — Call the `regen_forms` admin API for each verb ID
supplied via stdin or `--input`. Designed to pair with `check_nikud --missing`.
Requires a running server (local by default; `--base-url` for stage/prod).
```
python -m tools.check_nikud --missing | python -m tools.regen_forms_bulk
python -m tools.regen_forms_bulk --input missing-nikud.csv \
    --base-url https://verbboard-stage.example.com
```

`backfill_translations.py` — Fill missing `Example.translations` keys for all
verbs in Firestore. Safe to re-run (only writes missing keys). Requires
`ANTHROPIC_API_KEY`.
```
python -m tools.backfill_translations --language ru
python -m tools.backfill_translations --language all --dry-run
python -m tools.backfill_translations --language en --target-lang ru
```

`backfill_es_tenses.py` — Add missing imperfect/future/imperative tense slots
to existing Spanish verbs via Anthropic Message Batches. Never overwrites
present or preterite. Requires `ANTHROPIC_API_KEY`.
```
python -m tools.backfill_es_tenses
python -m tools.backfill_es_tenses --dry-run
python -m tools.backfill_es_tenses --collection verb_candidates
```

`backfill_es_vosotros.py` — Add missing `vosotros` conjugation slot to all
four tenses (present/preterite/imperfect/future) for existing Spanish verbs via
Anthropic Message Batches. Only writes `forms.<tense>.vosotros`; all other
fields are left untouched. Requires `ANTHROPIC_API_KEY`.
```
python -m tools.backfill_es_vosotros
python -m tools.backfill_es_vosotros --dry-run
python -m tools.backfill_es_vosotros --collection verb_candidates
```

`fix_ru_perfective_form_slots.py` — Remove erroneous `present` form slots from
Russian perfective verbs in Firestore. Dry-run by default.
```
python -m tools.fix_ru_perfective_form_slots
python -m tools.fix_ru_perfective_form_slots --apply
```

`migrate_pair_to_lemma.py` — Convert `morph.pair` from latin verb IDs
(e.g. `ru_smotret`) to Cyrillic lemmas (e.g. `смотреть`) for all Russian verbs.
Dry-run by default; pass `--apply` to write.
```
python tools/migrate_pair_to_lemma.py
python tools/migrate_pair_to_lemma.py --apply
```

---

## Audio

`cache_audio.py` — Pre-warm TTS audio for a language and write to one or more
GCS buckets in a single TTS pass. Requires GCP auth and `GOOGLE_CLOUD_PROJECT`.
```
python -m tools.cache_audio --language he \
    --bucket verbboard-audio-stage --bucket verbboard-audio-prod
GOOGLE_CLOUD_PROJECT=knotmem26 AUDIO_BUCKET=verbboard-audio-prod \
    python -m tools.cache_audio --language all
python -m tools.cache_audio --language ru --voice female --dry-run
```

`clean_audio.py` — Delete unhashed audio blobs (old format: `present_1s.mp3`)
from GCS, keeping only hashed blobs (`present_1s_abc123def4.mp3`). Dry-run by
default.
```
python -m tools.clean_audio --language he \
    --project knotmem26 --bucket verbboard-audio-stage
python -m tools.clean_audio --language all --execute \
    --project knotmem26 --bucket verbboard-audio-stage
```
