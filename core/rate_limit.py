"""Minimal in-process rate limiting.

Cloud Run may run multiple instances, so this is a per-instance soft limit,
not a globally enforced one -- but it caps the cost of a single-instance abuse
burst without adding infra (Redis, etc.) the rest of the app doesn't have.
Bounded like the other in-process caches in this codebase (`_GENERATING` in
core/verb_autogen.py): a stale-key sweep keeps memory from growing unbounded
under a wide-IP scan.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, *, max_calls: int, window_seconds: float, max_tracked_keys: int = 5000) -> None:
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._max_tracked_keys = max_tracked_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > self._window_seconds:
            hits.popleft()

        if len(hits) >= self._max_calls:
            return False

        hits.append(now)
        if len(self._hits) > self._max_tracked_keys:
            self._evict_stale(now)
        return True

    def _evict_stale(self, now: float) -> None:
        stale_keys = [key for key, hits in self._hits.items() if not hits or now - hits[-1] > self._window_seconds]
        for key in stale_keys:
            del self._hits[key]
