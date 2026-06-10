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
- Business logic in `core/` (render, search, progress, settings)
- Jinja2 template output (key HTML, data attributes, filter buttons)
- Language plugin correctness (board shape, row keys)

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

Pre-commit hook runs all unit tests on every commit.

---

### 2. E2E tests — `tests/e2e/`

Browser-driven. Use **Playwright** (Chromium via `playwright.sync_api`) controlled by **pytest-playwright**.

Each test gets:
- A real FastAPI server started on a random free port in a background thread (`live_server_url` session fixture in `tests/e2e/conftest.py`)
- A fresh Chromium page (`page` fixture, function-scoped)

The live server connects to the real Firestore, so tests that need verb data skip gracefully when Firestore is empty (`pytest.skip`). This makes them safe to run locally without credentials and safe in CI with credentials.

`ensure_audio` is patched to a no-op in the e2e conftest so tests never call TTS.

What they cover:
- JS-rendered UI (Playwright waits for JS execution, so server-rendered HTML alone is not enough)
- Navigation flows: `ui_language` propagation through JS-built hrefs, back-button roundtrips
- Client-side interaction: translation toggle click, badge merge logic via `page.evaluate`
- State retention across page loads

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

For pre-commit (unit only), parallelization is not used — the hook runs `pytest` directly without `-n` so failures are easy to read.

---

## Testing Principles

- Mock Firestore, TTS/audio, Anthropic/model calls, and external services in unit tests
- Do not hit real GCP or generate real audio in unit or e2e tests
- Keep unit tests deterministic and fast
- Avoid brittle HTML/CSS assertions; prefer status codes, redirects, payload shape, key rendered text
- E2E tests that need Firestore data must skip gracefully when the data is absent
- Pure algorithmic JS (merge rules, preference guards) is tested via `page.evaluate` -- no Firebase auth needed
- Async Playwright tests must run in a `ThreadPoolExecutor` worker thread to avoid asyncio loop conflicts (see `tests/test_audio.py`)

---

## Covered Features

- **Focus filter** — `tests/test_focus_filter_render.py`: 18 unit tests covering
  `data-gender`/`data-number` attribute rendering for HE/RU/ES/EN, and filter button
  panel presence by language.

- **Inline translations toggle** — `tests/e2e/test_translation_toggle.py`: 4 e2e tests
  covering show/hide class toggle, button text swap, and absence when ui_language
  matches verb language.

- **Badge merge (cross-device sync)** — `tests/e2e/test_badge_merge.py`: 7 e2e tests
  documenting the merge contract (server wins when longer or tied, local wins when
  strictly longer, edge cases for empty arrays).

- **ui_language propagation** — `tests/e2e/test_ui_lang_in_verb_links.py`: 6 e2e tests
  covering JS-built verb hrefs, `return_to` encoding, back-button roundtrip, and
  bottom-nav back link.

- **Verbs display batch** — `tests/test_verbs_display_batch.py`: 7 unit tests covering
  `window.VB_DISPLAY_BATCH` embed from Settings and show-more wrapper presence.
