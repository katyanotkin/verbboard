"""Tests for core/tts.py's tts_to_mp3() retry-with-backoff behavior.

Edge TTS (edge_tts.Communicate.save) is a free, unofficial API that
intermittently drops/resets connections. tts_to_mp3() retries up to
_MAX_TTS_ATTEMPTS times with a short backoff, and removes any truncated
output file left behind by a failed attempt so it can't later pass the
size-based cache-hit check and be served as complete audio forever.

Playwright e2e tests leave a running asyncio loop in the main thread, so
async coroutines here are run in a worker thread with their own fresh loop
(same pattern as tests/test_audio.py's _run_async).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from pathlib import Path

import pytest

import core.tts as tts_module


def _run_async(coro):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


class _FakeCommunicate:
    """Stand-in for edge_tts.Communicate. Fails the first `fail_times` calls
    (across all instances -- edge_tts.Communicate is re-instantiated per
    attempt, so shared class-level state models the real retry loop), then
    writes a valid-size file."""

    fail_times: int = 0
    calls: list[str] = []

    def __init__(self, text: str, voice: str, rate: str) -> None:
        self.text = text

    async def save(self, path: str) -> None:
        _FakeCommunicate.calls.append(path)
        attempt_index = len(_FakeCommunicate.calls)
        if attempt_index <= _FakeCommunicate.fail_times:
            # Simulate edge_tts writing a truncated file before the
            # connection drops mid-stream.
            Path(path).write_bytes(b"x" * 10)
            raise RuntimeError("connection reset")
        Path(path).write_bytes(b"x" * 3000)


class _AlwaysFailCommunicate(_FakeCommunicate):
    async def save(self, path: str) -> None:
        _FakeCommunicate.calls.append(path)
        Path(path).write_bytes(b"x" * 10)
        raise RuntimeError("connection reset")


class _MustNotBeCalledCommunicate:
    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("edge_tts.Communicate must not be constructed on a cache hit")


@pytest.fixture(autouse=True)
def _fast_backoff(monkeypatch):
    """Skip the real sleep durations so retry tests run instantly."""
    monkeypatch.setattr(tts_module, "_RETRY_BACKOFF_SECONDS", (0, 0))


@pytest.fixture(autouse=True)
def _reset_fake_calls():
    _FakeCommunicate.calls = []
    _FakeCommunicate.fail_times = 0
    yield
    _FakeCommunicate.calls = []
    _FakeCommunicate.fail_times = 0


def test_retries_then_succeeds(tmp_path, monkeypatch) -> None:
    """Fails on the first 2 attempts, succeeds on the 3rd (within budget)."""
    _FakeCommunicate.fail_times = 2
    monkeypatch.setattr(tts_module.edge_tts, "Communicate", _FakeCommunicate)

    out_path = tmp_path / "out.mp3"
    _run_async(tts_module.tts_to_mp3("hello", out_path, "en-US-JennyNeural"))

    assert len(_FakeCommunicate.calls) == 3
    assert out_path.exists()
    assert out_path.stat().st_size > 2000


def test_exhausts_all_attempts_raises_and_cleans_up(tmp_path, monkeypatch) -> None:
    """All _MAX_TTS_ATTEMPTS attempts fail: raises, and the truncated file
    from the last failed attempt is removed (never left behind to falsely
    pass the size-based cache-hit check)."""
    monkeypatch.setattr(tts_module.edge_tts, "Communicate", _AlwaysFailCommunicate)

    out_path = tmp_path / "out.mp3"
    with pytest.raises(RuntimeError, match="connection reset"):
        _run_async(tts_module.tts_to_mp3("hello", out_path, "en-US-JennyNeural"))

    assert len(_FakeCommunicate.calls) == tts_module._MAX_TTS_ATTEMPTS
    assert not out_path.exists(), "truncated output from the last failed attempt must be removed"


def test_cache_hit_skips_edge_tts_entirely(tmp_path, monkeypatch) -> None:
    """An existing file over the size threshold short-circuits before any
    edge_tts call is made."""
    monkeypatch.setattr(tts_module.edge_tts, "Communicate", _MustNotBeCalledCommunicate)

    out_path = tmp_path / "out.mp3"
    out_path.write_bytes(b"x" * 3000)

    _run_async(tts_module.tts_to_mp3("hello", out_path, "en-US-JennyNeural"))

    assert out_path.stat().st_size == 3000


def test_single_failure_then_success_only_retries_once(tmp_path, monkeypatch) -> None:
    """Sanity check on the boundary: exactly one failure still succeeds
    within budget, with only 2 total attempts made."""
    _FakeCommunicate.fail_times = 1
    monkeypatch.setattr(tts_module.edge_tts, "Communicate", _FakeCommunicate)

    out_path = tmp_path / "out.mp3"
    _run_async(tts_module.tts_to_mp3("hello", out_path, "en-US-JennyNeural"))

    assert len(_FakeCommunicate.calls) == 2
    assert out_path.exists()
