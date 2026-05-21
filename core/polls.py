from __future__ import annotations

ACTIVE_POLL_ID = "feature_priority"

POLL_QUESTIONS: dict[str, dict[str, str]] = {
    "feature_priority": {
        "en": "What would you like to see next?",
        "ru": "Что бы вы хотели увидеть следующим?",
        "es": "¿Qué te gustaría ver a continuación?",
        "he": "מה הייתם רוצים לראות בהמשך?",
    }
}

# Each poll's options: list of (value, {lang: label}) pairs
POLL_OPTIONS: dict[str, list[tuple[str, dict[str, str]]]] = {
    "feature_priority": [
        (
            "search_english",
            {
                "en": "Search by English verb for any language",
                "ru": "Поиск по английскому глаголу в любом языке",
                "he": "חיפוש לפי פועל באנגלית בכל שפה",
                "es": "Buscar por verbo en inglés en cualquier idioma",
            },
        ),
        (
            "word_families",
            {
                "en": "Related words / word families",
                "ru": "Родственные слова / семейства слов",
                "he": "מילים קרובות / משפחות מילים",
                "es": "Palabras relacionadas / familias de palabras",
            },
        ),
        (
            "mobile_ux",
            {
                "en": "Mobile UX improvements",
                "ru": "Улучшение мобильного интерфейса",
                "he": "שיפורי חווית מובייל",
                "es": "Mejoras de UX móvil",
            },
        ),
        (
            "more_verbs",
            {
                "en": "More verbs coverage",
                "ru": "Больше глаголов",
                "he": "כיסוי יותר פעלים",
                "es": "Mayor cobertura de verbos",
            },
        ),
    ]
}


def get_poll_question(poll_id: str, language: str) -> str:
    questions = POLL_QUESTIONS.get(poll_id, {})
    return questions.get(language) or questions.get("en") or ""


def get_poll_options(poll_id: str, language: str) -> list[tuple[str, str]]:
    """Returns [(value, label)] for the given poll and UI language."""
    opts = POLL_OPTIONS.get(poll_id, [])
    result = []
    for value, labels in opts:
        label = labels.get(language) or labels.get("en") or value
        result.append((value, label))
    return result


def get_poll_valid_answers(poll_id: str) -> set[str]:
    return {value for value, _ in POLL_OPTIONS.get(poll_id, [])}
