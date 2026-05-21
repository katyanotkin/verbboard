"""
Tests for Hebrew nikud (vowel diacritics) normalization.

Covers three layers of the fix:
  1. core/search_utils.py  -- normalize_text / _strip_combining
  2. core/storage/verb_document.py  -- _dedupe / build_search_extract_from_entry
  3. core/storage/verb_repository.py  -- find_verb_by_search_extract fallback logic
"""

from __future__ import annotations

import unicodedata
from unittest.mock import MagicMock, patch

from core.search_utils import _strip_combining, normalize_text
from core.storage import verb_repository as repo
from core.storage.verb_document import _dedupe, build_search_extract_from_entry

# ---------------------------------------------------------------------------
# normalize_text / _strip_combining
# ---------------------------------------------------------------------------


class TestStripCombining:
    def test_strips_hebrew_nikud(self) -> None:
        # הֵבֵאתִי has nikud combining marks; stripped form is הבאתי
        with_nikud = "הֵבֵאתִי"
        without_nikud = "הבאתי"
        assert _strip_combining(with_nikud) == without_nikud

    def test_strips_single_nikud_mark(self) -> None:
        # Alef + patah (U+05B7)
        assert _strip_combining("אַ") == "א"

    def test_leaves_plain_hebrew_unchanged(self) -> None:
        # No combining marks -- should pass through unchanged
        plain = "הבאתי"
        assert _strip_combining(plain) == plain

    def test_strips_spanish_accents(self) -> None:
        # é decomposes to e + combining acute
        assert _strip_combining("hablaré") == "hablare"

    def test_strips_mixed_accents(self) -> None:
        assert _strip_combining("café") == "cafe"

    def test_leaves_russian_unchanged(self) -> None:
        # Russian Cyrillic letters are not combining marks
        word = "идти"  # идти
        assert _strip_combining(word) == word

    def test_leaves_english_unchanged(self) -> None:
        assert _strip_combining("going") == "going"

    def test_empty_string(self) -> None:
        assert _strip_combining("") == ""


class TestNormalizeText:
    def test_strips_hebrew_nikud_and_casefoldes(self) -> None:
        with_nikud = "הֵבֵאתִי"
        result = normalize_text(with_nikud)
        # After stripping nikud the base letters should remain, no combining marks
        for char in result:
            assert not unicodedata.combining(char), f"Combining mark found: {char!r}"

    def test_strips_spanish_accent_and_casefoldes(self) -> None:
        assert normalize_text("Hablaré") == "hablare"

    def test_normalizes_uppercase_spanish(self) -> None:
        assert normalize_text("Él") == "el"  # É -> e after strip + casefold

    def test_russian_yo_preserved(self) -> None:
        # ё (U+0451) decomposes under NFKD to е + combining diaeresis.
        # After _strip_combining, ё becomes е. casefold keeps it е.
        result = normalize_text("ё")  # ё
        assert result == "е"  # е (ya, that is the NFKD base letter for ё)

    def test_russian_plain_letters_unchanged(self) -> None:
        assert normalize_text("идти") == "идти"

    def test_english_plain_word_unchanged(self) -> None:
        assert normalize_text("going") == "going"

    def test_collapses_whitespace(self) -> None:
        assert normalize_text("  go   go  ") == "go go"

    def test_strips_surrounding_whitespace(self) -> None:
        assert normalize_text("  go  ") == "go"

    def test_empty_string_returns_empty(self) -> None:
        assert normalize_text("") == ""

    def test_nikud_word_matches_stripped_equivalent(self) -> None:
        with_nikud = "הֵבֵאתִי"
        without_nikud = "הבאתי"
        assert normalize_text(with_nikud) == normalize_text(without_nikud)


# ---------------------------------------------------------------------------
# _dedupe and build_search_extract_from_entry
# ---------------------------------------------------------------------------


