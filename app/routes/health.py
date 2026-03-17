from __future__ import annotations

from fastapi import APIRouter

from core.paths import DATA_DIR

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/data")
def health_data() -> dict[str, object]:
    languages = sorted(
        path.name
        for path in DATA_DIR.iterdir()
        if path.is_dir() and (path / "lexicon.json").exists()
    )
    return {
        "status": "ok",
        "languages": languages,
    }


@router.get("/health/audio")
def health_audio() -> dict[str, object]:
    return {
        "status": "ok",
        "audio_enabled": True,
    }
