from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

from core.account_deletion import delete_account
from core.auth.firebase_auth import get_optional_auth_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/account")


@router.delete("")
def delete_account_route(request: Request):
    user = get_optional_auth_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        delete_account(user.uid)
    except Exception:
        logger.exception("Account deletion failed for uid=%s", user.uid)
        raise HTTPException(status_code=500, detail="Account deletion failed, please try again") from None

    return {"ok": True}
