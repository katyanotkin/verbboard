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


# ---------------------------------------------------------------------------
# _call_claude_single_example
# ---------------------------------------------------------------------------


def _patch_single(mock_client):
    return patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    )


def test_single_example_returns_src_dst_dict() -> None:
    """Happy path: valid JSON with src+dst is returned as a plain dict."""
    payload = {"src": "Je vais à l'école.", "dst": "I go to school."}
    mock_client = _make_mock_client(json.dumps(payload))

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        result = _run_async(_call_claude_single_example("fr", "aller", [], 0))

    assert result == payload


def test_single_example_strips_markdown_fences() -> None:
    payload = {"src": "Ich gehe.", "dst": "I go."}
    fenced = f"```json\n{json.dumps(payload)}\n```"
    mock_client = _make_mock_client(fenced)

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        result = _run_async(_call_claude_single_example("de", "gehen", [], 0))

    assert result == payload


def test_single_example_raises_502_on_invalid_json() -> None:
    mock_client = _make_mock_client("Sorry, cannot do that.")

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        with pytest.raises(HTTPException) as exc_info:
            _run_async(_call_claude_single_example("en", "go", [], 0))

    assert exc_info.value.status_code == 502
    assert "invalid JSON" in exc_info.value.detail


def test_single_example_raises_502_on_missing_src() -> None:
    mock_client = _make_mock_client('{"dst": "I go."}')

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        with pytest.raises(HTTPException) as exc_info:
            _run_async(_call_claude_single_example("en", "go", [], 0))

    assert exc_info.value.status_code == 502
    assert "unexpected format" in exc_info.value.detail


def test_single_example_raises_502_on_missing_dst() -> None:
    mock_client = _make_mock_client('{"src": "I go."}')

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        with pytest.raises(HTTPException) as exc_info:
            _run_async(_call_claude_single_example("en", "go", [], 0))

    assert exc_info.value.status_code == 502


def test_single_example_uses_512_max_tokens() -> None:
    mock_client = _make_mock_client('{"src": "x", "dst": "y"}')

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("en", "go", [], 0))

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs.get("max_tokens") == 512


def test_single_example_passes_system_prompt() -> None:
    mock_client = _make_mock_client('{"src": "x", "dst": "y"}')

    with (
        _patch_single(mock_client),
        patch("app.routes.admin_candidates.get_cached_system", return_value="sys"),
    ):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", [], 0))

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs.get("system") == "sys"


def test_single_example_avoid_note_excludes_replaced_index() -> None:
    """The replaced example's native sentence must appear in the form-preservation note
    but NOT in the avoid list.  Other examples' native sentences must be in the avoid list."""
    existing = [
        {"src": "A native", "dst": "A english"},
        {"src": "B native", "dst": "B english"},
    ]
    mock_client = _make_mock_client('{"src": "C", "dst": "new"}')

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("en", "go", existing, 1))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    # form-preservation note must include the original sentence and ask for same form
    assert "B native" in user_content
    assert "SAME grammatical form" in user_content
    # other examples' native sentences must be in the avoid list
    assert "A native" in user_content
    # English translations must never appear in the prompt
    assert "A english" not in user_content
    assert "B english" not in user_content
    # B native must not be in the avoid list (it precedes "Avoid repeating", not follow it)
    avoid_section = (
        user_content.split("Avoid repeating", 1)[-1]
        if "Avoid repeating" in user_content
        else ""
    )
    assert "B native" not in avoid_section


def test_single_example_no_avoid_note_when_only_one_example() -> None:
    """When replacing the only example there is nothing to avoid."""
    mock_client = _make_mock_client('{"src": "x", "dst": "y"}')

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(
            _call_claude_single_example("en", "go", [{"src": "A", "dst": "B"}], 0)
        )

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    assert "Avoid" not in user_content


# ---------------------------------------------------------------------------
# avoid_note bug: mixed-format example list (old-format dst-only + regen src+dst)
# ---------------------------------------------------------------------------


def test_single_example_avoid_note_uses_dst_for_old_format_examples() -> None:
    """When the existing list has old-format entries (dst=native, no src key), the
    avoid note must include the native sentence -- not nothing.

    This is the CORRECT current behavior for old-format examples.
    """
    # Old _call_claude format: only "dst" key, value = native sentence
    existing = [
        {"dst": "Я иду домой."},  # old format, dst = native
        {"dst": "replace me"},  # index to replace
    ]
    mock_client = _make_mock_client(
        '{"src": "Мы идём вместе.", "dst": "We go together."}'
    )

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", existing, 1))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    # Old-format example at index 0: dst IS the native sentence, appears in avoid list.
    assert "Я иду домой." in user_content
    # Replaced example's native sentence appears in the form-preservation note, not avoid.
    assert "replace me" in user_content
    assert "SAME grammatical form" in user_content
    avoid_section = (
        user_content.split("Avoid repeating", 1)[-1]
        if "Avoid repeating" in user_content
        else ""
    )
    assert "replace me" not in avoid_section


def test_single_example_avoid_note_uses_src_for_regen_format_examples() -> None:
    """When the existing list contains a previously-regened example
    (src=native, dst=English translation), the avoid list must use src
    (the native sentence), not dst (the English translation).
    """
    # Regen format: src = native sentence, dst = English translation
    existing = [
        {"src": "Я иду домой.", "dst": "I go home."},  # previously regened example
        {"src": "replace me native", "dst": "replace me english"},  # index to replace
    ]
    mock_client = _make_mock_client(
        '{"src": "Мы идём вместе.", "dst": "We go together."}'
    )

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", existing, 1))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]

    # The native sentence (src) must be in the avoid list; English translation must not.
    assert "Я иду домой." in user_content  # native sentence (src) is in avoid list
    assert "I go home." not in user_content  # English translation (dst) is not used


def test_single_example_avoid_note_mixed_old_and_regen_formats() -> None:
    """When examples come from different sources -- some old-format (dst=native),
    some regen-format (src=native, dst=English) -- the avoid list must contain
    the native sentence from each example regardless of format.
    """
    existing = [
        {"dst": "Я иду домой."},  # old format: dst = native (correct)
        {
            "src": "Он идёт на работу.",
            "dst": "He goes to work.",
        },  # regen format: dst = English (wrong)
        {"src": "replace me", "dst": "replace me en"},  # index to replace
    ]
    mock_client = _make_mock_client(
        '{"src": "Мы идём вместе.", "dst": "We go together."}'
    )

    with _patch_single(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", existing, 2))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]

    # Old-format example: dst = native sentence -- appears in avoid list.
    assert "Я иду домой." in user_content
    # Regen-format example: src = native sentence -- appears in avoid list.
    assert "Он идёт на работу." in user_content
    # English translation of regen-format example must NOT appear.
    assert "He goes to work." not in user_content
