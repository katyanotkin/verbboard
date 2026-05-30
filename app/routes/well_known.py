import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

router = APIRouter()

# sha256_cert_fingerprints is filled in after the signing keystore is generated.
# See docs/pwa-android.md for the keytool command.
_ASSETLINKS = [
    {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.verbboard.app",
            "sha256_cert_fingerprints": ["PLACEHOLDER"],
        },
    }
]

_SW_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "sw.js")
_SW_CONTENT = open(_SW_PATH).read()


@router.get("/.well-known/assetlinks.json", include_in_schema=False)
async def assetlinks() -> JSONResponse:
    return JSONResponse(_ASSETLINKS)


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
