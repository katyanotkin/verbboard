"""
Read-only audit of live verb examples (issue #99, replaces the legacy lexicon-JSON audit).

Reads verb documents from Firestore (or a JSON export with --from-json) and runs a registry of
small check functions over each verb. Nothing is ever written. Findings have a severity:

    error    wrong or unsafe content (stale target, duplicate sentence, missing translation, ...)
    warning  weak content worth a look (missing tense coverage, untagged, skewed persons, ...)
    info     numbers only (never fails a run)

Exit codes: 0 no errors (and no warnings with --strict), 1 findings, 2 could not run.

Usage (project root, needs GCP auth for Firestore):

    python -m tools.audit_examples --language ru
    python -m tools.audit_examples --language es --verb-id es_hablar --report /tmp/es.csv
    python -m tools.audit_examples --from-json /tmp/verbs.json --strict

`audit_payload(language, data)` is the pure entry point (one verb document in, findings out), so a
later post-generation gate can call it without Firestore.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from core.example_targets import explain_untagged, iter_form_cells, native_sentence, validate_target
from core.languages.config import ALL_STUDY_LANGUAGES, UI_LANGUAGES

ERROR = "error"
WARNING = "warning"
INFO = "info"
_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

EXIT_CLEAN = 0
EXIT_FINDINGS = 1
EXIT_COULD_NOT_RUN = 2


@dataclass(frozen=True)
class Finding:
    severity: str
    check: str
    language: str
    verb_id: str
    example_index: int | None  # 0-based, None for a verb-level finding
    message: str
    text: str = ""


@dataclass(frozen=True)
class VerbContext:
    language: str
    verb_id: str
    lemma: str
    forms: Any
    examples: list[dict[str, Any]]
    data: dict[str, Any]

    def finding(
        self, severity: str, check_name: str, message: str, *, index: int | None = None, text: str = ""
    ) -> Finding:
        return Finding(severity, check_name, self.language, self.verb_id, index, message, text)

    def sentences(self) -> list[tuple[int, str]]:
        """(index, native sentence) for every example that has one."""
        pairs = [(i, native_sentence(example)) for i, example in enumerate(self.examples)]
        return [(i, text) for i, text in pairs if text.strip()]


CheckFunction = Callable[[VerbContext], Iterable[Finding]]
CHECKS: dict[str, CheckFunction] = {}


def check(name: str) -> Callable[[CheckFunction], CheckFunction]:
    def register(function: CheckFunction) -> CheckFunction:
        CHECKS[name] = function
        return function

    return register


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_int(value: Any) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _target_path(example: dict[str, Any]) -> str | None:
    target = example.get("target")
    if not isinstance(target, dict) or not isinstance(target.get("tense"), str):
        return None
    person = target.get("person")
    return target["tense"] if not person else f"{target['tense']}.{person}"


# ---------------------------------------------------------------------------
# Coverage and tagging
# ---------------------------------------------------------------------------


@check("coverage_per_tense")
def _coverage_per_tense(ctx: VerbContext) -> Iterable[Finding]:
    """Every conjugated tense stored on the verb (a tense with persons) should have an example."""
    conjugated = {cell.tense for cell in iter_form_cells(ctx.forms) if cell.person is not None}
    covered: set[str] = set()
    for example in ctx.examples:
        path = _target_path(example)
        if path:
            covered.add(path.split(".")[0])
        target = example.get("target")
        for extra in (target.get("also") or []) if isinstance(target, dict) else []:
            if isinstance(extra, str):
                covered.add(extra.split(".")[0])
    for tense in sorted(conjugated - covered):
        yield ctx.finding(WARNING, "coverage_per_tense", f"no example shows the '{tense}' tense")


@check("unused_forms")
def _unused_forms(ctx: VerbContext) -> Iterable[Finding]:
    cells = {cell.path for cell in iter_form_cells(ctx.forms) if cell.person is not None}
    used = {path for example in ctx.examples if (path := _target_path(example))}
    yield ctx.finding(
        INFO, "unused_forms", f"{len(used & cells)} of {len(cells)} conjugation cells are an example target"
    )


@check("untagged_example")
def _untagged_example(ctx: VerbContext) -> Iterable[Finding]:
    for index, sentence in ctx.sentences():
        if ctx.examples[index].get("target") is None:
            reason = explain_untagged(ctx.language, sentence, ctx.forms)
            yield ctx.finding(WARNING, "untagged_example", f"no fill-in target ({reason})", index=index, text=sentence)


@check("stale_target")
def _stale_target(ctx: VerbContext) -> Iterable[Finding]:
    for index, sentence in ctx.sentences():
        target = ctx.examples[index].get("target")
        if target is None:
            continue
        problems = validate_target(ctx.language, sentence, ctx.forms, target)
        if problems:
            yield ctx.finding(ERROR, "stale_target", "; ".join(problems), index=index, text=sentence)


@check("duplicate_cell")
def _duplicate_cell(ctx: VerbContext) -> Iterable[Finding]:
    seen: dict[str, int] = {}
    for index, example in enumerate(ctx.examples):
        path = _target_path(example)
        if path is None:
            continue
        if path in seen:
            yield ctx.finding(
                WARNING,
                "duplicate_cell",
                f"'{path}' is already the target of example {seen[path]}",
                index=index,
                text=native_sentence(example),
            )
        else:
            seen[path] = index


@check("person_spread")
def _person_spread(ctx: VerbContext) -> Iterable[Finding]:
    persons = [
        example["target"]["person"]
        for example in ctx.examples
        if isinstance(example.get("target"), dict)
        and isinstance(example["target"].get("person"), str)
        and example["target"]["person"]
    ]
    if len(persons) < 5:
        return
    person, count = Counter(persons).most_common(1)[0]
    if count / len(persons) > 0.6:
        yield ctx.finding(WARNING, "person_spread", f"{count} of {len(persons)} tagged examples use person '{person}'")


# ---------------------------------------------------------------------------
# Sentence quality
# ---------------------------------------------------------------------------

_MIN_WORDS = 3
_MAX_WORDS = 22


@check("duplicate_text")
def _duplicate_text(ctx: VerbContext) -> Iterable[Finding]:
    seen: dict[str, int] = {}
    for index, sentence in ctx.sentences():
        key = _normalize(sentence)
        if key in seen:
            yield ctx.finding(
                ERROR, "duplicate_text", f"same sentence as example {seen[key]}", index=index, text=sentence
            )
        else:
            seen[key] = index


@check("sentence_length")
def _sentence_length(ctx: VerbContext) -> Iterable[Finding]:
    for index, sentence in ctx.sentences():
        words = len(sentence.split())
        if words < _MIN_WORDS:
            yield ctx.finding(WARNING, "sentence_length", f"very short ({words} words)", index=index, text=sentence)
        elif words > _MAX_WORDS:
            yield ctx.finding(WARNING, "sentence_length", f"very long ({words} words)", index=index, text=sentence)


@check("stock_opener")
def _stock_opener(ctx: VerbContext) -> Iterable[Finding]:
    openers = [_normalize(sentence).split(" ")[0].strip("¿¡\"'«»(") for _, sentence in ctx.sentences()]
    if len(openers) < 4:
        return
    opener, count = Counter(openers).most_common(1)[0]
    if count >= 3 and count / len(openers) > 0.5:
        yield ctx.finding(WARNING, "stock_opener", f"{count} of {len(openers)} examples start with '{opener}'")


# Phrases a linguist flagged as unnatural or wrong in earlier audits (kept from the legacy script).
BANNED_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "en": [
        re.compile(pattern, re.IGNORECASE)
        for pattern in (
            r"\bthe project now\b",
            r"\bmy work every day\b",
            r"\ba new task at work\b",
            r"\bsay me\b",
            r"\bdiscuss about\b",
            r"\bwatch at\b",
            r"\bmeet the project\b",
            r"\bbecome the job\b",
            r"\bbecome my work\b",
            r"\bknow carefully\b",
            r"\bhave carefully\b",
            r"\bbe carefully\b",
        )
    ],
    "ru": [
        re.compile(pattern, re.IGNORECASE)
        for pattern in (r"\bрадио покупал[ао]?(\s|$)", r"\bрадио покупало\b", r"\bрадио читало\b")
    ],
}


@check("banned_phrase")
def _banned_phrase(ctx: VerbContext) -> Iterable[Finding]:
    for index, sentence in ctx.sentences():
        for pattern in BANNED_PATTERNS.get(ctx.language, []):
            if pattern.search(sentence):
                yield ctx.finding(ERROR, "banned_phrase", f"matched {pattern.pattern}", index=index, text=sentence)


# ---------------------------------------------------------------------------
# Language-specific checks
# ---------------------------------------------------------------------------

_RU_COMPOUND_FUTURE = re.compile(r"\bбуд(?:у|ешь|ет|ем|ете|ут)\s+[а-яё]+(?:ть|ться|ти|чь)\b", re.IGNORECASE)
_RU_NEUTER_SUBJECTS = {"оно", "это", "всё", "что", "лето", "утро", "солнце", "море"}
_RU_NEUTER_ENDINGS = ("о", "е", "ё", "ие", "ье")


@check("ru_aspect_slot")
def _ru_aspect_slot(ctx: VerbContext) -> Iterable[Finding]:
    if ctx.language != "ru":
        return
    aspect = str(_as_dict(ctx.data.get("morph")).get("aspect", "")).lower()
    for index, sentence in ctx.sentences():
        target = ctx.examples[index].get("target")
        if aspect == "perfective" and isinstance(target, dict) and target.get("tense") == "present":
            yield ctx.finding(ERROR, "ru_aspect_slot", "perfective verb tagged as present", index=index, text=sentence)
        if _RU_COMPOUND_FUTURE.search(sentence):
            yield ctx.finding(
                WARNING, "ru_aspect_slot", "compound future (буду + infinitive)", index=index, text=sentence
            )


@check("ru_forced_neuter")
def _ru_forced_neuter(ctx: VerbContext) -> Iterable[Finding]:
    """Heuristic: a past-neuter example whose nearby words contain no neuter subject."""
    if ctx.language != "ru":
        return
    for index, sentence in ctx.sentences():
        target = ctx.examples[index].get("target")
        if not (isinstance(target, dict) and target.get("tense") == "past" and target.get("person") == "n"):
            continue
        start, end = _as_int(target.get("start")), _as_int(target.get("end"))
        nearby = _normalize(sentence[:start]).split(" ")[-4:] + _normalize(sentence[end:]).split(" ")[:3]
        words = [word.strip(",.;:!?") for word in nearby if word]
        if not any(word in _RU_NEUTER_SUBJECTS or word.endswith(_RU_NEUTER_ENDINGS) for word in words):
            yield ctx.finding(
                WARNING, "ru_forced_neuter", "past neuter with no neuter subject nearby", index=index, text=sentence
            )


_EN_STATIVE_GERUNDS = {
    "needing",
    "wanting",
    "knowing",
    "liking",
    "loving",
    "hating",
    "believing",
    "understanding",
    "seeming",
    "belonging",
    "owning",
    "preferring",
    "meaning",
}
_EN_BE_PROGRESSIVE = re.compile(r"\b(?:am|is|are|was|were|been|be)\s+(\w+ing)\b", re.IGNORECASE)
_EN_DOUBLED_FINAL = {"begin", "forget", "regret", "prefer", "refer", "admit", "commit", "permit", "occur", "submit"}


def _en_expected_gerund(lemma: str) -> str | None:
    if re.fullmatch(r"[^aeiou]*[aeiou][^aeiouwxy]", lemma) or lemma in _EN_DOUBLED_FINAL:
        return lemma + lemma[-1] + "ing"
    if len(lemma) > 2 and re.search(r"[^aeiouye]e$", lemma):
        return lemma[:-1] + "ing"
    return None


@check("en_gerund")
def _en_gerund(ctx: VerbContext) -> Iterable[Finding]:
    if ctx.language != "en":
        return
    gerund = ctx.forms.get("gerund") if isinstance(ctx.forms, dict) else None
    if not isinstance(gerund, str) or not gerund.strip():
        return
    gerund = gerund.strip().lower()
    expected = _en_expected_gerund(ctx.lemma.strip().lower())
    if expected and gerund != expected:
        yield ctx.finding(ERROR, "en_gerund", f"gerund '{gerund}' should probably be '{expected}'")
    if not any(re.search(rf"\b{re.escape(gerund)}\b", sentence.lower()) for _, sentence in ctx.sentences()):
        yield ctx.finding(WARNING, "en_gerund", f"no example uses the gerund '{gerund}'")


@check("en_stative_progressive")
def _en_stative_progressive(ctx: VerbContext) -> Iterable[Finding]:
    if ctx.language != "en":
        return
    for index, sentence in ctx.sentences():
        match = _EN_BE_PROGRESSIVE.search(sentence)
        if match and match.group(1).lower() in _EN_STATIVE_GERUNDS:
            yield ctx.finding(
                WARNING, "en_stative_progressive", f"stative progressive '{match.group(0)}'", index=index, text=sentence
            )


_HEBREW_LETTER = re.compile("[\u05d0-\u05ea]")
_HEBREW_NIQQUD = re.compile("[\u05b0-\u05bd\u05bf\u05c1\u05c2\u05c4\u05c5\u05c7]")


@check("he_niqqud")
def _he_niqqud(ctx: VerbContext) -> Iterable[Finding]:
    if ctx.language != "he":
        return
    for index, sentence in ctx.sentences():
        if _HEBREW_LETTER.search(sentence) and not _HEBREW_NIQQUD.search(sentence):
            yield ctx.finding(WARNING, "he_niqqud", "sentence has no niqqud", index=index, text=sentence)


# ---------------------------------------------------------------------------
# Translations
# ---------------------------------------------------------------------------

_RATIO_MIN_CHARS = 12
_RATIO_LOW = 0.25
_RATIO_HIGH = 4.0


def _translation_languages(language: str) -> list[str]:
    return [ui for ui in UI_LANGUAGES if ui != language]


@check("translation_missing")
def _translation_missing(ctx: VerbContext) -> Iterable[Finding]:
    for index, sentence in ctx.sentences():
        translations = _as_dict(ctx.examples[index].get("translations"))
        missing = [ui for ui in _translation_languages(ctx.language) if not str(translations.get(ui, "")).strip()]
        if missing:
            yield ctx.finding(
                ERROR, "translation_missing", f"missing: {', '.join(missing)}", index=index, text=sentence
            )
    lemma_translations = _as_dict(ctx.data.get("lemma_translations"))
    missing_lemma = [
        ui for ui in _translation_languages(ctx.language) if not str(lemma_translations.get(ui, "")).strip()
    ]
    if missing_lemma:
        yield ctx.finding(WARNING, "translation_missing", f"lemma missing: {', '.join(missing_lemma)}")


@check("translation_quality")
def _translation_quality(ctx: VerbContext) -> Iterable[Finding]:
    for index, sentence in ctx.sentences():
        translations = _as_dict(ctx.examples[index].get("translations"))
        for ui in _translation_languages(ctx.language):
            translated = str(translations.get(ui, "")).strip()
            if not translated:
                continue
            if _normalize(translated) == _normalize(sentence):
                yield ctx.finding(
                    WARNING, "translation_quality", f"{ui} translation equals the source", index=index, text=sentence
                )
            elif len(sentence) >= _RATIO_MIN_CHARS:
                ratio = len(translated) / len(sentence)
                if ratio > _RATIO_HIGH or ratio < _RATIO_LOW:
                    yield ctx.finding(
                        WARNING,
                        "translation_quality",
                        f"{ui} translation length ratio {ratio:.2f}",
                        index=index,
                        text=sentence,
                    )


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def audit_payload(language: str, data: dict[str, Any], *, only: Iterable[str] | None = None) -> list[Finding]:
    """Audit one verb document. Pure: no I/O. `only` limits the run to named checks."""
    raw_examples = data.get("examples")
    examples = (
        [example for example in raw_examples if isinstance(example, dict)] if isinstance(raw_examples, list) else []
    )
    ctx = VerbContext(
        language=language,
        verb_id=str(data.get("verb_id", "")),
        lemma=str(data.get("lemma", "")),
        forms=data.get("forms"),
        examples=examples,
        data=data,
    )
    selected = set(only) if only is not None else None
    findings: list[Finding] = []
    for name, function in CHECKS.items():
        if selected is None or name in selected:
            try:
                findings.extend(function(ctx))
            except Exception as error:  # noqa: BLE001 - one bad document must not abort the whole audit
                findings.append(ctx.finding(ERROR, "check_crashed", f"{name} raised {type(error).__name__}: {error}"))
    return findings


def load_from_firestore(language: str, verb_id: str) -> list[dict[str, Any]]:
    from dotenv import load_dotenv

    load_dotenv(override=True)
    from core.storage.firestore_db import get_db

    query = get_db().collection("verbs")
    if language:
        query = query.where("language", "==", language)
    verbs = [snapshot.to_dict() or {} for snapshot in query.stream()]
    return [verb for verb in verbs if not verb_id or verb.get("verb_id") == verb_id]


def load_from_json(path: Path, language: str, verb_id: str) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("verbs"), list):
        payload = payload["verbs"]
    if isinstance(payload, dict):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError(f"{path}: expected a list of verb documents or {{'verbs': [...]}}")
    verbs = [verb for verb in payload if isinstance(verb, dict)]
    return [
        verb
        for verb in verbs
        if (not language or verb.get("language") in (None, "", language))
        and (not verb_id or verb.get("verb_id") == verb_id)
    ]


def sort_findings(findings: list[Finding]) -> list[Finding]:
    return sorted(
        findings, key=lambda f: (_SEVERITY_ORDER[f.severity], f.language, f.verb_id, f.example_index or -1, f.check)
    )


def write_report(findings: list[Finding], path: Path) -> None:
    rows = [asdict(finding) for finding in sort_findings(findings)]
    if path.suffix.lower() == ".json":
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(Finding.__dataclass_fields__))
        writer.writeheader()
        writer.writerows(rows)


def exit_code_for(findings: list[Finding], *, strict: bool) -> int:
    if any(f.severity == ERROR for f in findings):
        return EXIT_FINDINGS
    if strict and any(f.severity == WARNING for f in findings):
        return EXIT_FINDINGS
    return EXIT_CLEAN


def print_summary(findings: list[Finding], verbs_seen: int, max_lines: int) -> None:
    by_severity = Counter(f.severity for f in findings)
    print(
        f"verbs audited: {verbs_seen}  errors: {by_severity[ERROR]}  "
        f"warnings: {by_severity[WARNING]}  info: {by_severity[INFO]}"
    )
    by_check = Counter((f.check, f.severity) for f in findings if f.severity != INFO)
    for (name, severity), count in sorted(by_check.items(), key=lambda item: (_SEVERITY_ORDER[item[0][1]], -item[1])):
        print(f"  {severity:<8}{name:<26}{count}")
    shown = [f for f in sort_findings(findings) if f.severity != INFO][:max_lines]
    for finding in shown:
        where = f"{finding.verb_id}" + ("" if finding.example_index is None else f"#{finding.example_index}")
        print(
            f"[{finding.severity}] {finding.check} {where}: {finding.message}"
            + (f"  | {finding.text}" if finding.text else "")
        )
    hidden = sum(1 for f in findings if f.severity != INFO) - len(shown)
    if hidden > 0:
        print(f"... {hidden} more (use --report to get all)")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--language", default="", help=f"one of {', '.join(ALL_STUDY_LANGUAGES)}; default all")
    parser.add_argument("--verb-id", default="", help="audit a single verb")
    parser.add_argument("--from-json", default="", help="read verb documents from a JSON file instead of Firestore")
    parser.add_argument("--report", default="", help="write all findings here (.csv or .json)")
    parser.add_argument(
        "--check", action="append", default=[], help=f"run only this check (repeatable): {', '.join(CHECKS)}"
    )
    parser.add_argument("--strict", action="store_true", help="warnings also make the exit code 1")
    parser.add_argument("--max-lines", type=int, default=60, help="findings printed to the terminal")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    unknown = [name for name in args.check if name not in CHECKS]
    if unknown:
        print(f"unknown check(s): {', '.join(unknown)}", file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    if args.language and args.language not in ALL_STUDY_LANGUAGES:
        print(f"unknown language: {args.language}", file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    try:
        verbs = (
            load_from_json(Path(args.from_json), args.language, args.verb_id)
            if args.from_json
            else load_from_firestore(args.language, args.verb_id)
        )
    except Exception as error:  # noqa: BLE001 - any load failure means "could not run"
        print(f"could not load verbs: {error}", file=sys.stderr)
        return EXIT_COULD_NOT_RUN
    if not verbs:
        print("no verbs matched", file=sys.stderr)
        return EXIT_COULD_NOT_RUN

    findings: list[Finding] = []
    for verb in verbs:
        language = str(verb.get("language") or args.language)
        if not language:
            findings.append(
                Finding(
                    ERROR, "missing_language", "", str(verb.get("verb_id", "")), None, "verb document has no language"
                )
            )
            continue
        findings.extend(audit_payload(language, verb, only=args.check or None))
    print_summary(findings, len(verbs), args.max_lines)
    if args.report:
        write_report(findings, Path(args.report))
        print(f"report: {args.report}")
    return exit_code_for(findings, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
