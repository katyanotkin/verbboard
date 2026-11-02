"""Tie each example sentence to the conjugated form it shows (the "target").

An example's `target` says which cell of `forms` (tense + person) appears in the
sentence and where, so a practice page can blank exactly that word. Offsets are
code-point offsets into the native sentence (`src` when present, else `dst`),
computed here and never by an LLM.

Every writer of examples calls `tag_examples()`; the loader calls
`parse_example_target()`, which re-validates on every load so a stale tag (forms
or sentence edited afterwards) degrades to "untagged" rather than a wrong blank.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable, Optional

TARGET_VERSION = 1
# A sentence whose word fits several cells (en "walked" = past and past participle) is tagged with
# all of them so the practice label stays truthful; more than this many is too vague to practice.
MAX_LABELS_PER_TARGET = 3

# Elided / leading subject pronouns French forms are stored with ("il aimait", "j'aime").
_FR_PRONOUN_TOKENS = ("je", "j'", "tu", "il", "elle", "on", "nous", "vous", "ils", "elles")
_ES_SUBJUNCTIVE_SUFFIXES = (("ramos", "semos"), ("rais", "seis"), ("ras", "ses"), ("ran", "sen"), ("ra", "se"))
_VOWELS = "aeiouáéíóú"


# Cells the board never shows (the feminine-plural imperative is literary and error-prone), so a
# practice label for them would point at a row the learner cannot find.
_UNPRACTICED_CELLS = {("he", "imperative", "fp")}

# Subject pronouns per person key, used to pick the label when several cells share a surface form
# ("הם נתנו" is 3pl, not 1pl). Keys are the person keys stored in `forms`.
_SUBJECT_WORDS: dict[str, dict[str, tuple[str, ...]]] = {
    "he": {
        "1sg": ("אני",),
        "2msg": ("אתה",),
        "2fsg": ("את",),
        "3msg": ("הוא",),
        "3fsg": ("היא",),
        "1pl": ("אנחנו", "אנו"),
        "2mpl": ("אתם",),
        "2fpl": ("אתן",),
        "3pl": ("הם", "הן"),
        "m_sg": ("הוא", "אתה", "אני"),
        "f_sg": ("היא", "את", "אני"),
        "m_pl": ("הם", "אתם", "אנחנו"),
        "f_pl": ("הן", "אתן", "אנחנו"),
    },
    "fr": {
        "je": ("je", "j'"),
        "tu": ("tu",),
        "il": ("il", "elle", "on"),
        "nous": ("nous",),
        "vous": ("vous",),
        "ils": ("ils", "elles"),
    },
    "it": {
        "io": ("io",),
        "tu": ("tu",),
        "lui": ("lui", "lei", "egli"),
        "noi": ("noi",),
        "voi": ("voi",),
        "loro": ("loro", "essi"),
    },
    "es": {
        "yo": ("yo",),
        "tu": ("tú", "tu"),
        "el": ("él", "ella", "usted"),
        "nos": ("nosotros", "nosotras"),
        "vosotros": ("vosotros", "vosotras"),
        "ellos": ("ellos", "ellas", "ustedes"),
    },
    "tr": {"ben": ("ben",), "sen": ("sen",), "o": ("o",), "biz": ("biz",), "siz": ("siz",), "onlar": ("onlar",)},
    "ru": {"1sg": ("я",), "2sg": ("ты",), "3sg": ("он", "она", "оно"), "1pl": ("мы",), "2pl": ("вы",), "3pl": ("они",)},
}
_SUBJECT_WINDOW_WORDS = 3


@dataclass(frozen=True)
class FormCell:
    tense: str
    person: Optional[str]
    value: str

    @property
    def path(self) -> str:
        return self.tense if self.person is None else f"{self.tense}.{self.person}"


def native_sentence(example: dict[str, Any]) -> str:
    """The native-language sentence, mirroring verb_loader's `src or dst` rule."""
    sentence = example.get("src") or example.get("dst")
    return sentence if isinstance(sentence, str) else ""


def iter_form_cells(forms: Any) -> Iterable[FormCell]:
    """Yield every string cell of `forms` (flat `tense: str` or nested `tense: {person: str}`)."""
    if not isinstance(forms, dict):
        return
    for tense, value in forms.items():
        if isinstance(value, str):
            if value.strip():
                yield FormCell(tense, None, value.strip())
        elif isinstance(value, dict):
            for person, text in value.items():
                if isinstance(text, str) and text.strip():
                    yield FormCell(tense, person, text.strip())


def get_cell(forms: Any, tense: str, person: Optional[str]) -> Optional[FormCell]:
    for cell in iter_form_cells(forms):
        if cell.tense == tense and cell.person == person:
            return cell
    return None


