#!/usr/bin/env bash
# Pre-commit pytest hook: runs e2e tests against local-run if it is up,
# skips e2e entirely when no local server is detected.
set -a
source .env 2>/dev/null
set +a

PORT=${HOST_PORT:-8001}

if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    E2E_BASE_URL="http://localhost:${PORT}" PYTHONPATH=. .venv/bin/pytest -q -x --tb=short tests/
else
    echo ">>> local-run not detected on port ${PORT} -- skipping e2e (run: make local-run)"
    PYTHONPATH=. .venv/bin/pytest -q -x --tb=short --ignore=tests/e2e tests/
fi
