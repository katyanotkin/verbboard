from __future__ import annotations

from core.demand.recommendation import recommend


def test_recommendation_regression_cases(monkeypatch) -> None:
    wiktionary_truth = {
        ("en", "grey"): True,
        ("es", "hable"): True,
        ("es", "blue"): False,
        ("ru", "пить"): True,
        ("ru", "зынаешь"): False,
    }

    def fake_wiktionary_has_language_entry(language: str, word: str) -> bool:
        return wiktionary_truth.get((language, word), False)

    monkeypatch.setattr(
        "core.demand.recommendation._wiktionary_has_language_entry",
        fake_wiktionary_has_language_entry,
    )

    cases = [
        ("en", "grey", 2, 2, ("new_verb_candidate", "passes_all_checks")),
        ("es", "hable", 2, 2, ("new_verb_candidate", "passes_all_checks")),
        ("es", "blue", 2, 2, ("reject_noise", "no_wiktionary_language_entry")),
        ("ru", "пить", 2, 2, ("new_verb_candidate", "passes_all_checks")),
        ("ru", "зынаешь", 2, 2, ("reject_noise", "no_wiktionary_language_entry")),
        ("he", "färgstark", 2, 2, ("reject_noise", "script_mismatch")),
    ]

    for language, query, count, cutoff, expected in cases:
        result = recommend(
            language=language,
            normalized_query=query,
            count=count,
            cutoff=cutoff,
        )
        assert result == expected


def test_recommendation_rejects_below_cutoff(monkeypatch) -> None:
    monkeypatch.setattr(
        "core.demand.recommendation._wiktionary_has_language_entry",
        lambda language, word: True,
    )

    result = recommend(
        language="ru",
        normalized_query="пить",
        count=1,
        cutoff=2,
    )

    assert result == ("reject_noise", "below_cutoff")