# ---------------------------------------------------------------------------
# Folding: compare sentence and form on the same footing, keeping a map back to
# the original character offsets.
# ---------------------------------------------------------------------------


def _fold_char(language: str, ch: str, keep_marks: bool = False) -> str:
    if ch in "’‘ʼ":
        return "'"
    if language == "ru":
        if ch == "́":
            return ""
        if ch == "ё":
            return "е"
        if ch == "Ё":
            return "е"
    if language == "he" and not keep_marks and "֐" <= ch <= "׿" and unicodedata.category(ch) == "Mn":
        return ""
    if language == "tr":
        if ch == "I":
            return "ı"
        if ch == "İ":
            return "i"
    lowered = ch.lower()
    return lowered if len(lowered) == 1 else ch


def fold_with_map(language: str, text: str, keep_marks: bool = False) -> tuple[str, list[int]]:
    """Fold `text`; `index_map[i]` is the original offset of folded char i."""
    folded: list[str] = []
    index_map: list[int] = []
    for offset, ch in enumerate(text):
        piece = _fold_char(language, ch, keep_marks)
        if piece:
            folded.append(piece)
            index_map.append(offset)
    return "".join(folded), index_map


def fold(language: str, text: str) -> str:
    return fold_with_map(language, text)[0]


# ---------------------------------------------------------------------------
# Accepted spellings of one form cell.
# ---------------------------------------------------------------------------


def _strip_fr_pronoun(value: str) -> str:
    lowered = value.lower().replace("’", "'")
    for token in _FR_PRONOUN_TOKENS:
        if token.endswith("'") and lowered.startswith(token):
            return value[len(token) :].strip()
        if lowered.startswith(token + " "):
            return value[len(token) + 1 :].strip()
    return value


def _agreement_variants(language: str, value: str) -> list[str]:
    """Participle agreement for compound forms stored in one gender/number (fr/it)."""
    if " " not in value:
        return []
    if language == "fr" and value.endswith("é"):
        return [value + "e", value + "s", value + "es"]
    if language == "it" and value.endswith("o"):
        stem = value[:-1]
        return [stem + "a", stem + "i", stem + "e"]
    return []


def _es_subjunctive_variants(value: str) -> list[str]:
    for suffix, replacement in _ES_SUBJUNCTIVE_SUFFIXES:
        if value.endswith(suffix) and len(value) > len(suffix) and value[-len(suffix) - 1] in _VOWELS:
            return [value[: -len(suffix)] + replacement]
    return []


def variants_for(language: str, cell: FormCell) -> list[str]:
    """Surface strings accepted for `cell`, longest/most specific first, de-duplicated."""
    values = [part.strip() for part in cell.value.split("/") if part.strip()]
    variants: list[str] = []
    for value in values:
        variants.append(value)
        if language == "fr":
            stripped = _strip_fr_pronoun(value)
            if stripped != value:
                variants.append(stripped)
        for base in list(variants):
            variants.extend(_agreement_variants(language, base))
        if language == "es" and cell.tense == "subjunctive_imperfect":
            variants.extend(_es_subjunctive_variants(value))
    seen: set[str] = set()
    ordered: list[str] = []
    for variant in sorted(variants, key=lambda v: -len(v)):
        key = fold(language, variant)
        if key and key not in seen:
            seen.add(key)
            ordered.append(variant)
    return ordered


def answer_matches_cell(language: str, answer: str, cell: FormCell) -> bool:
    answer_folded = fold(language, answer)
    for variant in variants_for(language, cell):
        variant_folded = fold(language, variant)
        if answer_folded == variant_folded:
            return True
    return False


# ---------------------------------------------------------------------------
# Locating a form in a sentence.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Match:
    start: int
    end: int
    cell: FormCell
    kind: str  # always exact (spelling tolerance was removed)


_WORD_CHAR = r"[\w\u0300-\u036f\u0591-\u05c7]"  # letters plus combining marks (niqqud, accents)


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_" or unicodedata.category(ch).startswith("M")


def _word_pattern(folded_variant: str) -> re.Pattern[str]:
    tokens = [re.escape(token) for token in folded_variant.split()]
    return re.compile(f"(?<!{_WORD_CHAR})" + r"\s+".join(tokens) + f"(?!{_WORD_CHAR})")


