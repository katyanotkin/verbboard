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
}


@pytest.mark.parametrize("language", sorted(_PLUGIN_TENSE_KEYS))
def test_prompt_requests_every_optional_tense(language):
    prompt = _LANG_PROMPTS[language]
    for key in _PLUGIN_TENSE_KEYS[language]:
        assert f"{key}:" in prompt, f"{language} prompt does not request forms.{key}"
