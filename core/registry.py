from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from core.models import Board, VerbEntry


BuildBoardFn = Callable[[VerbEntry, str, str], Board]


@dataclass(frozen=True)
class LanguagePlugin:
    language: str
    display_name: str
    build_board: BuildBoardFn


_PLUGINS: Dict[str, LanguagePlugin] = {}


def register(plugin: LanguagePlugin) -> None:
    _PLUGINS[plugin.language] = plugin


def get(language: str) -> LanguagePlugin:
    return _PLUGINS[language]


def all_plugins() -> Dict[str, LanguagePlugin]:
    return dict(_PLUGINS)