def _find_spans(language: str, sentence: str, answer_text: str, tier: int = 1) -> list[tuple[int, int, str]]:
    """Spans (original offsets) where `answer_text` appears as whole words.

    Hebrew has two tiers (0: vowel marks must match, 1: marks ignored); other languages use tier 1.
    Plene/defective spelling (ביקשו vs בקשו) is deliberately NOT tolerated: it cannot be told apart
    from a different word (כתוב vs כתב), and a wrong blank is worse than an untagged example.
    """
    folded_sentence, index_map = fold_with_map(language, sentence, keep_marks=(tier == 0))
    folded_answer = fold_with_map(language, answer_text, keep_marks=(tier == 0))[0]
    if not folded_answer:
        return []
    spans = []
    for hit in _word_pattern(folded_answer).finditer(folded_sentence):
        start = index_map[hit.start()]
        end = index_map[hit.end() - 1] + 1
        while end < len(sentence) and unicodedata.category(sentence[end]).startswith("M"):
            end += 1  # marks dropped by folding that trail the last letter belong to the word
        spans.append((start, end, "exact"))
    return spans


def _find_matches_at_tier(language: str, sentence: str, forms: Any, tier: int) -> list[Match]:
    matches: list[Match] = []
    for cell in iter_form_cells(forms):
        if (language, cell.tense, cell.person) in _UNPRACTICED_CELLS:
            continue
        for variant in variants_for(language, cell):
            for start, end, kind in _find_spans(language, sentence, variant, tier):
                matches.append(Match(start, end, cell, kind))
    return matches


def find_matches(language: str, sentence: str, forms: Any) -> list[Match]:
    """All form matches in `sentence`; Hebrew uses the strictest tier that finds anything."""
    for tier in (0, 1) if language == "he" else (1,):
        matches = _find_matches_at_tier(language, sentence, forms, tier)
        if matches:
            return matches
    return []


def _drop_contained(matches: list[Match]) -> list[Match]:
    """Drop matches strictly inside a longer match ("aiutato" inside "ho aiutato")."""
    kept = []
    for match in matches:
        contained = any(
            other.start <= match.start
            and match.end <= other.end
            and (other.end - other.start) > (match.end - match.start)
            for other in matches
        )
        if not contained:
            kept.append(match)
    return kept


def _build_target(language: str, sentence: str, match: Match, source: str) -> dict[str, Any]:
    answer = sentence[match.start : match.end]
    alternatives = [v for v in variants_for(language, match.cell) if v != answer]
    return {
        "tense": match.cell.tense,
        "person": match.cell.person,
        "start": match.start,
        "end": match.end,
        "answer": answer,
        "alternatives": alternatives,
        "match": match.kind,
        "source": source,
        "v": TARGET_VERSION,
    }


def _prefer_by_subject(language: str, sentence: str, start: int, cells: list[FormCell]) -> list[FormCell]:
    """Keep the cells whose subject pronoun stands just before the form; all cells when none does."""
    table = _SUBJECT_WORDS.get(language)
    if not table or len(cells) < 2:
        return cells
    before = fold(language, sentence[:start]).replace("'", "' ")
    words = re.findall(r"[\w']+", before)[-_SUBJECT_WINDOW_WORDS:]
    consistent = [c for c in cells if c.person in table and any(fold(language, w) in words for w in table[c.person])]
    return consistent or cells


def tag_sentence(language: str, sentence: str, forms: Any) -> Optional[dict[str, Any]]:
    """Deterministic tag: only when exactly one form cell matches at exactly one place."""
    if not sentence or unicodedata.normalize("NFC", sentence) != sentence:
        return None
    matches = _drop_contained(find_matches(language, sentence, forms))
    if len({(m.start, m.end) for m in matches}) != 1:
        return None
    ordered_cells: list[FormCell] = []
    for match in matches:
        if match.cell.path not in {c.path for c in ordered_cells}:
            ordered_cells.append(match.cell)
    ordered_cells = _prefer_by_subject(language, sentence, matches[0].start, ordered_cells)
    if len(ordered_cells) > MAX_LABELS_PER_TARGET:
        return None
    primary = next(m for m in matches if m.cell.path == ordered_cells[0].path)
    target = _build_target(language, sentence, primary, "deterministic")
    if len(ordered_cells) > 1:
        target["also"] = [c.path for c in ordered_cells[1:]]
    return target


def explain_untagged(language: str, sentence: str, forms: Any) -> str:
    """Why `tag_sentence` returned None: no_match | too_many_forms | ambiguous_position | not_nfc | empty."""
    if not sentence:
        return "empty"
    if unicodedata.normalize("NFC", sentence) != sentence:
        return "not_nfc"
    matches = _drop_contained(find_matches(language, sentence, forms))
    if not matches:
        return "no_match"
    if len({(m.start, m.end) for m in matches}) > 1:
        return "ambiguous_position"
    if len({m.cell.path for m in matches}) > MAX_LABELS_PER_TARGET:
        return "too_many_forms"
    return "tagged"