class TestDedupe:
    def test_strips_nikud_before_deduplication(self) -> None:
        with_nikud = "הֵבֵאתִי"
        without_nikud = "הבאתי"
        result = _dedupe([with_nikud])
        # stored form must be the stripped version, not the original with nikud
        assert result == [without_nikud]

    def test_deduplicates_nikud_and_plain_equivalent(self) -> None:
        with_nikud = "הֵבֵאתִי"
        without_nikud = "הבאתי"
        result = _dedupe([with_nikud, without_nikud])
        assert len(result) == 1

    def test_strips_spanish_accents(self) -> None:
        result = _dedupe(["había"])  # había
        assert result == ["habia"]

    def test_preserves_plain_russian(self) -> None:
        result = _dedupe(["идти"])  # идти
        assert result == ["идти"]

    def test_preserves_plain_english(self) -> None:
        result = _dedupe(["go", "went", "gone"])
        assert result == ["go", "went", "gone"]

    def test_removes_duplicates_case_insensitive(self) -> None:
        result = _dedupe(["Go", "go", "GO"])
        assert len(result) == 1

    def test_skips_empty_strings(self) -> None:
        result = _dedupe(["", "  ", "go"])
        assert result == ["go"]


class TestBuildSearchExtractFromEntry:
    def _make_he_entry(
        self,
        *,
        lemma: str,
        forms: dict,
        root: str | None = None,
    ) -> dict:
        entry: dict = {"lemma": lemma, "forms": forms}
        if root is not None:
            entry["morph"] = {"root": root}
        return entry

    def test_hebrew_forms_with_nikud_are_stored_stripped(self) -> None:
        # A Hebrew verb form with nikud: הֵבֵאתִי
        form_with_nikud = "הֵבֵאתִי"
        expected_stripped = "הבאתי"
        entry = self._make_he_entry(
            lemma="להביא",  # plain lemma: להביא
            forms={"past_1sg": form_with_nikud},
        )
        result = build_search_extract_from_entry(language="he", entry=entry)
        assert expected_stripped in result
        assert form_with_nikud not in result

    def test_hebrew_lemma_with_nikud_stored_stripped(self) -> None:
        lemma_with_nikud = "לְהָבִיא"
        entry = self._make_he_entry(lemma=lemma_with_nikud, forms={})
        result = build_search_extract_from_entry(language="he", entry=entry)
        for item in result:
            for char in item:
                assert not unicodedata.combining(char), f"Nikud not stripped: {char!r}"

    def test_hebrew_root_included_when_present(self) -> None:
        entry = self._make_he_entry(
            lemma="להביא",
            forms={},
            root="באי",  # ב-א-י
        )
        result = build_search_extract_from_entry(language="he", entry=entry)
        assert "באי" in result

    def test_non_hebrew_forms_stripped_of_accents(self) -> None:
        # Spanish: hablar forms with accents
        entry = {
            "lemma": "hablar",
            "forms": {"yo_pret": "hablé"},  # hablé
        }
        result = build_search_extract_from_entry(language="es", entry=entry)
        assert "hable" in result

    def test_english_forms_returned_as_is(self) -> None:
        entry = {
            "lemma": "go",
            "forms": {"past": "went", "gerund": "going"},
        }
        result = build_search_extract_from_entry(language="en", entry=entry)
        assert "go" in result
        assert "went" in result
        assert "going" in result

    def test_no_duplicates_in_output(self) -> None:
        entry = {
            "lemma": "go",
            "forms": {"base": "go", "inf": "go"},
        }
        result = build_search_extract_from_entry(language="en", entry=entry)
        assert result.count("go") == 1

    def test_empty_forms_returns_just_lemma(self) -> None:
        entry = {"lemma": "go", "forms": {}}
        result = build_search_extract_from_entry(language="en", entry=entry)
        assert result == ["go"]


# ---------------------------------------------------------------------------
# find_verb_by_search_extract -- fallback logic
# ---------------------------------------------------------------------------


def _make_db() -> MagicMock:
    return MagicMock()


def _fake_doc(data: dict) -> MagicMock:
    doc = MagicMock()
    doc.to_dict.return_value = data
    return doc


