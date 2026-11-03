from __future__ import annotations

import logging

from core.analytics.session_tracker import delete_sessions_for_uid
from core.entitlements import delete_entitlement
from core.progress.progress_repository import delete_all_progress_data

logger = logging.getLogger(__name__)


def delete_account(uid: str) -> None:
    """Delete every uid-keyed record across Firestore, then the Firebase Auth
    account itself. Order: data first, auth account last -- if a Firestore
    step fails partway, the user can still sign in and retry rather than
    losing access to an account whose data deletion is incomplete.

    Accepted, not fixed: a second open tab for the same uid can write progress
    data (merge=True) between this function's Firestore deletes and the auth
    account actually being gone, and a stale ID token (not revoked by
    delete_user) could do the same for up to its ~1h expiry if the client's
    signOut() never ran. Both would resurrect a doc or two under a uid whose
    Firebase Auth account no longer exists -- low-probability, self-inflicted
    by the same user's own other session, not a cross-user exposure, and not
    closeable without a tombstone check in every write path (real scope
    creep beyond a v1 self-serve deletion feature).
    """
    delete_all_progress_data(uid)
    delete_entitlement(uid)
    delete_sessions_for_uid(uid)
    _delete_auth_user(uid)


def _delete_auth_user(uid: str) -> None:
    from firebase_admin import auth as firebase_auth_admin
    from firebase_admin.auth import UserNotFoundError

    from core.auth.firebase_auth import initialize_firebase_admin

    initialize_firebase_admin()
    try:
        firebase_auth_admin.delete_user(uid)
    except UserNotFoundError:
        # Dev-bypass uids (local-dev-user, stage-mock-user, prod-mock-user)
        # and any account already removed on Firebase's side -- data deletion
        # above already ran, nothing left to do.
        pass
