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
        (
            "more_languages",
            {
                "en": "More languages to study",
                "ru": "Больше языков для изучения",
                "he": "יותר שפות ללימוד",
                "es": "Más idiomas para estudiar",
            },
        ),
    ]
}

# Options retired from display (kept in POLL_OPTIONS so admin analytics can still
# label historic votes) -- mobile_ux is superseded by more_languages; more_verbs
# coverage is already driven by demand signals, not the poll.
POLL_HIDDEN_OPTIONS: dict[str, set[str]] = {
    "feature_priority": {"mobile_ux", "more_verbs"},
}


def get_poll_question(poll_id: str, language: str) -> str:
    questions = POLL_QUESTIONS.get(poll_id, {})
    return questions.get(language) or questions.get("en") or ""


def get_poll_options(poll_id: str, language: str) -> list[tuple[str, str]]:
    """Returns [(value, label)] for the given poll and UI language, excluding hidden options."""
    opts = POLL_OPTIONS.get(poll_id, [])
    hidden = POLL_HIDDEN_OPTIONS.get(poll_id, set())
    result = []
    for value, labels in opts:
        if value in hidden:
            continue
        label = labels.get(language) or labels.get("en") or value
        result.append((value, label))
    return result


def get_poll_valid_answers(poll_id: str) -> set[str]:
    hidden = POLL_HIDDEN_OPTIONS.get(poll_id, set())
    return {value for value, _ in POLL_OPTIONS.get(poll_id, []) if value not in hidden}
