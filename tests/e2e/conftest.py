from __future__ import annotations

import os
import socket
import threading
import time
from typing import Any

import pytest
import uvicorn

from core.audio_backend.base import AudioBackend

# The root tests/conftest.py runs first and imports app.main, which means
# app.routes.learn has already bound `ensure_audio` as a local name.
# Re-patch it here so the local live server never calls real TTS.
import app.routes.learn as _learn_route


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


_learn_route.ensure_audio = _noop_audio  # type: ignore[assignment]

from app.main import app  # noqa: E402

TEST_PORT = 9753
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"


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

    config = uvicorn.Config(app, host="127.0.0.1", port=TEST_PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    if not _wait_for_port("127.0.0.1", TEST_PORT):
        raise RuntimeError(f"Test server did not start on port {TEST_PORT}")

    return BASE_URL


@pytest.fixture(scope="session")
def browser() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser_instance = playwright.chromium.launch()
        yield browser_instance
        browser_instance.close()


@pytest.fixture
def page(browser: Any, live_server_url: str) -> Any:
    page_instance = browser.new_page()
    page_instance.set_default_timeout(8_000)
    yield page_instance
    page_instance.close()
