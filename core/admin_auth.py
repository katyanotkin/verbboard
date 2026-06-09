from __future__ import annotations

import hashlib
import hmac
import logging

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.settings import load_settings

logger = logging.getLogger(__name__)

ADMIN_SESSION_COOKIE = "verbboard_admin_session"
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
    settings = load_settings()
    secret_tag = hashlib.md5(settings.admin_secret.encode()).hexdigest()[:8]
    print(f"[admin] verify: secret_tag={secret_tag} token={token[:16]}...", flush=True)
    serializer = URLSafeTimedSerializer(settings.admin_secret)
    try:
        payload = serializer.loads(
            token,
            salt=ADMIN_SESSION_SALT,
            max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        )
    except SignatureExpired:
        print("[admin] verify: SignatureExpired", flush=True)
        return False
    except BadSignature as exc:
        print(f"[admin] verify: BadSignature: {exc}", flush=True)
        return False
    except Exception as exc:
        print(f"[admin] verify: unexpected {type(exc).__name__}: {exc}", flush=True)
        return False
    result = isinstance(payload, dict) and payload.get("role") == "admin"
    print(f"[admin] verify: result={result} payload={payload}", flush=True)
    return result
