from __future__ import annotations

import hmac
import logging

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.settings import load_settings

logger = logging.getLogger(__name__)

# Firebase Hosting only forwards cookies named exactly __session to Cloud Run.
# All other cookie names are stripped at the CDN layer before reaching the backend.
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
