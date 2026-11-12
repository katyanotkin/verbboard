"""Cheap spam checks for the public feedback form (no external services)."""

from __future__ import annotations

import re

# Form-testing / spam-probe services whose submissions are never real feedback.
BLOCKED_EMAIL_DOMAINS = frozenset({"formtests.info"})

# Hidden input name: real users never see or fill it, form-filling bots do.
HONEYPOT_FIELD = "hp_url"


def is_blocked_email(email: str) -> bool:
    domain = email.strip().rsplit("@", 1)[-1].lower().strip("<>. ") if "@" in email else ""
    return any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_EMAIL_DOMAINS)


def is_spam_submission(*, honeypot: str, contact_email: str) -> bool:
    return bool(honeypot.strip()) or is_blocked_email(contact_email)


_URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_MAX_LINKS_BEFORE_HIDDEN = 1


def looks_like_link_spam(comment: str) -> bool:
    """Cold-outreach pitches carry links; real feedback rarely carries two or more.

    Such comments are stored with hidden=True (recoverable in admin), not dropped.
    """
    return len(_URL_PATTERN.findall(comment)) > _MAX_LINKS_BEFORE_HIDDEN
