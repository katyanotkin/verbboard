"""Cheap spam checks for the public feedback form (no external services)."""

from __future__ import annotations

# Form-testing / spam-probe services whose submissions are never real feedback.
BLOCKED_EMAIL_DOMAINS = frozenset({"formtests.info"})

# Hidden input name: real users never see or fill it, form-filling bots do.
HONEYPOT_FIELD = "hp_url"


def is_blocked_email(email: str) -> bool:
    domain = email.strip().rsplit("@", 1)[-1].lower().strip("<>. ") if "@" in email else ""
    return any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_EMAIL_DOMAINS)


def is_spam_submission(*, honeypot: str, contact_email: str) -> bool:
    return bool(honeypot.strip()) or is_blocked_email(contact_email)
