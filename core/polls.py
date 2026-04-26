from __future__ import annotations

ACTIVE_POLL_ID = "cross_device_progress"

POLL_QUESTIONS: dict[str, dict[str, str]] = {
    "cross_device_progress": {
        "en": "Want your progress saved across devices?",
        "ru": "Хотите сохранять прогресс на разных устройствах?",
        "es": "¿Quieres guardar tu progreso entre dispositivos?",
        "he": "רוצה לשמור את ההתקדמות שלך בין מכשירים?",
    }
}


def get_poll_question(poll_id: str, language: str) -> str:
    questions = POLL_QUESTIONS.get(poll_id, {})
    return questions.get(language) or questions.get("en") or ""
