from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.paths import DATA_DIR


def lexicon_path_for_language(language: str) -> Path:
    return DATA_DIR / language / "lexicon.json"


def load_required_lexicon_payload(language: str) -> dict[str, Any]:
    lexicon_path = lexicon_path_for_language(language)

    if not lexicon_path.exists():
        raise RuntimeError(
            f"Missing generated lexicon for language={language}: {lexicon_path}. "
            "Rebuild the Docker image so lexicons are generated at build time."
        )

    try:
        payload = json.loads(lexicon_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"Invalid generated lexicon JSON for language={language}: {lexicon_path}"
        ) from error

    if not isinstance(payload, dict):
        raise RuntimeError(
            f"Invalid generated lexicon payload for language={language}: "
            f"expected top-level object in {lexicon_path}"
        )

    return payload
