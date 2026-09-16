"""Tests for core/languages/ru/validation.py's validate_ru_payload().

This is the extra post-generation sanity gate for cold (search-miss) Russian
verb autogeneration (issue #31) -- unlike pair-completion, there is no admin
review before the result goes live, so a bad aspect/form payload from Claude
must be caught here instead of publishing a broken conjugation table.
"""

from __future__ import annotations

from core.languages.ru.validation import validate_ru_payload


def _forms(**overrides):
    base = {
        "past": {"m": "делал"},
        "imperative": {"sg": "делай"},
    }
    base.update(overrides)
    return base


class TestValidAspects:
    def test_valid_imperfective(self):
        forms = _forms(present={"1sg": "делаю"})
        assert validate_ru_payload("делать", {"aspect": "imperfective", "pair": "сделать"}, forms) is None

    def test_valid_perfective(self):
        forms = _forms(future={"1sg": "сделаю"})
        assert validate_ru_payload("сделать", {"aspect": "perfective", "pair": "делать"}, forms) is None

    def test_valid_biaspectual(self):
        forms = _forms(present={"1sg": "исследую"}, future={"1sg": "исследую"})
        assert validate_ru_payload("исследовать", {"aspect": "biaspectual", "pair": ""}, forms) is None

    def test_valid_without_pair(self):
        forms = _forms(present={"1sg": "делаю"})
        assert validate_ru_payload("делать", {"aspect": "imperfective", "pair": ""}, forms) is None


class TestAspectFormMismatch:
    def test_imperfective_missing_present(self):
        forms = _forms()
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": ""}, forms)
        assert reason is not None
        assert "present" in reason

    def test_imperfective_with_future_rejected(self):
        forms = _forms(present={"1sg": "делаю"}, future={"1sg": "сделаю"})
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": ""}, forms)
        assert reason is not None
        assert "future" in reason

    def test_perfective_missing_future(self):
        forms = _forms()
        reason = validate_ru_payload("сделать", {"aspect": "perfective", "pair": ""}, forms)
        assert reason is not None
        assert "future" in reason

    def test_perfective_with_present_rejected(self):
        forms = _forms(present={"1sg": "делаю"}, future={"1sg": "сделаю"})
        reason = validate_ru_payload("сделать", {"aspect": "perfective", "pair": ""}, forms)
        assert reason is not None
        assert "present" in reason


class TestAspectField:
    def test_missing_aspect(self):
        forms = _forms(present={"1sg": "делаю"})
        reason = validate_ru_payload("делать", {"pair": ""}, forms)
        assert reason is not None
        assert "aspect" in reason

    def test_invalid_aspect_value(self):
        forms = _forms(present={"1sg": "делаю"})
        reason = validate_ru_payload("делать", {"aspect": "imperative", "pair": ""}, forms)
        assert reason is not None
        assert "aspect" in reason

    def test_morph_not_a_dict(self):
        reason = validate_ru_payload("делать", "imperfective", _forms(present={"1sg": "делаю"}))
        assert reason == "morph is not an object"


class TestSharedFormRequirements:
    def test_missing_past(self):
        forms = {"present": {"1sg": "делаю"}, "imperative": {"sg": "делай"}}
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": ""}, forms)
        assert reason is not None
        assert "past" in reason

    def test_missing_imperative(self):
        forms = {"present": {"1sg": "делаю"}, "past": {"m": "делал"}}
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": ""}, forms)
        assert reason is not None
        assert "imperative" in reason

    def test_empty_past_dict_rejected(self):
        forms = _forms(present={"1sg": "делаю"}, past={})
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": ""}, forms)
        assert reason is not None
        assert "past" in reason


class TestPairField:
    def test_pair_equal_to_lemma_rejected(self):
        forms = _forms(present={"1sg": "делаю"})
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": "делать"}, forms)
        assert reason is not None
        assert "pair" in reason

    def test_pair_equal_to_lemma_case_insensitive(self):
        forms = _forms(present={"1sg": "делаю"})
        reason = validate_ru_payload("Делать", {"aspect": "imperfective", "pair": "делать"}, forms)
        assert reason is not None

    def test_pair_not_cyrillic_rejected(self):
        forms = _forms(present={"1sg": "делаю"})
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": "sdelat"}, forms)
        assert reason is not None
        assert "Cyrillic" in reason

    def test_pair_mixed_script_rejected(self):
        forms = _forms(present={"1sg": "делаю"})
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": "сdelat"}, forms)
        assert reason is not None
        assert "Cyrillic" in reason

    def test_pair_not_a_string_rejected(self):
        forms = _forms(present={"1sg": "делаю"})
        reason = validate_ru_payload("делать", {"aspect": "imperfective", "pair": ["сделать"]}, forms)
        assert reason == "morph.pair is not a string"

    def test_biaspectual_with_nonempty_pair_rejected(self):
        forms = _forms(present={"1sg": "исследую"}, future={"1sg": "исследую"})
        reason = validate_ru_payload("исследовать", {"aspect": "biaspectual", "pair": "что-то"}, forms)
        assert reason is not None
        assert "biaspectual" in reason
