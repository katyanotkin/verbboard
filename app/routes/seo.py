import asyncio
import logging

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response

from core.sitemap_service import build_robots_txt, build_sitemap_xml

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/robots.txt", include_in_schema=False)
async def robots_txt() -> PlainTextResponse:
    return PlainTextResponse(build_robots_txt(), headers={"Cache-Control": "public, max-age=3600"})


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml() -> Response:
    try:
        xml = await asyncio.to_thread(build_sitemap_xml)
    except Exception:
        logger.exception("sitemap generation failed")
        return PlainTextResponse("sitemap unavailable", status_code=503, headers={"Cache-Control": "no-store"})
    return Response(xml, media_type="application/xml", headers={"Cache-Control": "public, max-age=3600"})
