"""
Tests for _call_claude (admin_candidates) and get_anthropic_client (settings_ai).

Covers:
- _call_claude is a coroutine (awaitable)
- Successful JSON response is parsed and returned as a dict
- Invalid JSON from Claude raises HTTPException 502
- Per-language model selection (en->Haiku, others->Sonnet)
- Per-language max_tokens routing (he=4096, others=2048)
- get_anthropic_client singleton identity
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _run_async(coro):
    """Run a coroutine in a worker thread with its own event loop.

    Follows the same pattern as test_audio.py to avoid event loop conflicts
    when Playwright e2e tests have already started a loop in the main thread.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _make_mock_client(response_text: str) -> MagicMock:
    """Build a mock AsyncAnthropic client whose messages.create returns response_text."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=response_text)]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)
    return mock_client


# ---------------------------------------------------------------------------
# _call_claude is awaitable
# ---------------------------------------------------------------------------


def test_call_claude_returns_coroutine_without_await() -> None:
    """Calling _call_claude without await must return a coroutine, not a dict."""
    from app.routes.admin_candidates import _call_claude

    mock_client = _make_mock_client('{"lemma": "go"}')

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        result = _call_claude("en", "go")

    assert inspect.iscoroutine(result), "expected a coroutine object, got " + repr(
        result
    )
    # Close the coroutine to avoid RuntimeWarning about never-awaited coroutine
    result.close()


# ---------------------------------------------------------------------------
# Successful JSON response
# ---------------------------------------------------------------------------


def test_call_claude_returns_parsed_dict_on_valid_json() -> None:
    """A valid JSON string from Claude must be parsed into a Python dict."""
    payload = {"lemma": "go", "forms": {"base": "go", "past": "went"}}
    mock_client = _make_mock_client(json.dumps(payload))

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        from app.routes.admin_candidates import _call_claude

        result = _run_async(_call_claude("en", "go"))

    assert result == payload


# ---------------------------------------------------------------------------
# Invalid JSON raises HTTPException 502
# ---------------------------------------------------------------------------


def test_call_claude_raises_502_on_invalid_json() -> None:
    """Non-JSON text from Claude must raise HTTPException with status_code=502."""
    mock_client = _make_mock_client("Sorry, I cannot help with that.")

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        from app.routes.admin_candidates import _call_claude

        with pytest.raises(HTTPException) as exc_info:
            _run_async(_call_claude("en", "go"))

    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# Per-language max_tokens
# ---------------------------------------------------------------------------


def test_call_claude_uses_4096_max_tokens_for_hebrew() -> None:
    """Hebrew language must trigger max_tokens=4096."""
    mock_client = _make_mock_client('{"lemma": "ללכת"}')

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        from app.routes.admin_candidates import _call_claude

        _run_async(_call_claude("he", "ללכת"))

    _, kwargs = mock_client.messages.create.call_args
    assert (
        kwargs.get("max_tokens") == 4096
    ), f"expected max_tokens=4096 for 'he', got {kwargs.get('max_tokens')}"


def test_call_claude_uses_2048_max_tokens_for_non_hebrew() -> None:
    """Non-Hebrew languages must fall back to max_tokens=2048."""
    mock_client = _make_mock_client('{"lemma": "go"}')

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        from app.routes.admin_candidates import _call_claude

        _run_async(_call_claude("en", "go"))

    _, kwargs = mock_client.messages.create.call_args
    assert (
        kwargs.get("max_tokens") == 2048
    ), f"expected max_tokens=2048 for 'en', got {kwargs.get('max_tokens')}"


# ---------------------------------------------------------------------------
# Per-language model selection
# ---------------------------------------------------------------------------


def test_call_claude_uses_haiku_for_english() -> None:
    """English must use the Haiku model."""
    mock_client = _make_mock_client('{"lemma": "go"}')

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        from app.routes.admin_candidates import _call_claude

        _run_async(_call_claude("en", "go"))

    _, kwargs = mock_client.messages.create.call_args
    assert (
        kwargs.get("model") == "claude-haiku-4-5-20251001"
    ), f"expected Haiku for 'en', got {kwargs.get('model')}"


def test_call_claude_uses_sonnet_for_non_english() -> None:
    """Non-English languages must use the Sonnet model."""
    for lang, query in [("he", "ללכת"), ("ru", "идти"), ("es", "ir")]:
        mock_client = _make_mock_client(f'{{"lemma": "{query}"}}')

        with patch(
            "app.routes.admin_candidates.get_anthropic_client",
            return_value=mock_client,
        ):
            from app.routes.admin_candidates import _call_claude

            _run_async(_call_claude(lang, query))

        _, kwargs = mock_client.messages.create.call_args
        assert (
            kwargs.get("model") == "claude-sonnet-4-6"
        ), f"expected Sonnet for '{lang}', got {kwargs.get('model')}"


# ---------------------------------------------------------------------------
# No assistant prefill (Claude 4.x does not support it)
# ---------------------------------------------------------------------------


def test_call_claude_sends_only_user_message() -> None:
    """messages list must contain exactly one user message -- no assistant prefill."""
    mock_client = _make_mock_client('{"lemma": "go"}')

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        from app.routes.admin_candidates import _call_claude

        _run_async(_call_claude("en", "go"))

    _, kwargs = mock_client.messages.create.call_args
    messages = kwargs.get("messages", [])
    assert len(messages) == 1, f"expected 1 message, got {len(messages)}"
    assert messages[0]["role"] == "user"


def test_call_claude_handles_markdown_fenced_json() -> None:
    """Claude sometimes wraps output in ```json fences; these must be stripped."""
    payload = {"lemma": "go", "forms": {"past": "went"}}
    fenced = f"```json\n{json.dumps(payload)}\n```"
    mock_client = _make_mock_client(fenced)

    with patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    ):
        from app.routes.admin_candidates import _call_claude

        result = _run_async(_call_claude("en", "go"))

    assert result == payload


# ---------------------------------------------------------------------------
# Singleton client
# ---------------------------------------------------------------------------


def test_get_anthropic_client_returns_same_instance() -> None:
    """get_anthropic_client() must return the identical object on repeated calls."""
    from core.settings_ai import get_anthropic_client

    get_anthropic_client.cache_clear()

    try:
        with patch("anthropic.AsyncAnthropic") as mock_cls:
            mock_instance = MagicMock()
            mock_cls.return_value = mock_instance

            with patch(
                "core.settings_ai._load_anthropic_api_key",
                return_value="test-key",
            ):
                first = get_anthropic_client()
                second = get_anthropic_client()

        assert first is second, "lru_cache must return the same instance on every call"
        assert (
            mock_cls.call_count == 1
        ), f"AsyncAnthropic constructor called {mock_cls.call_count} times, expected 1"
    finally:
        get_anthropic_client.cache_clear()
