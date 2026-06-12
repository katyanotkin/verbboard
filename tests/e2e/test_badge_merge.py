"""E2E tests: practice badge merge rule (cross-device sync).

When a logged-in user's practice badges are fetched from the server, practice_loop.js
applies a merge rule before writing to localStorage:

    server.length >= local.length  →  use server badges
    server.length <  local.length  →  use local badges (protect against silent save failure)

This means:
- Server wins on equal length (tie) and when server has more badges.
- Local wins only when it has strictly more badges than the server.

These tests inject and exercise the merge rule as a pure function via page.evaluate,
following the same pattern as test_preference_guard.py.  They verify the contract
rather than the internal implementation -- if practice_loop.js changes the rule,
this test must also be updated.

No Firebase auth is required because we test the decision logic in isolation.
"""

from __future__ import annotations

# ── helpers ───────────────────────────────────────────────────────────────────


# Replicates the exact merge expression from practice_loop.js:
#   const badgesToStore = payload.badges.length >= localBadges.length
#       ? payload.badges
#       : localBadges;
def _merge(page, server: list, local: list) -> list:
    return page.evaluate(
        "([s, l]) => s.length >= l.length ? s : l",
        [server, local],
    )


# ── merge rule cases ──────────────────────────────────────────────────────────


def test_badge_merge_server_wins_when_longer(page, live_server_url):
    """Server has more badges than local → use server.

    Typical case: user completed sessions on another device and local is behind.
    """
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    result = _merge(page, server=[3, 6, 9], local=[3])
    assert result == [3, 6, 9], f"Server longer: expected [3,6,9], got {result}"


def test_badge_merge_local_wins_when_longer(page, live_server_url):
    """Local has more badges than server → use local.

    Guards against a silent server-save failure: the user earned badges locally
    but the server write failed, so the server holds a shorter list.
    """
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    result = _merge(page, server=[3], local=[3, 6, 9])
    assert result == [3, 6, 9], f"Local longer: expected [3,6,9], got {result}"


def test_badge_merge_server_wins_on_equal_length(page, live_server_url):
    """Equal length → server wins (>= means server is authoritative on tie).

    This prevents an unnecessary local-override when both sides agree on count.
    """
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    server = [3, 6]
    local = [3, 9]  # same length, different content
    result = _merge(page, server=server, local=local)
    assert result == server, f"Equal length: server must win (>=). server={server}, local={local}, got {result}"


def test_badge_merge_empty_local_uses_server(page, live_server_url):
    """No local badges (fresh install or cleared storage) → use server."""
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    result = _merge(page, server=[3, 6], local=[])
    assert result == [3, 6], f"Empty local: expected [3,6], got {result}"


def test_badge_merge_empty_server_uses_local(page, live_server_url):
    """Server has no badges → keep local badges."""
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    result = _merge(page, server=[], local=[3, 6, 9])
    assert result == [3, 6, 9], f"Empty server: expected [3,6,9], got {result}"


def test_badge_merge_both_empty_returns_empty(page, live_server_url):
    """Both sides empty → result is empty (no badges on either device)."""
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    result = _merge(page, server=[], local=[])
    assert result == [], f"Both empty: expected [], got {result}"


def test_badge_merge_preserves_badge_values(page, live_server_url):
    """Merge must not mutate the values, only pick one list wholesale.

    Badge entries are integers (practice session sizes: 3, 6, 9).  The merge
    must never produce a mix of values from both lists.
    """
    page.goto(f"{live_server_url}/?language=en")
    page.wait_for_load_state("networkidle")

    server = [3, 6, 9, 3]
    local = [3]
    result = _merge(page, server=server, local=local)

    assert result == server, "Merge must return one list wholesale, not a hybrid"
    assert set(result) <= {
        3,
        6,
        9,
    }, f"Badge values must be valid session sizes, got {result}"
