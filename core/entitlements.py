from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

from core.languages.config import FREE_STUDY_LANGUAGES
from core.settings import Settings
from core.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

# New top-level collection -- deliberately NOT on users/{uid}, which is
# merge-written on every authenticated request via sync_user_profile(). A
# hot, broadly-written document is the wrong place for entitlement state.
ENTITLEMENTS_COLLECTION = "user_entitlements"

_CACHE_TTL_SECONDS = 60.0
_entitlement_cache: dict[str, tuple[float, bool]] = {}

_ACTIVE_STATUSES = {"active"}


def requires_entitlement(language: str, settings: Settings | None = None) -> bool:
    """True if `language` is Plus-only under the current edition config.

    Today FREE_STUDY_LANGUAGES == every registered language (en/ru/he/es), so
    this is always False in production -- infrastructure ahead of content.
    `settings` is accepted (unused today) so a future edition-scoped allowlist
    can be threaded through without changing the call signature.
    """
    del settings  # not yet used -- FREE_STUDY_LANGUAGES is edition-independent today
    return language not in FREE_STUDY_LANGUAGES


def _is_active(data: dict[str, Any]) -> bool:
    if data.get("status") not in _ACTIVE_STATUSES:
        return False
    expires_at = data.get("expires_at")
    if expires_at is None:
        return True
    now = datetime.now(UTC)
    try:
        return expires_at > now
    except TypeError:
        # Can't compare (e.g. tz-naive datetime from a mock/emulator) --
        # fail toward "still active" rather than raising.
        return True


def has_plus_entitlement(uid: str) -> bool:
    """True iff user_entitlements/{uid}.status == "active" and not expired.

    Cached for _CACHE_TTL_SECONDS (mirrors core/verb_loader.py's TTL-cache
    pattern; functools.lru_cache has no TTL and would never expire a revoked
    grant).

    Fails open on a Firestore read error/timeout: this gates study content,
    not sensitive data, so a false grant (a few minutes of free content during
    a GCP incident) is far cheaper than a false denial (locking out a
    legitimately-entitled paying user). Fails closed only on a definitive
    negative -- no document, or status != "active".
    """
    now = time.monotonic()
    cached = _entitlement_cache.get(uid)
    if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
        return cached[1]

    try:
        doc = get_db().collection(ENTITLEMENTS_COLLECTION).document(uid).get()
    except Exception:
        logger.warning("has_plus_entitlement: Firestore read failed for uid=%s", uid, exc_info=True)
        if cached is not None:
            return cached[1]
        return True

    if not doc.exists:
        _entitlement_cache[uid] = (now, False)
        return False

    result = _is_active(doc.to_dict() or {})
    _entitlement_cache[uid] = (now, result)
    return result


def can_study(language: str, uid: str | None, settings: Settings | None = None) -> bool:
    return not requires_entitlement(language, settings) or (uid is not None and has_plus_entitlement(uid))


def invalidate_entitlement_cache(uid: str) -> None:
    _entitlement_cache.pop(uid, None)


# ---------------------------------------------------------------------------
# Admin grant/revoke (Part E)
# ---------------------------------------------------------------------------


def get_entitlement(uid: str) -> dict[str, Any] | None:
    doc = get_db().collection(ENTITLEMENTS_COLLECTION).document(uid).get()
    if not doc.exists:
        return None
    data = doc.to_dict() or {}
    data["uid"] = uid
    return data


def set_entitlement(
    *,
    uid: str,
    status: str,
    note: str = "",
    plan: str = "plus",
    source: str = "manual_admin",
) -> dict[str, Any]:
    """Manual admin grant/revoke. Phase 1 only writes the fields it uses
    (status/plan/source/granted_at/updated_at/note); the billing-only fields
    (product_id/purchase_token/order_id/expires_at) are seeded to None on
    first write so the full Phase-2 schema exists without a migration, and
    are left untouched on subsequent writes so a future billing-sourced value
    is never clobbered by a manual admin edit.
    """
    if status not in {"active", "expired", "revoked", "none"}:
        raise ValueError(f"Unsupported entitlement status: {status!r}")

    now = datetime.now(UTC)
    db = get_db()
    doc_ref = db.collection(ENTITLEMENTS_COLLECTION).document(uid)
    existing_snap = doc_ref.get()

    data: dict[str, Any] = {
        "status": status,
        "plan": plan,
        "source": source,
        "note": note or None,
        "updated_at": now,
        "last_verified_at": now,
    }
    if status == "active":
        data["granted_at"] = now

    if not existing_snap.exists:
        data.setdefault("product_id", None)
        data.setdefault("purchase_token", None)
        data.setdefault("order_id", None)
        data.setdefault("expires_at", None)

    doc_ref.set(data, merge=True)
    invalidate_entitlement_cache(uid)

    merged = {**(existing_snap.to_dict() or {}), **data}
    merged["uid"] = uid
    return merged


def lookup_uid_by_email(email: str) -> str | None:
    """Resolve a Firebase Auth uid from an email address for the admin grant
    page. None if no account exists with that email or the lookup fails."""
    from firebase_admin import auth as firebase_auth_admin

    from core.auth.firebase_auth import initialize_firebase_admin

    initialize_firebase_admin()
    try:
        user_record = firebase_auth_admin.get_user_by_email(email)
    except Exception:
        return None
    return user_record.uid