def _split_path(path: str) -> tuple[str, Optional[str]]:
    tense, _, person = path.partition(".")
    return tense, (person or None)


def tag_from_hint(language: str, sentence: str, forms: Any, path: str, answer: str) -> Optional[dict[str, Any]]:
    """Tag from a generator/LLM-named form; kept only if it validates against the sentence."""
    if not (isinstance(path, str) and isinstance(answer, str) and answer.strip()):
        return None
    tense, person = _split_path(path.strip())
    cell = get_cell(forms, tense, person)
    if cell is None or not answer_matches_cell(language, answer.strip(), cell):
        return None
    spans = _find_spans(language, sentence, answer.strip())
    if len(spans) != 1:
        return None
    start, end, kind = spans[0]
    return _build_target(language, sentence, Match(start, end, cell, kind), "generated")


def validate_target(language: str, sentence: str, forms: Any, target: Any) -> list[str]:
    """Return a list of problems; empty means the target is safe to serve."""
    if not isinstance(target, dict):
        return ["target is not a map"]
    problems: list[str] = []
    tense, person = target.get("tense"), target.get("person")
    start, end, answer = target.get("start"), target.get("end"), target.get("answer")
    if not isinstance(tense, str) or not (person is None or isinstance(person, str)):
        return ["bad tense/person"]
    cell = get_cell(forms, tense, person)
    if cell is None:
        problems.append("form missing from forms")
    if not (isinstance(start, int) and isinstance(end, int) and isinstance(answer, str)):
        return problems + ["bad span"]
    if not (0 <= start < end <= len(sentence)) or sentence[start:end] != answer:
        problems.append("span does not match sentence")
        return problems
    if (start > 0 and _is_word_char(sentence[start - 1])) or (end < len(sentence) and _is_word_char(sentence[end])):
        problems.append("span not on word boundary")
    if cell is not None and not answer_matches_cell(language, answer, cell):
        problems.append("answer does not match form")
    also = target.get("also")
    if also is not None:
        if not isinstance(also, list) or len(also) + 1 > MAX_LABELS_PER_TARGET:
            problems.append("bad also")
        else:
            for path in also:
                other = get_cell(forms, *_split_path(path)) if isinstance(path, str) else None
                if other is None or not answer_matches_cell(language, answer, other):
                    problems.append("also form does not match answer")
                    break
    return problems


def parse_example_target(language: str, sentence: str, forms: Any, raw: Any) -> Optional[dict[str, Any]]:
    """Loader hook: the stored target if it still validates, else None."""
    if raw is None or validate_target(language, sentence, forms, raw):
        return None
    alternatives = raw.get("alternatives")
    parsed = {
        "tense": raw["tense"],
        "person": raw.get("person"),
        "start": raw["start"],
        "end": raw["end"],
        "answer": raw["answer"],
        "alternatives": [a for a in alternatives if isinstance(a, str)] if isinstance(alternatives, list) else [],
        "match": raw.get("match", "exact"),
        "source": raw.get("source", "deterministic"),
        "v": raw.get("v", TARGET_VERSION),
    }
    if raw.get("also"):
        parsed["also"] = list(raw["also"])
    return parsed


def tag_generated_payload(language: str, generated: Any) -> Any:
    """Tag `generated["examples"]` of a freshly generated verb payload (after language normalization)."""
    if isinstance(generated, dict) and isinstance(generated.get("examples"), list):
        generated = {**generated, "examples": tag_examples(language, generated.get("forms"), generated["examples"])}
    return generated


def tag_examples(language: str, forms: Any, examples: list[Any], *, retag: bool = False) -> list[Any]:
    """Return `examples` with a validated `target` on each taggable one.

    The generator may attach `form` ("tense.person") and `answer` hints to an
    example; they are consumed here (never stored). A hint wins over the
    deterministic matcher when it validates. An existing valid target is kept
    unless `retag`. Untaggable examples are returned without a target.
    """
    tagged: list[Any] = []
    for example in examples or []:
        if not isinstance(example, dict):
            tagged.append(example)
            continue
        result = {k: v for k, v in example.items() if k not in ("form", "answer")}
        sentence = native_sentence(result)
        target = None
        if not retag and result.get("target") is not None:
            target = parse_example_target(language, sentence, forms, result.get("target"))
        if target is None:
            hint_path, hint_answer = example.get("form"), example.get("answer")
            if hint_path and hint_answer:
                target = tag_from_hint(language, sentence, forms, hint_path, hint_answer)
            if target is None:
                target = tag_sentence(language, sentence, forms)
        if target is None:
            result.pop("target", None)
        else:
            result["target"] = target
        tagged.append(result)
    return tagged
