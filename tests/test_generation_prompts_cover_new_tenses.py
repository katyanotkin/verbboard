"""Every optional tense a plugin renders must be requested by that language's generation prompt.

Both generation paths (Claude via get_cached_system, Gemini autogen via _build_verb_prompt) read
core.settings_ai._LANG_PROMPTS, so a form key the board reads but the prompt never asks for would
silently leave newly generated verbs without that section.
"""

import pytest

from core.settings_ai import _LANG_PROMPTS

_PLUGIN_TENSE_KEYS = {
    "fr": ("conditionnel_present", "subjonctif_present"),
    "es": ("conditional", "subjunctive_present", "subjunctive_imperfect"),
    "it": ("condizionale_presente", "congiuntivo_presente", "congiuntivo_imperfetto"),
    "pt": ("conditional", "subjunctive_present", "subjunctive_imperfect"),
}


@pytest.mark.parametrize("language", sorted(_PLUGIN_TENSE_KEYS))
def test_prompt_requests_every_optional_tense(language):
    prompt = _LANG_PROMPTS[language]
    for key in _PLUGIN_TENSE_KEYS[language]:
        assert f"{key}:" in prompt, f"{language} prompt does not request forms.{key}"


# Number of required example categories per language prompt (the stated sentence count must cover them).
_REQUIRED_EXAMPLE_CATEGORIES = {"en": 6, "ru": 7, "es": 7, "it": 7, "fr": 7, "pt": 7, "he": 6}


@pytest.mark.parametrize("language", sorted(_REQUIRED_EXAMPLE_CATEGORIES))
def test_prompt_example_count_covers_required_categories(language):
    import re

    prompt = _LANG_PROMPTS[language]
    match = re.search(r"examples: (?:exactly )?(\d+) sentences", prompt)
    assert match, f"{language} prompt states no example count"
    assert int(match.group(1)) >= _REQUIRED_EXAMPLE_CATEGORIES[language]


def test_ru_prompt_distributes_examples_per_aspect():
    prompt = _LANG_PROMPTS["ru"]
    assert "imperfective: 3 present" in prompt
    assert "perfective: 3 future" in prompt


def test_en_prompt_exercises_gerund():
    assert "gerund" in _LANG_PROMPTS["en"].split("examples:")[1]


def test_tr_prompt_requires_onlar():
    assert "onlar" in _LANG_PROMPTS["tr"].split("examples:")[1]


def test_english_prompt_requires_real_imperatives():
    assert "real command" in _LANG_PROMPTS["en"]
