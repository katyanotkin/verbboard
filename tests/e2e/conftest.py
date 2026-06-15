from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from typing import Any

import pytest
import uvicorn

# The root tests/conftest.py runs first and imports app.main, which means
# app.routes.learn has already bound `ensure_audio` as a local name.
# Re-patch it here so the local live server never calls real TTS.
import app.routes.learn as _learn_route
import core.analytics.session_tracker as _session_tracker
from core.audio_backend.base import AudioBackend


async def _noop_audio(
    audio_backend: AudioBackend,
    *,
    language: str,
    verb_id: str,
    voice: str,
    form_key: str,
    text: str,
    voice_edge_id: str,
) -> str:
    return f"noop/{language}/{verb_id}/{voice}/{form_key}.mp3"


async def _noop_start_session(*args: object, **kwargs: object) -> None:
    return


_learn_route.ensure_audio = _noop_audio  # type: ignore[assignment]
_session_tracker.start_session = _noop_start_session  # type: ignore[assignment]

from app.main import app  # noqa: E402


def _free_port() -> int:
    """Return a random OS-assigned free port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]


def _wait_for_port(host: str, port: int, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.1):
                return True
        except OSError:
            time.sleep(0.05)
    return False


@pytest.fixture(scope="session")
def live_server_url() -> str:
    external_base_url = os.getenv("E2E_BASE_URL")
    if external_base_url:
        return external_base_url.rstrip("/")

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_for_port("127.0.0.1", port):
        raise RuntimeError(f"Test server did not start on port {port}")

    # Warm up: prime Firestore caches so the first test does not hit a cold app.
    # /learn warms the individual get_verb() Firestore path (not covered by /verbs list cache).
    base = f"http://127.0.0.1:{port}"
    for warmup_url in (
        f"{base}/?language=en",
        f"{base}/verbs?language=en",
        f"{base}/verbs?language=ru",
        f"{base}/learn?language=en&verb_id=en_be",
        f"{base}/learn?language=ru&verb_id=ru_govorit",
    ):
        for _ in range(10):
            try:
                urllib.request.urlopen(warmup_url, timeout=10)
                break
            except Exception:
                time.sleep(1)

    return base


@pytest.fixture(scope="session")
def browser() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser_instance = playwright.chromium.launch()
        yield browser_instance
        browser_instance.close()


@pytest.fixture
def page(browser: Any, live_server_url: str) -> Any:
    # Isolated context per test: each test gets its own localStorage/cookies so
    # one test's practice sessions or known-verb state cannot leak into the next.
    ctx = browser.new_context()
    page_instance = ctx.new_page()
    page_instance.set_default_timeout(60_000)
    # Belt-and-suspenders: abort Firebase CDN requests so networkidle never
    # stalls waiting for gstatic.com, even if FIREBASE_WEB_CONFIG_JSON is set.
    page_instance.route("https://www.gstatic.com/firebasejs/**", lambda route: route.abort())
    yield page_instance
    ctx.close()
