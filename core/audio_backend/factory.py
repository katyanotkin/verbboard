from __future__ import annotations

from core.settings import Settings

from .base import AudioBackend
from .local import LocalAudioBackend


def create_audio_backend(settings: Settings) -> AudioBackend:
    if settings.audio_backend == "local":
        return LocalAudioBackend(settings.local_audio_cache_dir)

    if settings.audio_backend == "gcs":
        from .gcs import GCSAudioBackend

        return GCSAudioBackend(
            project=settings.google_cloud_project,
            bucket=settings.audio_bucket,
        )

    raise RuntimeError(f"Unsupported AUDIO_BACKEND={settings.audio_backend!r}")
