from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from core.settings import load_settings

ADMIN_SESSION_COOKIE = "verbboard_admin_session"
ADMIN_SESSION_SALT = "verbboard-admin-session"
ADMIN_SESSION_MAX_AGE_SECONDS = 60 * 60 * 12  # 12 hours


def _serializer() -> URLSafeTimedSerializer:
    settings = load_settings()
    return URLSafeTimedSerializer(settings.admin_secret)


def verify_admin_password(password: str) -> bool:
    settings = load_settings()
    return password == settings.admin_secret


def create_admin_session_token() -> str:
    serializer = _serializer()
    return serializer.dumps({"role": "admin"}, salt=ADMIN_SESSION_SALT)


def verify_admin_session_token(token: str) -> bool:
    serializer = _serializer()
    try:
        payload = serializer.loads(
            token,
            salt=ADMIN_SESSION_SALT,
            max_age=ADMIN_SESSION_MAX_AGE_SECONDS,
        )
    except (BadSignature, SignatureExpired):
        return False

    return payload == {"role": "admin"}
