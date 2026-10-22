"""Minimal in-process rate limiting.

Cloud Run may run multiple instances, so this is a per-instance soft limit,
not a globally enforced one -- but it caps the cost of a single-instance abuse
burst without adding infra (Redis, etc.) the rest of the app doesn't have.
Bounded like the other in-process caches in this codebase (`_GENERATING` in
core/verb_autogen.py): a stale-key sweep keeps memory from growing unbounded
under a wide-IP scan.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from starlette.requests import Request


class SlidingWindowRateLimiter:
    def __init__(self, *, max_calls: int, window_seconds: float, max_tracked_keys: int = 5000) -> None:
        self._max_calls = max_calls
        self._window_seconds = window_seconds
        self._max_tracked_keys = max_tracked_keys
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()  # sync routes run in the threadpool

    def allow(self, key: str) -> bool:
        with self._lock:
            return self._allow_locked(key)

    def is_limited(self, key: str) -> bool:
        """True if `key` is at its cap right now; records nothing."""
        with self._lock:
            now = time.monotonic()
            hits = self._hits.get(key)
            if not hits:
                return False
            while hits and now - hits[0] > self._window_seconds:
                hits.popleft()
            return len(hits) >= self._max_calls

    def _allow_locked(self, key: str) -> bool:
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


def client_ip(request: Request) -> str:
    """Best-effort per-instance rate-limit key -- NOT a hard security boundary.

    Deliberately takes the LAST X-Forwarded-For hop, not the first: this key
    gates paid-API rate limits, where the first hop is whatever the client sent
    and trivially spoofable (core.analytics.session_tracker's fingerprint uses
    the first hop because analytics tolerates spoofing). CAVEAT (issue #73):
    behind Firebase Hosting the last hop may be a Google proxy address that
    varies per request, in which case this key never repeats and per-IP limits
    do nothing; callers that spend money therefore also sit behind a global cap.
    """
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
        if hops:
            return hops[-1]
    return (request.client.host if request.client else "") or "unknown"