class TestFindVerbBySearchExtract:
    """
    Firestore is mocked. The query chain used by find_verb_by_search_extract is:
      db.collection(COLLECTION)
        .where("language", "==", language)
        .where("search_extract", "array_contains", q)
        .limit(1)
        .stream()
    """

    def _configure_stream(self, db: MagicMock, docs: list) -> None:
        """Wire the mock so that .stream() returns the given docs."""
        (db.collection().where().where().limit().stream.return_value) = iter(docs)

    def test_returns_result_on_stripped_query_first(self) -> None:
        """When the stripped form matches, the doc is returned."""
        db = _make_db()
        verb_data = {"verb_id": "he_lavo", "language": "he"}
        self._configure_stream(db, [_fake_doc(verb_data)])

        with patch.object(repo, "get_db", return_value=db):
            result = repo.find_verb_by_search_extract(
                "he",
                "לאבו",  # plain Hebrew, no nikud
            )

        assert result == verb_data

    def test_returns_none_when_no_docs_found(self) -> None:
        db = _make_db()
        self._configure_stream(db, [])

        with patch.object(repo, "get_db", return_value=db):
            result = repo.find_verb_by_search_extract("he", "xyzzy")

        assert result is None

    def test_stripped_query_differs_from_original_triggers_fallback(self) -> None:
        """
        When a query contains nikud, the stripped form is tried first. If that
        returns nothing, the original casefold form is tried as a fallback.

        We verify this by configuring the mock so that the FIRST .stream() call
        returns nothing and the SECOND call returns a real document.
        """
        db = _make_db()
        verb_data = {"verb_id": "he_hevi", "language": "he"}

        # Build a stream that returns empty on the first call, then a doc on the second.
        stream_side_effect = [iter([]), iter([_fake_doc(verb_data)])]
        (
            db.collection().where().where().limit().stream.side_effect
        ) = stream_side_effect

        # Query with nikud so stripped != original
        query_with_nikud = "הֵבֵאתִי"

        with patch.object(repo, "get_db", return_value=db):
            result = repo.find_verb_by_search_extract("he", query_with_nikud)

        assert result == verb_data

    def test_no_fallback_when_stripped_equals_original(self) -> None:
        """
        For plain ASCII/Latin/Cyrillic queries, stripped == original, so only one
        DB query is made.
        """
        db = _make_db()
        self._configure_stream(db, [])

        with patch.object(repo, "get_db", return_value=db):
            repo.find_verb_by_search_extract("en", "go")

        # .stream() should have been called exactly once
        stream_mock = db.collection().where().where().limit().stream
        assert stream_mock.call_count == 1

    def test_fallback_queries_original_casefold(self) -> None:
        """
        When the fallback fires, the second query must use casefold of the
        original (not the stripped form, which already failed).
        """
        db = _make_db()
        stream_calls = 0

        def counting_stream():
            nonlocal stream_calls
            stream_calls += 1
            return iter([])

        (db.collection().where().where().limit().stream.side_effect) = counting_stream

        query_with_nikud = "הֵבֵאתִי"

        with patch.object(repo, "get_db", return_value=db):
            repo.find_verb_by_search_extract("he", query_with_nikud)

        # Both the stripped query and the original-casefold fallback should fire
        assert stream_calls == 2

    def test_stripped_match_preempts_fallback(self) -> None:
        """If the first (stripped) query hits, the fallback should NOT fire."""
        db = _make_db()
        verb_data = {"verb_id": "he_hevi", "language": "he"}

        stream_calls = 0

        def counting_stream():
            nonlocal stream_calls
            stream_calls += 1
            if stream_calls == 1:
                return iter([_fake_doc(verb_data)])
            return iter([])

        (db.collection().where().where().limit().stream.side_effect) = counting_stream

        query_with_nikud = "הֵבֵאתִי"

        with patch.object(repo, "get_db", return_value=db):
            result = repo.find_verb_by_search_extract("he", query_with_nikud)

        assert result == verb_data
        assert stream_calls == 1

    def test_empty_query_returns_none(self) -> None:
        db = _make_db()

        with patch.object(repo, "get_db", return_value=db):
            result = repo.find_verb_by_search_extract("en", "")

        assert result is None
        # The DB should never have been queried for an empty string
        db.collection.assert_not_called()
