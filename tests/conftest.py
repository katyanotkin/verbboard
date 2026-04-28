from __future__ import annotations

import os

# Must be set before any import that calls load_settings()
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("AUDIO_BACKEND", "local")
os.environ.setdefault("VERB_DATA_SOURCE", "local")

# Stub out lexicon preload before app.main is imported, so the startup hook
# does not try to read missing local lexicon files.
from core.lexicon import lexicon_store  # noqa: E402

lexicon_store.preload_all = lambda: None  # type: ignore[method-assign]

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from core.models import Example, VerbEntry  # noqa: E402


@pytest.fixture()
def client() -> TestClient:  # type: ignore[return]
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
