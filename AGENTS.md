# Agent guidance (VerbBoard)

Use this file when editing or extending this repository.

## Environment

- **Python:** 3.12

## Stack

- **Web:** FastAPI (`app/main.py`, routers under `app/routes/`)

## Architecture

- **Handlers:** Keep route handlers thin—parse/validate HTTP, call into cohesive modules, return responses.
- **Logic:** Put non-trivial behavior in dedicated modules (e.g. something like `core/*_service.py` or small helpers colocated with the domain), not bloated inside `APIRouter` functions.

## Verb data

- Runtime (stage/prod) reads all verb data from **Firestore**. `runtime/data/<language>/lexicon.json` files are retained only for local development and Firestore import/backfill workflows — they are not read at runtime.

## Style

- **Names:** Prefer explicit, readable variable and function names over abbreviations.
- **Design:** Avoid overengineering—prefer the smallest change that fits the codebase and the rules above.
