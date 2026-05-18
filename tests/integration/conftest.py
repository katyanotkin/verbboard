from __future__ import annotations

# ---------------------------------------------------------------------------
# Integration test fixtures.
#
# These tests make real HTTP requests against a live server (local, stage,
# or prod).  They are skipped via pytestmark in the test file itself
# (not via an autouse fixture) so they cannot accidentally skip the whole
# pytest session.
#
# Env vars read here:
#   PROGRESS_TEST_BASE_URL  - target server (required to run these tests)
#   PROGRESS_TEST_TOKEN     - Bearer token sent with every authenticated
#                             request (default: "local-dev")
#
# No fixture names here overlap with tests/conftest.py.
# Root conftest provides: client, mock_verb.
# This conftest provides:  live_base_url, live_auth_headers, live_verb_id.
# ---------------------------------------------------------------------------
import os
import uuid

import pytest


@pytest.fixture(scope="session")
def live_base_url() -> str:
    return os.environ["PROGRESS_TEST_BASE_URL"].rstrip("/")


@pytest.fixture(scope="session")
def live_auth_headers() -> dict[str, str]:
    token = os.getenv("PROGRESS_TEST_TOKEN", "local-dev")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def live_verb_id() -> str:
    """Unique synthetic verb ID per test to avoid Firestore collisions."""
    return f"en_pytest_{uuid.uuid4().hex[:10]}"
