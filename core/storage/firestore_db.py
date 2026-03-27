from __future__ import annotations

from google.cloud import firestore

_db: firestore.Client | None = None


def get_db() -> firestore.Client:
    global _db

    if _db is None:
        _db = firestore.Client()

    return _db
