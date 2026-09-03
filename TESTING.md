## Testing Strategy

Focus on regression testing of core VerbBoard behavior, not implementation details.

All tests live under `tests/` and run with `pytest`.

---

## Test Layers

### 1. Unit tests — `tests/*.py`

Fast, fully offline. No browser, no Firestore, no real audio.

External dependencies are replaced by stubs in `tests/conftest.py`:
- Firestore replaced with an in-memory `FakeDB`
- `ensure_audio` no-ops (no TTS calls)
- Anthropic/Gemini clients never called

What they cover:
- HTTP handler behavior (status codes, redirects, rendered text)
- Business logic in `core/` (render, search, progress, settings, editions, entitlements)
- Jinja2 template output (key HTML, data attributes, filter buttons)
- Language plugin correctness (board shape, row keys)
- Pure algorithmic logic that has a JS mirror (spaced-repetition Leitner box transitions, badge merge) — parity with the JS implementation is enforced here, not in e2e

Run:
```
PYTHONPATH=. pytest --ignore=tests/e2e --ignore=tests/integration -q
```

Parallel (safe — each worker is a separate process with its own stubs):
```
PYTHONPATH=. pytest --ignore=tests/e2e --ignore=tests/integration -n auto
```
Or via Makefile:
```
make test-unit-fast
```

Pre-commit hook runs the full test suite (unit + e2e) on every commit.

---

### 2. E2E tests — `tests/e2e/`

Browser-driven. Use **Playwright** (Chromium via `playwright.sync_api`) controlled by **pytest-playwright**.

Each test gets:
- A real FastAPI server started on a random free port in a background thread (`live_server_url` session fixture in `tests/e2e/conftest.py`)
- A fresh Chromium page (`page` fixture, function-scoped)

The live server connects to the real Firestore, so tests that need verb data skip gracefully when Firestore is empty (`pytest.skip`). This makes them safe to run locally without credentials and safe in CI with credentials.

`ensure_audio` is patched to a no-op in the e2e conftest so tests never call TTS.

The `live_server_url` session fixture also fires warm-up requests to `/`, `/verbs?language=en`, and `/verbs?language=ru` after server startup to prime Firestore caches before the first test runs.

What they cover:
- JS-rendered UI (Playwright waits for JS execution, so server-rendered HTML alone is not enough)
- Navigation flows: `ui_language` propagation through JS-built hrefs, back-button roundtrips
- Client-side interaction: translation toggle click
- State retention across page loads

Note: not every algorithmic-looking JS rule needs a browser test — badge merge logic, for example, is a pure function and is unit-tested directly in Python (`tests/test_badge_merge.py`) rather than driven through Playwright. Reach for e2e when the thing under test genuinely requires a rendered page or real browser JS execution; reach for a unit test with a `page.evaluate` fallback when it doesn't.

Run (sequential):
```
PYTHONPATH=. pytest tests/e2e -v
```

Run against a deployed service instead of local:
```
E2E_BASE_URL=https://stage.verbboard.com PYTHONPATH=. pytest tests/e2e -v
```

Parallel (safe — each worker starts its own server on a different port):
```
PYTHONPATH=. pytest tests/e2e -n 2 -v
```
Or via Makefile:
```
make test-e2e-parallel
```

**Playwright install** (first time):
```
playwright install chromium
```

---

### 3. Integration tests — `tests/integration/`

Hit the real Firestore. Use the same credentials as the running app (ADC or `GOOGLE_APPLICATION_CREDENTIALS`).

Run sequentially (shared Firestore state; parallel workers would race):
```
PYTHONPATH=. pytest tests/integration -v
```

Not part of pre-commit. Run manually or in CI with credentials.

---

### 4. Smoke tests — `scripts/smoke.py`, `scripts/smoke_nav.py`

HTTP-level checks against a running service. No pytest, no browser.

Target local, stage, or prod:
```
python scripts/smoke.py http://127.0.0.1:8001
python scripts/smoke_nav.py https://stage.verbboard.com
make smoke-prod
```

Used in the `gcp-promote-stage-to-prod` pipeline to validate stage before promoting the image.

---

## Parallelization

