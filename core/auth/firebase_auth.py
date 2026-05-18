from __future__ import annotations

import logging
from functools import lru_cache

import firebase_admin
from fastapi import Request
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials

from core.auth.models import AuthUser
from core.settings import load_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dev bypass tokens
#
# Each token is accepted only when:
#   - ALLOW_LOCAL_DEV_AUTH=true is set on the server, AND
#   - ENVIRONMENT matches the token's required environment.
#
# This means user-stage only works on stage, user-prod only on prod, etc.
# Neither token is accepted on an environment it was not intended for.
# ---------------------------------------------------------------------------

_DEV_BYPASS_TOKENS: dict[str, tuple[str, str, str, str]] = {
    # token          -> (required_env, uid,               email,                    display_name)
    "local-dev": ("local", "local-dev-user", "dev@example.com", "Local Dev"),
    "user-stage": (
        "stage",
        "stage-mock-user",
        "dev-stage@example.com",
        "Stage Mock User",
    ),
    "user-prod": ("prod", "prod-mock-user", "dev-prod@example.com", "Prod Mock User"),
}


@lru_cache(maxsize=1)
def initialize_firebase_admin() -> None:
    if firebase_admin._apps:
        return

    firebase_admin.initialize_app(credentials.ApplicationDefault())


def verify_firebase_token(token: str) -> AuthUser:
    settings = load_settings()

    if settings.allow_local_dev_auth:
        bypass = _DEV_BYPASS_TOKENS.get(token)
        if bypass is not None:
            required_env, uid, email, name = bypass
            if settings.environment == required_env:
                return AuthUser(uid=uid, email=email, name=name, picture="")

    initialize_firebase_admin()

    decoded = firebase_auth.verify_id_token(token)

    return AuthUser(
        uid=str(decoded["uid"]),
        email=str(decoded.get("email") or ""),
        name=str(decoded.get("name") or ""),
        picture=str(decoded.get("picture") or ""),
    )


def get_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        return ""
    return authorization[len(prefix) :].strip()


def get_optional_auth_user(request: Request) -> AuthUser | None:
    token = get_bearer_token(request)
    if not token:
        return None

    try:
        return verify_firebase_token(token)
    except Exception as exc:
        logger.debug("Firebase token verification failed: %s", exc)
        return None
