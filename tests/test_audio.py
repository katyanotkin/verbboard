from __future__ import annotations

import asyncio
import concurrent.futures

from fastapi.testclient import TestClient

from core.audio_service import build_hashed_audio_key
from core.audio_backend.base import AudioBackend
from core.models import VerbEntry


# ── shared fixtures ──────────────────────────────────────────────────────────

_EN_VERB_DATA = {
    "verb_id": "en_go",
    "language": "en",
    "lemma": "go",
    "rank": 1,
    "forms": {
        "base": "go",
        "past": "went",
        "past_participle": "gone",
        "present_3sg": "goes",
        "gerund": "going",
    },
    "examples": [{"dst": "I go to school every day.", "translations": {}}],
    "morph": None,
    "tags": None,
    "display_lemma": None,
    "display_forms": None,
}

_HE_VERB_DATA = {
    "verb_id": "he_lalechet",
    "language": "he",
    "lemma": "ללכת",
    "rank": 1,
    "forms": {},
    "morph": {"binyan": "פעל", "root": "ה-ל-כ"},
    "examples": [],
    "tags": None,
    "display_lemma": "ללכת",
    "display_forms": None,
}


class _StubBackend(AudioBackend):
    def exists(self, key: str) -> bool:
        return False

    def read_bytes(self, key: str) -> bytes:
        return b"stub-audio"

    def write_bytes(self, key: str, data: bytes) -> None:
        pass

    def list_keys(self, prefix: str):
        return iter([])


# ── audio endpoint: on-demand generation ────────────────────────────────────


def test_audio_cache_hit_skips_generation(client: TestClient, monkeypatch) -> None:
    ensure_called: list = []

    async def _fail_ensure(**kwargs):
        ensure_called.append(kwargs)

    monkeypatch.setattr("app.routes.audio.ensure_audio", _fail_ensure)
    monkeypatch.setattr(
        "app.routes.audio.read_audio_bytes",
        lambda **kw: b"cached-mp3",
    )

    form_key = build_hashed_audio_key("base", "go")
    resp = client.get(f"/audio/en/en_go/female/{form_key}.mp3")

    assert resp.status_code == 200
    assert ensure_called == []


def test_audio_miss_generates_and_returns_200(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
    called_with: list[dict] = []

    async def _capture_ensure(**kwargs):
        called_with.append(kwargs)

    monkeypatch.setattr("app.routes.audio.ensure_audio", _capture_ensure)
    monkeypatch.setattr("core.verb_loader.load_entry_by_id", lambda **kw: mock_verb)

    form_key = build_hashed_audio_key("base", "go")
    resp = client.get(f"/audio/en/en_go/female/{form_key}.mp3")

    assert resp.status_code == 200
    assert len(called_with) == 1
    assert called_with[0]["text"] == "go"
    assert called_with[0]["voice"] == "female"
    assert called_with[0]["language"] == "en"
    assert called_with[0]["verb_id"] == "en_go"


def test_audio_miss_example_generates_on_demand(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
    called_with: list[dict] = []

    async def _capture_ensure(**kwargs):
        called_with.append(kwargs)

    monkeypatch.setattr("app.routes.audio.ensure_audio", _capture_ensure)
    monkeypatch.setattr("core.verb_loader.load_entry_by_id", lambda **kw: mock_verb)

    example_text = "I go to school every day."
    form_key = build_hashed_audio_key("example_1", example_text)
    resp = client.get(f"/audio/en/en_go/male/{form_key}.mp3")

    assert resp.status_code == 200
    assert any(c["text"] == example_text for c in called_with)


def test_audio_miss_verb_not_found_returns_404(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr("core.verb_loader.load_entry_by_id", lambda **kw: None)

    form_key = build_hashed_audio_key("base", "go")
    resp = client.get(f"/audio/en/en_go/female/{form_key}.mp3")

    assert resp.status_code == 404


def test_audio_miss_unknown_form_key_returns_404(
    client: TestClient, monkeypatch, mock_verb: VerbEntry
) -> None:
    async def _noop(**kwargs):
        pass

    monkeypatch.setattr("app.routes.audio.ensure_audio", _noop)
    monkeypatch.setattr("core.verb_loader.load_entry_by_id", lambda **kw: mock_verb)

    resp = client.get("/audio/en/en_go/female/base_deadbeef00.mp3")
    assert resp.status_code == 404


# ── _warm_verb_audio ─────────────────────────────────────────────────────────


def _run_async(coro) -> None:
    """Run a coroutine in a worker thread with its own event loop.

    Playwright e2e tests leave a running loop in the main thread, so
    asyncio.run() and anyio runners both fail there. A fresh thread has
    no loop, so asyncio.run() works cleanly.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(asyncio.run, coro).result()


def test_warm_generates_both_voices(monkeypatch) -> None:
    from app.routes.admin_candidates import _warm_verb_audio

    called_voices: list[str] = []

    async def _capture(**kwargs):
        called_voices.append(kwargs["voice"])

    monkeypatch.setattr("core.audio_service.ensure_audio", _capture)

    _run_async(_warm_verb_audio(_StubBackend(), "en", _EN_VERB_DATA))

    assert "female" in called_voices
    assert "male" in called_voices


def test_warm_covers_all_forms_and_examples(monkeypatch) -> None:
    from app.routes.admin_candidates import _warm_verb_audio

    calls: list[dict] = []

    async def _capture(**kwargs):
        calls.append({"voice": kwargs["voice"], "text": kwargs["text"]})

    monkeypatch.setattr("core.audio_service.ensure_audio", _capture)

    _run_async(_warm_verb_audio(_StubBackend(), "en", _EN_VERB_DATA))

    female_texts = {c["text"] for c in calls if c["voice"] == "female"}
    # 5 form rows + 1 example = 6 per voice
    assert female_texts == {
        "go",
        "went",
        "gone",
        "goes",
        "going",
        "I go to school every day.",
    }
    assert len(calls) == 12  # 6 per voice × 2 voices


def test_warm_skips_no_audio_row_keys(monkeypatch) -> None:
    from app.routes.admin_candidates import _warm_verb_audio

    called_texts: list[str] = []

    async def _capture(**kwargs):
        called_texts.append(kwargs["text"])

    monkeypatch.setattr("core.audio_service.ensure_audio", _capture)

    _run_async(_warm_verb_audio(_StubBackend(), "he", _HE_VERB_DATA))

    assert "פעל" not in called_texts  # binyan must be skipped
    assert "ה-ל-כ" not in called_texts  # root must be skipped
    assert "ללכת" in called_texts  # infinitive must be included
