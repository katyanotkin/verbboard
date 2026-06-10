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

---

## TODO: test coverage gaps (from README/about page audit)

The README and about page document features that currently lack explicit regression tests.
Each item below is a candidate for a future unit or e2e test pass:

- **Focus filter** (`/learn`) — hide conjugation rows by gender (masculine/feminine) and
  number (singular/plural). Applies to Hebrew, Russian, and Spanish boards. No test
  verifies that the correct rows are hidden/shown based on active filter state.

- **Inline translations toggle** — when UI language differs from the verb language,
  example sentences show a translation button. No test covers the toggle interaction
  (button present, translation appears/hides on click, absent when languages match).

- **Cross-device sync merge on login** — local progress (seen/known verbs, practice
  badges) must merge automatically with server state when the user signs in. The merge
  logic in `progress_service.py` and the badge merge in `practice_loop.js` (keep longer
  list) are not covered by regression tests.
