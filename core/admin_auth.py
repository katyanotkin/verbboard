from __future__ import annotations

import hmac
import logging

from fastapi import Request, Response
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.settings import load_settings

logger = logging.getLogger(__name__)

# Firebase Hosting only forwards cookies named exactly __session to Cloud Run.
# All other cookie names are stripped at the CDN layer before reaching the backend.
#
# __session is a *shared envelope*: it can carry a "role" claim (admin session,
# see create_admin_session_token/verify_admin_session_token below) and/or a
# "uid" claim (signed-in regular user, see get_session_uid) in the same signed
# payload. Never introduce a second cookie name -- Fastly strips anything that
# isn't __session before it reaches Cloud Run and before it reaches the browser.
ADMIN_SESSION_COOKIE = "__session"
ADMIN_SESSION_SALT = "verbboard-admin-session"
ADMIN_SESSION_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 hours


def _serializer() -> URLSafeTimedSerializer:
    settings = load_settings()
    return URLSafeTimedSerializer(settings.admin_secret)


def verify_admin_password(password: str) -> bool:
    settings = load_settings()
    return hmac.compare_digest(password, settings.admin_secret)


def create_admin_session_token() -> str:
    serializer = _serializer()
    return serializer.dumps({"role": "admin"}, salt=ADMIN_SESSION_SALT)


def verify_admin_session_token(token: str) -> bool:
    if not token:
        return False
    serializer = URLSafeTimedSerializer(load_settings().admin_secret)
    try:
        payload = serializer.loads(
            token,
            salt=ADMIN_SESSION_SALT,
            max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        )
    except (SignatureExpired, BadSignature, Exception):
        return False
    return isinstance(payload, dict) and payload.get("role") == "admin"


# ---------------------------------------------------------------------------
# Shared session envelope
#
# The __session cookie can carry multiple claims at once (e.g. {"role": "admin",
# "uid": "abc123"} when the site owner is signed in as a regular user AND has
# an active admin session). Every write below merges with whatever claims are
# already present rather than clobbering the cookie -- see update_session_claims.
# ---------------------------------------------------------------------------


def _decode_session_token(token: str) -> dict:
    """Verify and decode a session token. Returns {} on missing/invalid/expired
    token -- never raises, so callers can treat a tampered cookie as "no claims"
    rather than an error."""
    if not token:
        return {}
    serializer = URLSafeTimedSerializer(load_settings().admin_secret)
    try:
        payload = serializer.loads(
            token,
            salt=ADMIN_SESSION_SALT,
            max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        )
    except (SignatureExpired, BadSignature, Exception):
        return {}
    return payload if isinstance(payload, dict) else {}


def read_session_claims(request: Request) -> dict:
    """Read and verify the __session cookie's claims. {} if missing/invalid/expired."""
    token = request.cookies.get(ADMIN_SESSION_COOKIE, "")
    return _decode_session_token(token)


def write_session_claims(response: Response, claims: dict) -> None:
    """Sign `claims` and set the __session cookie with the standard attributes.

    If `claims` is empty, the cookie is deleted instead of writing an empty
    envelope -- there is never a reason to keep a cookie with no claims.
    """
    if not claims:
        response.delete_cookie(key=ADMIN_SESSION_COOKIE, path="/", secure=True, samesite="lax")
        return
    serializer = _serializer()
    token = serializer.dumps(dict(claims), salt=ADMIN_SESSION_SALT)
    response.set_cookie(
        key=ADMIN_SESSION_COOKIE,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        path="/",
    )


def get_session_uid(request: Request) -> str | None:
    """Return the signed-in user's uid from the __session cookie, or None.

    None on a missing cookie, an admin-only session (no uid claim), or an
    invalid/tampered/expired cookie.
    """
    uid = read_session_claims(request).get("uid")
    return str(uid) if uid else None


def update_session_claims(request: Request, response: Response, **changes: str | None) -> dict:
    """Merge `changes` into the __session cookie's existing claims and write
    the result -- never clobbers claims that aren't part of `changes`.

    A value of None removes that key (e.g. update_session_claims(request,
    response, uid=None) clears only the uid claim on sign-out, leaving an
    admin "role" claim, if present, untouched). Returns the resulting claims
    dict (post-merge, pre-write is not observable to the caller since the
    write already happened).
    """
    claims = dict(read_session_claims(request))
    for key, value in changes.items():
        if value is None:
            claims.pop(key, None)
        else:
            claims[key] = value
    write_session_claims(response, claims)
    return claims
