from __future__ import annotations

import asyncio
import logging
import os
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request
from google.auth.exceptions import GoogleAuthError
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from core.persona_review_service import run_review

logger = logging.getLogger(__name__)
router = APIRouter()


def _verify_scheduler_token(authorization: str, audience: str, invoker_email: str) -> None:
    """Accept only a Google-signed OIDC token for this audience from the scheduler's service account."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing token")
    try:
        claims = id_token.verify_oauth2_token(authorization[7:], google_requests.Request(), audience=audience)
    except (ValueError, GoogleAuthError) as error:
        raise HTTPException(status_code=401, detail="invalid token") from error
    if not claims.get("email_verified") or claims.get("email") != invoker_email:
        raise HTTPException(status_code=403, detail="wrong caller")


@router.post("/internal/persona-review")
async def persona_review(request: Request, dry_run: bool = False, force: bool = False) -> dict[str, object]:
    """Called by Cloud Scheduler (issue #142). Disabled (404) unless all three settings are present."""
    audience = os.getenv("PERSONA_REVIEW_AUDIENCE", "")
    invoker_email = os.getenv("PERSONA_REVIEW_INVOKER_EMAIL", "")
    repo = os.getenv("PERSONA_REVIEW_REPO", "")
    token = os.getenv("GITHUB_ISSUES_TOKEN", "")
    if not (audience and invoker_email and repo and (token or dry_run)):
        raise HTTPException(status_code=404)

    await asyncio.to_thread(_verify_scheduler_token, request.headers.get("authorization", ""), audience, invoker_email)
    try:
        return await asyncio.to_thread(
            run_review,
            today=datetime.now(UTC).date(),
            repo=repo,
            token=token,
            dry_run=dry_run,
            force=force,
        )
    except Exception:
        logger.exception("PERSONA_REVIEW_FAILED")
        raise HTTPException(status_code=502, detail="review failed") from None
