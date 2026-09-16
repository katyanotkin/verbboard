"""Tests for core/rate_limit.py -- SlidingWindowRateLimiter.

Covers:
- allow() permits up to max_calls within the window
- the next call beyond max_calls is blocked
- allow() permits again once the window has elapsed
- a partially-elapsed window only frees the hits that actually expired
- keys are tracked independently of each other
- bounded eviction: stale keys are swept once max_tracked_keys is exceeded
"""

from __future__ import annotations

import pytest

from core.rate_limit import SlidingWindowRateLimiter


class _FakeClock:
    """Deterministic stand-in for time.monotonic()."""

    def __init__(self, start: float = 1_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture()
def fake_clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    clock = _FakeClock()
    monkeypatch.setattr("core.rate_limit.time.monotonic", clock)
    return clock


# ---------------------------------------------------------------------------
# Core allow/block behavior
# ---------------------------------------------------------------------------


def test_allows_up_to_max_calls_within_window(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=10)

    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is True


def test_blocks_call_beyond_max_within_window(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=3, window_seconds=10)

    for _ in range(3):
        assert limiter.allow("k") is True

    assert limiter.allow("k") is False
    # Still blocked on a subsequent check with no time passing.
    assert limiter.allow("k") is False


def test_allows_again_after_window_elapses(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=10)

    assert limiter.allow("k") is True
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False

    fake_clock.advance(10.01)

    assert limiter.allow("k") is True


def test_window_boundary_is_inclusive(fake_clock: _FakeClock) -> None:
    """A hit exactly window_seconds old is still counted as inside the window
    (the eviction check is strictly-greater-than), so allow() is still blocked
    right at the boundary and only opens up a moment after."""
    limiter = SlidingWindowRateLimiter(max_calls=1, window_seconds=10)

    assert limiter.allow("k") is True
    fake_clock.advance(10.0)
    assert limiter.allow("k") is False

    fake_clock.advance(0.01)
    assert limiter.allow("k") is True


def test_partial_window_elapse_only_frees_expired_hits(fake_clock: _FakeClock) -> None:
    """A sliding window frees exactly the hits that have aged out, not the
    whole bucket at once."""
    limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=10)

    assert limiter.allow("k") is True  # t=1000
    fake_clock.advance(6)
    assert limiter.allow("k") is True  # t=1006, both hits still within window
    assert limiter.allow("k") is False  # already at max_calls=2

    fake_clock.advance(4.01)  # t=1010.01 -- first hit (t=1000) now > 10s old
    # Only the first hit has expired; the second call frees exactly one slot.
    assert limiter.allow("k") is True
    assert limiter.allow("k") is False


# ---------------------------------------------------------------------------
# Key independence
# ---------------------------------------------------------------------------


def test_keys_are_independent(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=1, window_seconds=10)

    assert limiter.allow("a") is True
    assert limiter.allow("a") is False
    # A different key must not be affected by "a" exhausting its quota.
    assert limiter.allow("b") is True
    assert limiter.allow("b") is False


def test_many_independent_keys_each_get_their_own_quota(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=2, window_seconds=10)

    for key in ("a", "b", "c"):
        assert limiter.allow(key) is True
        assert limiter.allow(key) is True
        assert limiter.allow(key) is False


# ---------------------------------------------------------------------------
# Bounded eviction
# ---------------------------------------------------------------------------


def test_evicts_stale_keys_once_max_tracked_keys_exceeded(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=1, window_seconds=5, max_tracked_keys=3)

    assert limiter.allow("k1") is True
    fake_clock.advance(100)  # k1's hit is now long stale

    assert limiter.allow("k2") is True
    assert limiter.allow("k3") is True
    # Adding a 4th key pushes len(_hits) to 4 > max_tracked_keys=3, triggering
    # the stale-key sweep.
    assert limiter.allow("k4") is True

    assert "k1" not in limiter._hits, "stale key must be evicted once the tracked-key cap is exceeded"
    assert "k2" in limiter._hits
    assert "k3" in limiter._hits
    assert "k4" in limiter._hits


def test_eviction_does_not_remove_keys_with_recent_hits(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=5, window_seconds=1000, max_tracked_keys=2)

    assert limiter.allow("recent_a") is True
    assert limiter.allow("recent_b") is True
    # A third key exceeds max_tracked_keys, but neither prior key's window has
    # elapsed -- eviction must be a no-op for both.
    assert limiter.allow("recent_c") is True

    assert "recent_a" in limiter._hits
    assert "recent_b" in limiter._hits
    assert "recent_c" in limiter._hits


def test_eviction_not_triggered_below_max_tracked_keys(fake_clock: _FakeClock) -> None:
    limiter = SlidingWindowRateLimiter(max_calls=1, window_seconds=5, max_tracked_keys=10)

    assert limiter.allow("k1") is True
    fake_clock.advance(100)
    assert limiter.allow("k2") is True

    # len(_hits) == 2, well under max_tracked_keys=10 -- no sweep should run,
    # so the stale key is still present (just functionally expired).
    assert "k1" in limiter._hits
