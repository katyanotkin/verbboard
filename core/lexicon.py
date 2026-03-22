from __future__ import annotations

import json
from pathlib import Path

from core.lexicon_loader import lexicon_path_for_language
from core.models import Example, VerbEntry
from core.supported_languages import supported_languages_list


class LexiconStore:
    def __init__(self) -> None:
        self._entries_by_language: dict[str, list[VerbEntry]] = {}
        self._index_by_language: dict[str, dict[str, VerbEntry]] = {}

    def preload_all(self) -> None:
        for language in supported_languages_list():
            path = lexicon_path_for_language(language)
            entries = load_lexicon(path)
            self._entries_by_language[language] = entries
            self._index_by_language[language] = index_by_id(entries)

    def get_entries(self, language: str) -> list[VerbEntry]:
        if language not in self._entries_by_language:
            raise RuntimeError(f"Lexicon not preloaded for language={language}")
        return self._entries_by_language[language]

    def get_entry(self, language: str, verb_id: str) -> VerbEntry:
        if language not in self._index_by_language:
            raise RuntimeError(f"Lexicon not preloaded for language={language}")
        return self._index_by_language[language][verb_id]

    def loaded_languages(self) -> list[str]:
        return sorted(self._entries_by_language.keys())


lexicon_store = LexiconStore()


def load_lexicon(path: Path) -> list[VerbEntry]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    verbs = payload.get("verbs", [])
    entries: list[VerbEntry] = []
    for item in verbs:
        examples = [Example(dst=example["dst"]) for example in item.get("examples", [])]
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


def index_by_id(entries: list[VerbEntry]) -> dict[str, VerbEntry]:
    return {entry.id: entry for entry in entries}
