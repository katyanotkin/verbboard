## Testing Strategy

Focus on regression testing of core VerbBoard behavior, not implementation details.

All tests live under `/tests` and use `pytest`.

### Core areas to cover

- Search flows:
  - hit → `/learn`
  - miss → `demand_signal`
- Demand logging (`demand_signal`)
- Feedback submission and poll handling
- Admin feedback summaries (poll + device mix)
- `/learn` behavior:
  - default verb
  - valid `verb_id`
  - unknown `verb_id` → 404
  - candidate preview
- Device type detection
- `/health`

### Testing principles

- Mock Firestore, TTS/audio, Anthropic/model calls, and external services
- Do not hit real GCP or generate real audio
- Keep tests deterministic and fast
- Avoid brittle HTML/CSS assertions
- Prefer validating:
  - status codes
  - redirects
  - payload shape
  - key rendered text
  - service logic

---

## Test Layers

### 1. Regression tests (local)

- Run with `pytest`
- Safe for local development and pre-commit
- Fully mocked environment

Commands:
PYTHONPATH=. pytest -q tests
PYTHONPATH=. pytest -q tests/test_recommendation_regression.py


---

### 2. Smoke tests (runtime)

- Run via `scripts/smoke.py`
- Validate a running service over HTTP
- Can target local, stage, or prod
- Not part of pre-commit (may depend on live services)

Commands:
python scripts/smoke.py http://127.0.0.1:8001

make smoke-prod


---

## Notes

- Regression tests protect product behavior
- Smoke tests validate deployment correctness
- Keep the two layers separate, but consistent in what they verify
- Expanding smoke coverage (e.g. more endpoints) is encouraged, as long as it stays lightweight
