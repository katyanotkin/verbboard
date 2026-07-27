from __future__ import annotations

from core.registry import LanguagePlugin, all_plugins
from core.settings import Settings, load_settings


def active_study_plugins(settings: Settings | None = None) -> dict[str, LanguagePlugin]:
    """Registered language plugins allowed for study under the current edition.

    Iterates all_plugins() (not study_languages) so registry insertion order --
    and therefore picker order -- is preserved. An allowlisted-but-unregistered
    language (e.g. Plus's it/fr before those plugins exist) is silently absent,
    not an error: this is what keeps EDITION=plus a no-op before those plugins ship.
    """
    allowed = set((settings or load_settings()).study_languages)
    return {code: plugin for code, plugin in all_plugins().items() if code in allowed}


def is_study_language(language: str, settings: Settings | None = None) -> bool:
    return language in active_study_plugins(settings)


def resolve_study_language(language: str | None, plugins: dict[str, LanguagePlugin]) -> str:
    """Pick the active study language for a request, falling back to Hebrew."""
    selected = language or "he"
    if selected not in plugins:
        selected = "he" if "he" in plugins else next(iter(plugins))
    return selected
