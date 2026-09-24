from __future__ import annotations

import os

# Must be set before any import that calls load_settings()
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ.setdefault("ADMIN_SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("AUDIO_BUCKET", "test-bucket")

import sys  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import core.storage.firestore_db as firestore_db  # noqa: E402
from app.main import app  # noqa: E402
from core.audio_backend.base import AudioBackend  # noqa: E402
from core.models import Example, VerbEntry  # noqa: E402
from tests.fake_firestore import FakeFirestore  # noqa: E402


@pytest.fixture()
def fake_db(monkeypatch):
    """Opt-in in-memory Firestore fake (issue #8) -- request this explicitly
    in a test's signature to get a FakeFirestore instance with get_db()
    patched to return it.

    Patches both core.storage.firestore_db.get_db (the deferred-import call
    site used by e.g. session_tracker.py) and, by identity, every
    already-imported module's own `get_db` name if it's the same function
    object -- several modules (verb_repository.py, admin_feedback_service.py,
    and others) do `from core.storage.firestore_db import get_db` at module
    scope, so patching only the factory module misses them.

    NOT autouse: roughly 150 existing tests implicitly rely on a real (but
    doomed-to-fail against the test-only GOOGLE_CLOUD_PROJECT) Firestore call
    silently producing empty/not-found results, rather than mocking Firestore
    at all -- making this autouse broke all of them (see issue #8). New tests
    should opt in via this fixture instead of adding another one-off fake.
    """
    fake = FakeFirestore()
    real_get_db = firestore_db.get_db
    monkeypatch.setattr(firestore_db, "get_db", lambda: fake)
    for mod in list(sys.modules.values()):
        if mod is not None and getattr(mod, "get_db", None) is real_get_db:
            monkeypatch.setattr(mod, "get_db", lambda: fake)
    return fake


@pytest.fixture(autouse=True)
def _no_search_hit_writes(monkeypatch):
    """Keep search-route tests from incrementing real verb_search_hits counters.

    Many tests hit /search_verb for a real verb (e.g. "go") without mocking
    Firestore; the hit recorder would otherwise write to whatever project
    .env points at. Tests that assert on recording re-patch this name.
    """
    monkeypatch.setattr("app.routes.home.record_search_hit", lambda **kwargs: None)


class _StubAudioBackend(AudioBackend):
    def exists(self, key: str) -> bool:
        return False

    def read_bytes(self, key: str) -> bytes:
        return b""

    def write_bytes(self, key: str, data: bytes) -> None:
        pass

    def list_keys(self, prefix: str):
        return iter([])


@pytest.fixture()
def client(monkeypatch) -> TestClient:  # type: ignore[return]
    monkeypatch.setattr("app.main.create_audio_backend", lambda _: _StubAudioBackend())
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def mock_verb() -> VerbEntry:
    """Minimal English VerbEntry compatible with the English language plugin."""
    return VerbEntry(
        id="en_go",
        rank=1,
        lemma="go",
        forms={
            "base": "go",
            "past": "went",
            "past_participle": "gone",
            "present_3sg": "goes",
            "gerund": "going",
        },
        examples=[Example(dst="I go to school every day.")],
    )


async def noop_ensure_audio(**kwargs):  # type: ignore[return]
    """Async no-op replacement for ensure_audio to avoid real TTS/GCS calls."""
    return None
