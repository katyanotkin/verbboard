from __future__ import annotations

from core.settings import Settings

from .base import AudioBackend
from .gcs import GCSAudioBackend


def create_audio_backend(settings: Settings) -> AudioBackend:
    return GCSAudioBackend(
        project=settings.google_cloud_project,
        bucket=settings.audio_bucket,
    )
