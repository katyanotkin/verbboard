from __future__ import annotations

import importlib
import os
import sys

# Must be set before any import that calls load_settings()
os.environ.setdefault("ADMIN_SECRET", "test-secret")
os.environ.setdefault("ADMIN_SESSION_SECRET", "test-session-secret")
os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")
os.environ.setdefault("AUDIO_BUCKET", "test-bucket")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import core.storage.firestore_db as firestore_db  # noqa: E402
import core.verb_loader as verb_loader  # noqa: E402
from app.main import app  # noqa: E402
from core.audio_backend.base import AudioBackend  # noqa: E402
from core.models import Example, VerbEntry  # noqa: E402
from tests.fake_firestore import FakeFirestore  # noqa: E402


@pytest.fixture(autouse=True)
def _no_real_firestore(request, monkeypatch):
    """Guard: no unit test may reach the real Firestore project (issue #8).

    .env points GOOGLE_CLOUD_PROJECT at the live project and valid ADC
    credentials exist on dev machines, so a test that forgot to mock
    Firestore used to read/write live data (search tests once incremented
    real verb_search_hits counters), with every writer's `except Exception`
    hiding it.

    core.storage.firestore_db.get_db() lazily builds a singleton client in
    the module global `_db`. Pre-seeding that global with an in-memory
    FakeFirestore covers every import style (deferred or module-level
    `from ... import get_db`, present or future) with no identity walk, and
    unlike raising, lets code that expects "empty / not found" keep working.
    Tests that need to inspect state request `fake_db`, which returns this
    same instance. Tests that patch get_db themselves still win.

    tests/e2e runs a real in-process server against the live project on
    purpose, so it is exempt; tests/integration talks HTTP only.
    """
    fake = FakeFirestore()
    request.node._vb_fake_db = fake
    if "/tests/e2e/" in str(request.node.fspath).replace("\\", "/"):
        return
    monkeypatch.setattr(firestore_db, "_db", fake)
    # The process-wide verb list cache would otherwise carry one test's
    # (fake) catalog into the next.
    monkeypatch.setattr(verb_loader, "_ENTRIES_CACHE", {})


@pytest.fixture()
def fake_db(request, _no_real_firestore):
    """The per-test in-memory Firestore fake (issue #8) that the autouse
    `_no_real_firestore` guard already installed as the process client.
    Request it to seed or inspect state.
    """
    return request.node._vb_fake_db


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


def seed_spanish_verb(fake) -> None:
    """Put one minimal Spanish verb into a FakeFirestore `verbs` collection."""
    fake.collection("verbs").document("es_hablar").set(
        {
            "language": "es",
            "verb_id": "es_hablar",
            "lemma": "hablar",
            "rank": 1,
            "forms": {"infinitive": "hablar"},
            "examples": [{"dst": "Yo hablo con ella."}],
            "lemma_translations": {"en": "to speak"},
        }
    )


def resolve_dotted_target(dotted_path: str):
    """Split "pkg.mod.name" into (module, attribute name, original object).

    Raises AttributeError/ImportError-derived errors with a clear message if
    the path does not resolve.
    """
    module_path, _, attribute_name = dotted_path.rpartition(".")
    if not module_path:
        raise ValueError(f"patch target {dotted_path!r} must be a dotted 'module.attribute' path")
    module = importlib.import_module(module_path)
    if not hasattr(module, attribute_name):
        raise AttributeError(
            f"patch target {dotted_path!r}: module {module_path!r} has no attribute {attribute_name!r}"
        )
    return module, attribute_name, getattr(module, attribute_name)


def modules_holding_same_object(dotted_path: str) -> list[tuple[str, str]]:
    """(module name, attribute name) of every loaded app.*/core.* module other
    than the defining one that binds the very same object as `dotted_path`."""
    module, attribute_name, original = resolve_dotted_target(dotted_path)
    holders: list[tuple[str, str]] = []
    for module_name, candidate in list(sys.modules.items()):
        if candidate is None or candidate is module:
            continue
        if not (module_name.startswith("app.") or module_name.startswith("core.")):
            continue
        for name, value in list(vars(candidate).items()):
            if value is original:
                holders.append((module_name, name))
    return holders


def patch_everywhere(monkeypatch, dotted_path: str, replacement) -> None:
    """Patch `dotted_path` in its defining module AND in every loaded app.*/core.*
    module that holds the same object under any name (issue #58).

    A plain monkeypatch of the defining module silently stops applying the
    moment a consumer does a module-scope `from x import name`; this patches
    every copy so the test is independent of the consumer's import style.
    Raises if the path does not resolve.
    """
    module, attribute_name, original = resolve_dotted_target(dotted_path)
    monkeypatch.setattr(module, attribute_name, replacement)
    for holder_name, name in modules_holding_same_object(dotted_path):
        monkeypatch.setattr(sys.modules[holder_name], name, replacement)
