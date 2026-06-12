"""Tests for _call_claude_single_example (admin_candidates).

Covers:
- Happy path: valid JSON with src+dst returned as plain dict
- Markdown fence stripping
- 502 on invalid JSON / missing src / missing dst
- max_tokens=512 enforced
- System prompt is passed
- Avoid-note excludes the replaced example's native sentence
- Avoid-note uses src for regen-format and dst for old-format examples
- Mixed old-format / regen-format example lists handled correctly
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException


def _run_async(coro):
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def _make_mock_client(response_text: str) -> MagicMock:
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=response_text)]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)
    return mock_client


def _patch_client(mock_client):
    return patch(
        "app.routes.admin_candidates.get_anthropic_client",
        return_value=mock_client,
    )


# ── happy path ────────────────────────────────────────────────────────────────


def test_single_example_returns_src_dst_dict() -> None:
    """Happy path: valid JSON with src+dst is returned as a plain dict."""
    payload = {"src": "Je vais à l'école.", "dst": "I go to school."}
    mock_client = _make_mock_client(json.dumps(payload))

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        result = _run_async(_call_claude_single_example("fr", "aller", [], 0))

    assert result == payload


def test_single_example_strips_markdown_fences() -> None:
    payload = {"src": "Ich gehe.", "dst": "I go."}
    fenced = f"```json\n{json.dumps(payload)}\n```"
    mock_client = _make_mock_client(fenced)

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        result = _run_async(_call_claude_single_example("de", "gehen", [], 0))

    assert result == payload


# ── error cases ───────────────────────────────────────────────────────────────


def test_single_example_raises_502_on_invalid_json() -> None:
    mock_client = _make_mock_client("Sorry, cannot do that.")

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        with pytest.raises(HTTPException) as exc_info:
            _run_async(_call_claude_single_example("en", "go", [], 0))

    assert exc_info.value.status_code == 502
    assert "invalid JSON" in exc_info.value.detail


def test_single_example_raises_502_on_missing_src() -> None:
    mock_client = _make_mock_client('{"dst": "I go."}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        with pytest.raises(HTTPException) as exc_info:
            _run_async(_call_claude_single_example("en", "go", [], 0))

    assert exc_info.value.status_code == 502
    assert "unexpected format" in exc_info.value.detail


def test_single_example_raises_502_on_missing_dst() -> None:
    mock_client = _make_mock_client('{"src": "I go."}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        with pytest.raises(HTTPException) as exc_info:
            _run_async(_call_claude_single_example("en", "go", [], 0))

    assert exc_info.value.status_code == 502


# ── token / prompt config ─────────────────────────────────────────────────────


def test_single_example_uses_512_max_tokens() -> None:
    mock_client = _make_mock_client('{"src": "x", "dst": "y"}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("en", "go", [], 0))

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs.get("max_tokens") == 512


def test_single_example_passes_system_prompt() -> None:
    mock_client = _make_mock_client('{"src": "x", "dst": "y"}')

    with (
        _patch_client(mock_client),
        patch("app.routes.admin_candidates.get_cached_system", return_value="sys"),
    ):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", [], 0))

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs.get("system") == "sys"


# ── avoid-note logic ──────────────────────────────────────────────────────────


def test_single_example_avoid_note_excludes_replaced_index() -> None:
    """The replaced example's native sentence must appear in the form-preservation note
    but NOT in the avoid list. Other examples' native sentences must be in the avoid list."""
    existing = [
        {"src": "A native", "dst": "A english"},
        {"src": "B native", "dst": "B english"},
    ]
    mock_client = _make_mock_client('{"src": "C", "dst": "new"}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("en", "go", existing, 1))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    assert "B native" in user_content
    assert "SAME grammatical form" in user_content
    assert "A native" in user_content
    assert "A english" not in user_content
    assert "B english" not in user_content
    avoid_section = user_content.split("Avoid repeating", 1)[-1] if "Avoid repeating" in user_content else ""
    assert "B native" not in avoid_section


def test_single_example_no_avoid_note_when_only_one_example() -> None:
    """When replacing the only example there is nothing to avoid."""
    mock_client = _make_mock_client('{"src": "x", "dst": "y"}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("en", "go", [{"src": "A", "dst": "B"}], 0))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    assert "Avoid" not in user_content


def test_single_example_avoid_note_uses_dst_for_old_format_examples() -> None:
    """Old-format entries (dst=native, no src key): avoid note must include dst as the
    native sentence."""
    existing = [
        {"dst": "Я иду домой."},
        {"dst": "replace me"},
    ]
    mock_client = _make_mock_client('{"src": "Мы идём вместе.", "dst": "We go together."}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", existing, 1))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    assert "Я иду домой." in user_content
    assert "replace me" in user_content
    assert "SAME grammatical form" in user_content
    avoid_section = user_content.split("Avoid repeating", 1)[-1] if "Avoid repeating" in user_content else ""
    assert "replace me" not in avoid_section


def test_single_example_avoid_note_uses_src_for_regen_format_examples() -> None:
    """Regen-format entries (src=native, dst=English): avoid note must use src,
    not dst (the English translation)."""
    existing = [
        {"src": "Я иду домой.", "dst": "I go home."},
        {"src": "replace me native", "dst": "replace me english"},
    ]
    mock_client = _make_mock_client('{"src": "Мы идём вместе.", "dst": "We go together."}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", existing, 1))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    assert "Я иду домой." in user_content
    assert "I go home." not in user_content


def test_single_example_avoid_note_mixed_old_and_regen_formats() -> None:
    """Mixed list (some old-format, some regen-format): avoid note must extract the
    native sentence correctly from each regardless of format."""
    existing = [
        {"dst": "Я иду домой."},
        {"src": "Он идёт на работу.", "dst": "He goes to work."},
        {"src": "replace me", "dst": "replace me en"},
    ]
    mock_client = _make_mock_client('{"src": "Мы идём вместе.", "dst": "We go together."}')

    with _patch_client(mock_client):
        from app.routes.admin_candidates import _call_claude_single_example

        _run_async(_call_claude_single_example("ru", "идти", existing, 2))

    _, kwargs = mock_client.messages.create.call_args
    user_content = kwargs["messages"][0]["content"]
    assert "Я иду домой." in user_content
    assert "Он идёт на работу." in user_content
    assert "He goes to work." not in user_content
