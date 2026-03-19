from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from core.models import Example, VerbEntry


def load_lexicon(path: Path) -> List[VerbEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    verbs = payload.get("verbs", [])
    entries: List[VerbEntry] = []
    for item in verbs:
        examples = [Example(dst=e["dst"]) for e in item.get("examples", [])]
        entries.append(
            VerbEntry(
                id=item["id"],
                rank=int(item["rank"]),
                lemma=item["lemma"],
                forms=item.get("forms", {}),
                examples=examples,
                morph=item.get("morph"),
                tags=item.get("tags"),
                display_lemma=item.get("display_lemma"),
                display_forms=item.get("display_forms"),
            )
        )
    entries.sort(key=lambda entry: entry.rank)
    return entries


def index_by_id(entries: List[VerbEntry]) -> Dict[str, VerbEntry]:
    return {entry.id: entry for entry in entries}
