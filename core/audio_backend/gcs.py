from __future__ import annotations

from collections.abc import Iterator

from google.cloud import storage

from .base import AudioBackend


class GCSAudioBackend(AudioBackend):
    def __init__(self, project: str, bucket: str):
        self.client = storage.Client(project=project)
        self.bucket = self.client.bucket(bucket)

    def exists(self, key: str) -> bool:
        blob = self.bucket.blob(key)
        return blob.exists()

    def read_bytes(self, key: str) -> bytes:
        blob = self.bucket.blob(key)
        return blob.download_as_bytes()

    def write_bytes(self, key: str, data: bytes) -> None:
        blob = self.bucket.blob(key)
        blob.upload_from_string(data)

    def list_keys(self, prefix: str) -> Iterator[str]:
        for blob in self.bucket.list_blobs(prefix=prefix):
            yield blob.name
