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


@lru_cache(maxsize=1)
def initialize_firebase_admin() -> None:
    if firebase_admin._apps:
        return

    firebase_admin.initialize_app(credentials.ApplicationDefault())


def verify_firebase_token(token: str) -> AuthUser:
    settings = load_settings()
    if (
        settings.environment == "local"
        and settings.allow_local_dev_auth
        and token == "local-dev"
    ):
        return AuthUser(
            uid="local-dev-user",
            email="dev@example.com",
            name="Local Dev",
            picture="",
        )

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
