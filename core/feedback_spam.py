"""Cheap spam checks for the public feedback form (no external services)."""

from __future__ import annotations

import hashlib
import hmac
import time

# Form-testing / spam-probe services whose submissions are never real feedback.
BLOCKED_EMAIL_DOMAINS = frozenset({"formtests.info"})

# Hidden input name: real users never see or fill it, form-filling bots do.
HONEYPOT_FIELD = "hp_url"


def is_blocked_email(email: str) -> bool:
    domain = email.strip().rsplit("@", 1)[-1].lower().strip("<>. ") if "@" in email else ""
    return any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_EMAIL_DOMAINS)


def is_spam_submission(*, honeypot: str, contact_email: str) -> bool:
    return bool(honeypot.strip()) or is_blocked_email(contact_email)


# Minimum time-to-submit (issue #100): the form carries a signed render timestamp; a bot that
# posts back within a few seconds of the render is dropped. Fails open on a missing, malformed
# or forged token (cached old page, no-JS client, privacy tool): only a VALID token that is
# too fresh counts, so a real person is never rejected for lacking the field.
MIN_SECONDS_TO_SUBMIT = 3
_TOKEN_CONTEXT = b"feedback-form-v1|"


def _sign(secret: str, issued_at: int) -> str:
    return hmac.new(secret.encode(), _TOKEN_CONTEXT + str(issued_at).encode(), hashlib.sha256).hexdigest()[:32]


def make_form_token(secret: str, *, now: float | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    return f"{issued_at}.{_sign(secret, issued_at)}"


def submitted_too_fast(secret: str, token: str, *, now: float | None = None) -> bool:
    issued_text, _, signature = (token or "").partition(".")
    # Only plain ASCII digits (short) and an ASCII signature get as far as int()/compare_digest;
    # anything else (non-ASCII, huge, mangled by an autofill tool) simply fails open.
    if not (issued_text.isascii() and issued_text.isdecimal() and 0 < len(issued_text) <= 12):
        return False
    if not (signature.isascii() and signature):
        return False
    issued_at = int(issued_text)
    if not hmac.compare_digest(signature.encode(), _sign(secret, issued_at).encode()):
        return False
    elapsed = (time.time() if now is None else now) - issued_at
    return 0 <= elapsed < MIN_SECONDS_TO_SUBMIT
