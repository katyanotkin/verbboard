"""
Circuit breaker for the Anthropic API (out of credit, rate limited, overloaded).

Why: on 2026-10-05 the account ran out of credit and every Claude call failed
with HTTP 400 "credit balance is too low". Callers swallowed the error, so
searches kept spending rate-limit slots, the home page kept auto-reloading, and
pair completion blacklisted lemmas for 24 h. The breaker makes the outage one
visible, cheap state: while open, guarded calls raise ProviderUnavailable with
zero network traffic; after the cool-down exactly one probe call goes through.

In-process (per Cloud Run instance). Transitions (open/close) are mirrored to
Firestore `provider_status/anthropic` (best effort) for the admin banner and the
replay tool, and logged with fixed text for a Cloud Logging alert:
  PROVIDER_UNAVAILABLE provider=anthropic reason=<reason>
  PROVIDER_RECOVERED provider=anthropic

No Gemini fallback for Russian/Hebrew: quality and prompt parity are not there.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

import anthropic

logger = logging.getLogger(__name__)

# Cool-downs before one probe call is allowed through (seconds). Tune here.
OUT_OF_CREDIT_COOLDOWN_SECONDS = 120
RATE_LIMITED_DEFAULT_COOLDOWN_SECONDS = 60  # used when no Retry-After header
OVERLOADED_COOLDOWN_SECONDS = 120
AUTH_ERROR_COOLDOWN_SECONDS = 120
# A probe that never reports back (cancelled task, hung call) frees its slot after this.
PROBE_TIMEOUT_SECONDS = 60
# An `open` status doc not refreshed for this long is treated as stale by the admin banner.
STATUS_STALE_AFTER_SECONDS = 1800
_MAX_RETRY_AFTER_SECONDS = 900

OUT_OF_CREDIT = "out_of_credit"
RATE_LIMITED = "rate_limited"
OVERLOADED = "overloaded"
AUTH_ERROR = "auth_error"

ACTION_HINT = {
    OUT_OF_CREDIT: "top up Anthropic credit",
    AUTH_ERROR: "Claude API key rejected or lacks permission",
    RATE_LIMITED: "rate limited, retrying automatically",
    OVERLOADED: "Anthropic overloaded, retrying automatically",
}
_BILLING_WORDS = ("credit balance", "billing", "insufficient")

_STATUS_COLLECTION = "provider_status"
_FORCE_DOWN_ENV = "VB_FORCE_PROVIDER_DOWN"


class ProviderUnavailable(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def classify(exc: BaseException) -> str | None:
    """Map an exception to an outage reason, or None if it is not an outage."""
    if isinstance(exc, anthropic.BadRequestError):
        message = " ".join(str(exc).lower().split())
        return OUT_OF_CREDIT if any(word in message for word in _BILLING_WORDS) else None
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return AUTH_ERROR
    if isinstance(exc, anthropic.RateLimitError):
        return RATE_LIMITED
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402:
            return OUT_OF_CREDIT
        if exc.status_code in (401, 403):
            return AUTH_ERROR
        if exc.status_code == 529:
            return OVERLOADED
    return None


def _cooldown_seconds(reason: str, exc: BaseException | None) -> float:
    if reason == OUT_OF_CREDIT:
        return OUT_OF_CREDIT_COOLDOWN_SECONDS
    if reason == AUTH_ERROR:
        return AUTH_ERROR_COOLDOWN_SECONDS
    if reason == OVERLOADED:
        return OVERLOADED_COOLDOWN_SECONDS
    retry_after = None
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            retry_after = float(response.headers.get("retry-after"))
        except (TypeError, ValueError):
            retry_after = None
    if retry_after is None or retry_after <= 0:
        return RATE_LIMITED_DEFAULT_COOLDOWN_SECONDS
    return min(retry_after, _MAX_RETRY_AFTER_SECONDS)


def _forced_down() -> bool:
    """Local/stage simulation switch; never honored in prod."""
    if os.getenv(_FORCE_DOWN_ENV) != "1":
        return False
    from core.settings import _resolve_environment

    return _resolve_environment() != "prod"


def _write_status(provider: str, fields: dict) -> None:
    try:
        from core.storage.firestore_db import get_db

        get_db().collection(_STATUS_COLLECTION).document(provider).set(fields, merge=True)
    except Exception:
        logger.warning("Could not write provider_status/%s", provider, exc_info=True)


class CircuitBreaker:
    def __init__(self, provider: str) -> None:
        self.provider = provider
        self._lock = threading.Lock()
        self._open = False
        self._reason = ""
        self._open_until = 0.0
        self._probe_in_flight = False
        self._probe_started_at = 0.0

    def reset(self) -> None:
        with self._lock:
            self._open = False
            self._reason = ""
            self._open_until = 0.0
            self._probe_in_flight = False
            self._probe_started_at = 0.0

    def _probe_active(self) -> bool:
        return self._probe_in_flight and time.monotonic() - self._probe_started_at < PROBE_TIMEOUT_SECONDS

    def unavailable_reason(self) -> str | None:
        """Reason while calls are being refused (cool-down active), else None."""
        if _forced_down():
            return OUT_OF_CREDIT
        with self._lock:
            if self._open and (time.monotonic() < self._open_until or self._probe_active()):
                return self._reason
        return None

    def _acquire(self) -> bool:
        """Return True if the caller holds the probe slot; raise if refused."""
        if _forced_down():
            raise ProviderUnavailable(OUT_OF_CREDIT)
        with self._lock:
            if not self._open:
                return False
            if time.monotonic() < self._open_until or self._probe_active():
                raise ProviderUnavailable(self._reason)
            self._probe_in_flight = True
            self._probe_started_at = time.monotonic()
            return True

    def _on_success(self) -> None:
        with self._lock:
            was_open = self._open
            self._open = False
            self._probe_in_flight = False
        if was_open:
            logger.info("PROVIDER_RECOVERED provider=%s", self.provider)
            _write_status(self.provider, {"state": "closed", "closed_at": datetime.now(UTC).isoformat()})

    def _on_outage(self, reason: str, exc: BaseException) -> None:
        with self._lock:
            newly_opened = not self._open
            self._open = True
            self._reason = reason
            self._open_until = time.monotonic() + _cooldown_seconds(reason, exc)
            self._probe_in_flight = False
        if newly_opened:
            logger.error("PROVIDER_UNAVAILABLE provider=%s reason=%s", self.provider, reason)
            _write_status(
                self.provider,
                {
                    "state": "open",
                    "reason": reason,
                    "opened_at": datetime.now(UTC).isoformat(),
                    "updated_at": datetime.now(UTC).isoformat(),
                    "closed_at": None,
                    "last_error": str(exc)[:300],
                },
            )
        else:
            # A failed probe: refresh the heartbeat so the admin banner knows the
            # outage is still current (at most once per cool-down per instance).
            _write_status(self.provider, {"updated_at": datetime.now(UTC).isoformat()})

    @contextmanager
    def guard(self) -> Iterator[None]:
        """Wrap ONLY the API call (sync, or around an `await`).

        Raises ProviderUnavailable up front while open (no call made), and
        converts a classified outage error into ProviderUnavailable. Other
        exceptions pass through and do not trip the breaker.
        """
        holds_probe = self._acquire()
        settled = False
        try:
            yield
        except ProviderUnavailable:
            raise
        except Exception as exc:
            reason = classify(exc)
            if reason is None:
                raise
            settled = True
            self._on_outage(reason, exc)
            raise ProviderUnavailable(reason) from exc
        else:
            settled = True
            self._on_success()
        finally:
            # Any other exit (non-outage error, CancelledError, GeneratorExit)
            # must release the probe slot or the breaker would refuse forever.
            if holds_probe and not settled:
                with self._lock:
                    self._probe_in_flight = False


ANTHROPIC = CircuitBreaker("anthropic")


def provider_unavailable_reason() -> str | None:
    return ANTHROPIC.unavailable_reason()


def admin_banner_text() -> str | None:
    """Banner for admin pages when provider_status/anthropic is open; never raises."""
    try:
        from core.storage.firestore_db import get_db

        doc = get_db().collection(_STATUS_COLLECTION).document("anthropic").get()
        if not doc.exists:
            return None
        data = doc.to_dict() or {}
        if data.get("state") != "open":
            return None
        heartbeat = str(data.get("updated_at") or data.get("opened_at") or "")
        try:
            last_seen = datetime.fromisoformat(heartbeat)
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=UTC)
            if (datetime.now(UTC) - last_seen).total_seconds() > STATUS_STALE_AFTER_SECONDS:
                return None
        except ValueError:
            return None
        since = str(data.get("opened_at") or "")
        try:
            since = datetime.fromisoformat(since).strftime("%Y-%m-%d %H:%M UTC")
        except ValueError:
            pass
        return (
            f"Claude unavailable since {since}: {data.get('reason', 'unknown')} "
            f"({ACTION_HINT.get(data.get('reason', ''), 'see logs')}). "
            "Verb generation and Hebrew translations are paused."
        )
    except Exception:
        return None
