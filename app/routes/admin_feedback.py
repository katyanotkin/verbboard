from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.admin_feedback_service import (
    hide_feedback_by_id,
    list_feedback_facets,
    list_feedback_rows,
    unhide_feedback_by_id,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/feedback", response_class=HTMLResponse)
async def feedback_admin_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "admin_feedback.html",
        {
            "admin_prefix": request.scope.get("root_path", "")
            + request.url.path.removesuffix("/feedback"),
            "feedback_api_base": request.url.path.removesuffix("/feedback")
            + "/api/feedback",
        },
    )


@router.get("/api/feedback")
async def list_feedback(
    sort: str = Query("newest"),
    visibility: str = Query("visible"),
    page: str = Query(""),
    language: str = Query(""),
    source: str = Query(""),
    query: str = Query(""),
    limit: int = Query(200, ge=1, le=1000),
) -> JSONResponse:
    try:
        feedback_rows = list_feedback_rows(
            sort=sort,
            visibility=visibility,
            page=page,
            language=language,
            source=source,
            query=query,
            limit=limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return JSONResponse({"feedback": feedback_rows})


@router.get("/api/feedback/facets")
async def feedback_facets(
    limit: int = Query(1000, ge=1, le=2000),
) -> JSONResponse:
    return JSONResponse(list_feedback_facets(limit=limit))


@router.post("/api/feedback/{doc_id}/hide")
async def hide_feedback(doc_id: str) -> JSONResponse:
    if not hide_feedback_by_id(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")

    return JSONResponse({"hidden": doc_id})


@router.post("/api/feedback/{doc_id}/unhide")
async def unhide_feedback(doc_id: str) -> JSONResponse:
    if not unhide_feedback_by_id(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")

    return JSONResponse({"unhidden": doc_id})
