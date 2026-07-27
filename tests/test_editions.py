"""Unit tests for core/editions.py -- edition-scoped study language resolution.

No TestClient here -- app.main is already imported by tests/conftest.py before
any test module is collected, which triggers the language plugin self-registration
(core/main.py imports core.languages.{en,es,he,ru}.plugin). That registration
order (en, es, he, ru) is exactly what these tests rely on for the
order-preservation guarantee.
"""

from __future__ import annotations

from core.editions import active_study_plugins, is_study_language, resolve_study_language
from core.languages.config import FREE_STUDY_LANGUAGES, PLUS_EXTRA_STUDY_LANGUAGES, default_study_languages
from core.registry import all_plugins
from core.settings import load_settings

# ── active_study_plugins ──────────────────────────────────────────────────────


def test_active_study_plugins_free_edition_returns_registered_four():
    settings = load_settings()  # zero env vars -> free edition
    plugins = active_study_plugins(settings)
    assert set(plugins.keys()) == {"en", "es", "he", "ru"}


def test_active_study_plugins_preserves_registry_order_not_study_languages_order():
    """Order must match core.registry.all_plugins() (registration order), NOT
    alphabetical order and NOT settings.study_languages tuple order.

    This is the property most likely to silently break the home-page language
    picker if it regressed: registry order is (en, es, he, ru) while
    study_languages order is (en, ru, he, es) -- they genuinely differ.
    """
    settings = load_settings()
    plugins = active_study_plugins(settings)

    assert list(plugins.keys()) == list(all_plugins().keys())
    assert list(plugins.keys()) != list(settings.study_languages)


# ── is_study_language ─────────────────────────────────────────────────────────


def test_is_study_language_true_for_registered_free_language():
    settings = load_settings()
    assert is_study_language("en", settings) is True


def test_is_study_language_false_for_unregistered_plus_language():
    settings = load_settings()
    assert is_study_language("it", settings) is False


# ── resolve_study_language ────────────────────────────────────────────────────


def test_resolve_study_language_none_falls_back_to_hebrew():
    plugins = active_study_plugins(load_settings())
    assert resolve_study_language(None, plugins) == "he"


def test_resolve_study_language_unrecognized_code_falls_back_to_hebrew():
    plugins = active_study_plugins(load_settings())
    assert resolve_study_language("xx", plugins) == "he"


def test_resolve_study_language_exact_match_wins():
    plugins = active_study_plugins(load_settings())
    assert resolve_study_language("es", plugins) == "es"


# ── default_study_languages (pure function, no registry involved) ────────────


def test_default_study_languages_plus_adds_extras():
    assert default_study_languages("plus") == FREE_STUDY_LANGUAGES + PLUS_EXTRA_STUDY_LANGUAGES


def test_default_study_languages_free():
    assert default_study_languages("free") == FREE_STUDY_LANGUAGES


def test_default_study_languages_unknown_edition_falls_back_to_free():
    assert default_study_languages("anything-else") == FREE_STUDY_LANGUAGES
