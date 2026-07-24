import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

router = APIRouter()

# sha256_cert_fingerprints is the real Play App Signing key certificate (not
# the local upload-key keystore) -- copied from Play Console > Setup >
# App integrity > App signing key certificate after the first AAB upload.
_ASSETLINKS = [
    {
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {
            "namespace": "android_app",
            "package_name": "com.verbboard.app",
            "sha256_cert_fingerprints": [
                "3A:51:9F:C0:80:6A:91:31:16:71:4E:98:49:F8:B9:C2:F9:09:21:CE:06:E4:51:C7:2D:81:B5:40:42:85:F4:9C"
            ],
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
