"""Unit tests: practice badge merge rule.

Mirrors the merge expression from practice_loop.js:

    const badgesToStore = payload.badges.length >= localBadges.length
        ? payload.badges
        : localBadges;

Server wins on equal length or when it has more badges.
Local wins only when it has strictly more badges than the server.
"""

from __future__ import annotations


def _merge(server: list, local: list) -> list:
    return server if len(server) >= len(local) else local


def test_badge_merge_server_wins_when_longer():
    assert _merge(server=[3, 6, 9], local=[3]) == [3, 6, 9]


def test_badge_merge_local_wins_when_longer():
    assert _merge(server=[3], local=[3, 6, 9]) == [3, 6, 9]


def test_badge_merge_server_wins_on_equal_length():
    server = [3, 6]
    local = [3, 9]
    assert _merge(server, local) == server


def test_badge_merge_empty_local_uses_server():
    assert _merge(server=[3, 6], local=[]) == [3, 6]


def test_badge_merge_empty_server_uses_local():
    assert _merge(server=[], local=[3, 6, 9]) == [3, 6, 9]


def test_badge_merge_both_empty_returns_empty():
    assert _merge(server=[], local=[]) == []


def test_badge_merge_preserves_badge_values():
    server = [3, 6, 9, 3]
    result = _merge(server=server, local=[3])
    assert result == server
    assert set(result) <= {3, 6, 9}
