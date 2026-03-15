from __future__ import annotations
from abc import ABC, abstractmethod


class AudioBackend(ABC):
    @abstractmethod
    def exists(self, key: str) -> bool:
        pass

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        pass

    @abstractmethod
    def write_bytes(self, key: str, data: bytes) -> None:
        pass
