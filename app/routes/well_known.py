import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from core.settings import load_settings

router = APIRouter()

_SW_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "sw.js")
_SW_CONTENT = open(_SW_PATH).read()
_MANIFEST_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "manifest.json")
_MANIFEST_CONTENT = open(_MANIFEST_PATH).read()


@router.get("/.well-known/assetlinks.json", include_in_schema=False)
async def assetlinks() -> JSONResponse:
    settings = load_settings()
    return JSONResponse(
        [
            {
                "relation": ["delegate_permission/common.handle_all_urls"],
                "target": {
                    "namespace": "android_app",
                    "package_name": settings.android_package_name,
                    "sha256_cert_fingerprints": list(settings.android_cert_fingerprints),
                },
            }
        ]
    )


@router.get("/sw.js", include_in_schema=False)
async def service_worker() -> Response:
    # Serve sw.js from the root path so its default scope is "/".
    # Service-Worker-Allowed: / overrides the path-based scope restriction that
    # would otherwise limit the SW to /static/ when registered from /static/sw.js.
    return Response(
        content=_SW_CONTENT,
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


@router.get("/manifest.json", include_in_schema=False)
async def manifest() -> Response:
    # Alias of /static/manifest.json (the URL the pages' <link rel="manifest">
    # points at): /manifest.json is the first path people and PWA/TWA tooling
    # try by hand, and it used to 404.
    return Response(content=_MANIFEST_CONTENT, media_type="application/manifest+json")
