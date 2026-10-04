from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from core.audio_report_service import AudioReportError, submit_audio_report_async
from core.auth.firebase_auth import get_optional_auth_user

router = APIRouter()


class AudioReportRequest(BaseModel):
    language: str = Field(min_length=2, max_length=3)
    verb_id: str = Field(min_length=1, max_length=80)
    voice: str = Field(max_length=10)
    form_key: str = Field(min_length=1, max_length=80)
    reason: str = Field(max_length=20)
    comment: str | None = Field(default=None, max_length=1000)
    ui_language: str | None = Field(default=None, max_length=5)


@router.post("/api/audio_report")
async def post_audio_report(request: Request, body: AudioReportRequest) -> JSONResponse:
    user = get_optional_auth_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        result = await submit_audio_report_async(uid=user.uid, **body.model_dump())
    except AudioReportError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    return JSONResponse(result)