| Layer | Tool | Safe to parallelize? | Command |
|---|---|---|---|
| Unit | pytest-xdist | Yes — no shared state | `-n auto` |
| E2E | pytest-xdist | Yes — each worker gets its own server port and browser | `-n 2` |
| Integration | — | No — shared Firestore; run sequentially | (none) |
| Smoke | — | Not applicable (single HTTP script) | — |

`pytest-xdist` is declared in `pyproject.toml` under `[dependency-groups] dev` and is available in `.venv`.

For pre-commit, parallelization is not used — the hook runs `pytest` directly without `-n` so failures are easy to read. If e2e tests time out in the hook, run them separately against stage (`E2E_BASE_URL=https://stage.verbboard.com pytest tests/e2e -n 2`).

---

## Testing Principles

- Mock Firestore, TTS/audio, Anthropic/model calls, and external services in unit tests
- Do not hit real GCP or generate real audio in unit or e2e tests
- Keep unit tests deterministic and fast
- Avoid brittle HTML/CSS assertions; prefer status codes, redirects, payload shape, key rendered text
- E2E tests that need Firestore data must skip gracefully when the data is absent
- Pure algorithmic JS (merge rules, preference guards, Leitner box transitions) is tested via a Python mirror function plus a Node-subprocess parity check against the real JS — not via a browser
- Async Playwright tests must run in a `ThreadPoolExecutor` worker thread to avoid asyncio loop conflicts (see `tests/test_audio.py`)

---

## Covered Features

- **Focus filter** — `tests/test_focus_filter_render.py`: unit tests (parametrized) covering
  `data-gender`/`data-number` attribute rendering for HE/RU/ES/EN, and filter button
  panel presence by language.

- **Inline translations toggle** — `tests/e2e/test_translation_toggle.py`: e2e tests
  covering show/hide class toggle, button text swap, and absence when ui_language
  matches verb language.

- **Badge merge (cross-device sync)** — `tests/test_badge_merge.py`: 7 unit tests
  documenting the merge contract (server wins when longer or tied, local wins when
  strictly longer, edge cases for empty arrays). Pure-function logic — moved out of
  `tests/e2e/` since it needs no browser.

- **ui_language propagation** — `tests/e2e/test_ui_lang_in_verb_links.py`: e2e tests
  covering JS-built verb hrefs, `return_to` encoding, back-button roundtrip, and
  bottom-nav back link.

- **Verbs display batch** — `tests/test_verbs_display_batch.py`: 7 unit tests covering
  `window.VB_DISPLAY_BATCH` embed from Settings and show-more wrapper presence.

- **Practice skip audio gate** -- `tests/e2e/test_practice_skip_audio.py`: e2e tests covering
  the audio gate on both Skip and Next, `practice_min_plays` preference for numeric
  and `all` modes, and warn-element content. Specifically verify
  that Skip is blocked without listening and unblocked after enough plays -- enforcing that
  users must listen or abandon, not skip through an entire session unheard.

- **Spaced repetition (Leitner box)** — `tests/test_srs_merge.py`: unit tests on
  `leitner_next_box()` (promotion/demotion/cap rules) plus `test_srs_js_python_parity`,
  which runs a shared case table through Python and a Node subprocess and diffs the
  output against `app/static/srs.js`'s `nextBox()` — the two implementations are not
  allowed to drift silently. Also covers `getDueVerbIds()` due-date filtering.

- **Editions** — `tests/test_editions.py`: unit tests on `active_study_plugins()` /
  `resolve_study_language()` / `default_study_languages()` covering free-vs-Plus
  language sets and registry order preservation.

- **Entitlements** — `tests/test_entitlements.py`: unit tests on `can_study()` /
  `has_plus_entitlement()` / `requires_entitlement()`, including cache TTL behavior
  and fail-open-on-Firestore-error semantics.

- **Entitlement gate wiring** — `tests/test_entitlement_gate.py`: integration-style
  unit tests (TestClient) covering the gate as applied to `/learn`, `/verbs`,
  `/api/verbs`, `/audio`, `/search_verb[_by_lang]`, and `/api/preferences` —
  anonymous/unentitled/entitled paths, redirect vs 403 behavior per route.

- **Admin entitlement grant/revoke page** — `tests/test_admin_entitlements.py`:
  unit tests on `/admin/entitlements` covering uid/email lookup, grant, status
  validation, and admin-auth requirement.
