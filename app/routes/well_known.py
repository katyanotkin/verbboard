from fastapi import APIRouter
from fastapi.responses import JSONResponse

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


@router.get("/.well-known/assetlinks.json", include_in_schema=False)
async def assetlinks() -> JSONResponse:
    return JSONResponse(_ASSETLINKS)
