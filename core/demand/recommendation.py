from __future__ import annotations

import re
from functools import lru_cache
from typing import Literal
from urllib.parse import quote

import requests

Recommendation = Literal["new_verb_candidate", "reject_noise"]

WIKTIONARY_LANGUAGE_HEADERS = {
    "en": "==English==",
    "es": "==Spanish==",
    "ru": "==Russian==",
    "he": "==Hebrew==",
}


def _is_single_token(text: str) -> bool:
    return " " not in text.strip()


def _looks_like_word(text: str) -> bool:
    return bool(re.fullmatch(r"[^\W\d_]+", text))


def _script_matches_language(language: str, text: str) -> bool:
    if language == "en":
        return bool(re.fullmatch(r"[a-zA-Z]+", text))
    if language == "es":
        return bool(re.fullmatch(r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ]+", text))
    if language == "ru":
        return bool(re.fullmatch(r"[а-яА-ЯёЁ]+", text))
    if language == "he":
        return bool(re.fullmatch(r"[\u0590-\u05FF]+", text))
    return True


@lru_cache(maxsize=2048)
def _fetch_wiktionary_raw(word: str) -> str | None:
    url = f"https://en.wiktionary.org/w/index.php?title={quote(word)}&action=raw"

    try:
        response = requests.get(
            url,
            timeout=5,
            headers={"User-Agent": "verbboard-demand-review/1.0"},
        )
        if response.status_code != 200:
            return None
        return response.text
    except requests.RequestException:
        return None


def _wiktionary_has_language_entry(language: str, word: str) -> bool:
    raw_text = _fetch_wiktionary_raw(word)
    if not raw_text:
        return False

    if "Wiktionary does not yet have an entry for" in raw_text:
        return False

    header = WIKTIONARY_LANGUAGE_HEADERS.get(language)
    if not header:
        return False

    return header in raw_text


def recommend(
    *,
    language: str,
    normalized_query: str,
    count: int,
    cutoff: int,
    use_external_check: bool = True,
) -> tuple[Recommendation, str]:
    if not normalized_query:
        return "reject_noise", "empty"

    if not _is_single_token(normalized_query):
        return "reject_noise", "multi_token"

    if not _looks_like_word(normalized_query):
        return "reject_noise", "invalid_chars"

    if not _script_matches_language(language, normalized_query):
        return "reject_noise", "script_mismatch"

    if count < cutoff:
        return "reject_noise", "below_cutoff"

    if use_external_check:
        if not _wiktionary_has_language_entry(language, normalized_query):
            return "reject_noise", "no_wiktionary_language_entry"

    return "new_verb_candidate", "passes_all_checks"
