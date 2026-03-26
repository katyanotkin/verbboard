# Agent guidance (VerbBoard)

Use this file when editing or extending this repository.

## Environment

- **Python:** 3.12

## Stack

- **Web:** FastAPI (`app/main.py`, routers under `app/routes/`)

## Architecture

- **Handlers:** Keep route handlers thin—parse/validate HTTP, call into cohesive modules, return responses.
- **Logic:** Put non-trivial behavior in dedicated modules (e.g. something like `core/*_service.py` or small helpers colocated with the domain), not bloated inside `APIRouter` functions.

## Lexicon / verb data

- **Do not break** the existing **file-based** flow: runtime reads generated lexicons from `runtime/data/<language>/lexicon.json` (see `core/paths.py`, `core/lexicon.py`, `load_lexicon`).
- Preload via `lexicon_store` exists for startup/health; `/learn` and other paths may read lexicons from disk per request—preserve that contract unless the project explicitly migrates it.

## Style

- **Names:** Prefer explicit, readable variable and function names over abbreviations.
- **Design:** Avoid overengineering—prefer the smallest change that fits the codebase and the rules above.
