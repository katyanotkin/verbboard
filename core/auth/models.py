from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AuthUser:
    uid: str
    email: str
    name: str
    picture: str
