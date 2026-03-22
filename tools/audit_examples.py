from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from core.paths import DATA_DIR, DATA_SRC_DIR
from core.supported_languages import (
    supported_languages_list,
    supported_languages_with_all,
)


@dataclass(frozen=True)
class Issue:
    severity: str  # "ERROR" or "WARNING"
    language: str
    verb_id: str
    lemma: str
    example_index: int
    message: str
    text: str


BAD_PATTERNS_BY_LANGUAGE: dict[str, list[re.Pattern[str]]] = {
    "en": [
        re.compile(r"\bthe project now\b", re.IGNORECASE),
        re.compile(r"\bmy work every day\b", re.IGNORECASE),
        re.compile(r"\ba new task at work\b", re.IGNORECASE),
        re.compile(r"\bsay me\b", re.IGNORECASE),
        re.compile(r"\bdiscuss about\b", re.IGNORECASE),
        re.compile(r"\bwatch at\b", re.IGNORECASE),
        re.compile(r"\bmeet the project\b", re.IGNORECASE),
        re.compile(r"\bbecome the job\b", re.IGNORECASE),
        re.compile(r"\bbecome my work\b", re.IGNORECASE),
        re.compile(r"\bknow carefully\b", re.IGNORECASE),
        re.compile(r"\bhave carefully\b", re.IGNORECASE),
        re.compile(r"\bbe carefully\b", re.IGNORECASE),
    ],
    "ru": [
        re.compile(r"\bрадио покупал[ао]?(\s|$)", re.IGNORECASE),
        re.compile(r"\bрадио покупало\b", re.IGNORECASE),
        re.compile(r"\bрадио читало\b", re.IGNORECASE),
    ],
    "he": [],
}


ENGLISH_FORBIDDEN_OBJECTS_BY_STRATEGY: dict[str, set[str]] = {
    "meet_person_or_meet_with_group": {
        "project",
        "job",
        "task",
        "plan",
        "idea",
        "problem",
    },
    "become_state": {
        "project",
        "job",
        "task",
        "work",
        "meeting",
    },
    "say_content": {
        "me",
        "him",
        "her",
        "them",
        "us",
    },
}


def contains_russian_form_or_compound_future(
    example_text: str,
    forms: list[str],
    lemma: str,
) -> bool:
    normalized_text = normalize_text(example_text)

    for form in forms:
        normalized_form = normalize_text(form)
        if not normalized_form:
            continue
        pattern = r"(?<!\w)" + re.escape(normalized_form) + r"(?!\w)"
        if re.search(pattern, normalized_text, flags=re.IGNORECASE):
            return True

    normalized_lemma = normalize_text(lemma)
    future_auxiliaries = ["буду", "будешь", "будет", "будем", "будете", "будут"]
    for auxiliary in future_auxiliaries:
        pattern = (
            r"(?<!\w)"
            + re.escape(auxiliary)
            + r"\s+"
            + re.escape(normalized_lemma)
            + r"(?!\w)"
        )
        if re.search(pattern, normalized_text, flags=re.IGNORECASE):
            return True

    return False


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"invalid JSON in {path}: {error}")
    if not isinstance(payload, dict):
        fail(f"{path}: expected top-level object")
    return payload


def flatten_forms(forms_object: Any) -> list[str]:
    values: list[str] = []

    if isinstance(forms_object, dict):
        for value in forms_object.values():
            values.extend(flatten_forms(value))
    elif isinstance(forms_object, list):
        for item in forms_object:
            values.extend(flatten_forms(item))
    elif isinstance(forms_object, str):
        stripped_value = forms_object.strip()
        if stripped_value:
            values.append(stripped_value)

    return values


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def build_example_skeleton(text: str) -> str:
    skeleton = normalize_text(text)
    skeleton = re.sub(r"[a-zA-Zа-яА-Яא-ת]+", "w", skeleton)
    return skeleton


def contains_any_form(
    example_text: str,
    forms: list[str],
    language: str,
    lemma: str = "",
) -> bool:
    normalized_example = normalize_text(example_text)

    if language == "ru":
        return contains_russian_form_or_compound_future(
            example_text=example_text,
            forms=forms,
            lemma=lemma,
        )

    for form in forms:
        normalized_form = normalize_text(form)
        if not normalized_form:
            continue

        if language == "en":
            pattern = r"(?<!\w)" + re.escape(normalized_form) + r"(?!\w)"
            if re.search(pattern, normalized_example, flags=re.IGNORECASE):
                return True
        else:
            if normalized_form in normalized_example:
                return True

    return False


def load_source_strategy_map(language: str) -> dict[str, str]:
    if language != "en":
        return {}

    source_path = DATA_SRC_DIR / language / "catalog.json"
    payload = load_json(source_path)
    verbs = payload.get("verbs", [])
    if not isinstance(verbs, list):
        fail(f"{source_path}: top-level 'verbs' must be a list")

    strategy_by_id: dict[str, str] = {}
    for entry in verbs:
        if not isinstance(entry, dict):
            continue
        verb_id = entry.get("id")
        strategy = entry.get("example_strategy")
        if isinstance(verb_id, str) and isinstance(strategy, str) and strategy.strip():
            strategy_by_id[verb_id] = strategy

    return strategy_by_id


def audit_bad_patterns(
    language: str,
    verb_id: str,
    lemma: str,
    example_index: int,
    text: str,
) -> list[Issue]:
    issues: list[Issue] = []
    for pattern in BAD_PATTERNS_BY_LANGUAGE.get(language, []):
        if pattern.search(text):
            issues.append(
                Issue(
                    severity="ERROR",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=example_index,
                    message=f"matched banned pattern: {pattern.pattern}",
                    text=text,
                )
            )
    return issues


def audit_english_strategy(
    verb_id: str,
    lemma: str,
    example_index: int,
    text: str,
    strategy: str | None,
) -> list[Issue]:
    issues: list[Issue] = []
    if not strategy:
        return issues

    text_lower = normalize_text(text)

    if strategy == "meet_person_or_meet_with_group":
        for forbidden in ENGLISH_FORBIDDEN_OBJECTS_BY_STRATEGY[strategy]:
            if re.search(
                rf"\bmeet(?:s|ing|ing with|)\s+the\s+{re.escape(forbidden)}\b",
                text_lower,
            ):
                issues.append(
                    Issue(
                        severity="ERROR",
                        language="en",
                        verb_id=verb_id,
                        lemma=lemma,
                        example_index=example_index,
                        message=f"'meet' used with forbidden direct object '{forbidden}'",
                        text=text,
                    )
                )
            if re.search(rf"\bmet\s+the\s+{re.escape(forbidden)}\b", text_lower):
                issues.append(
                    Issue(
                        severity="ERROR",
                        language="en",
                        verb_id=verb_id,
                        lemma=lemma,
                        example_index=example_index,
                        message=f"'meet' used with forbidden direct object '{forbidden}'",
                        text=text,
                    )
                )

    elif strategy == "become_state":
        for forbidden in ENGLISH_FORBIDDEN_OBJECTS_BY_STRATEGY[strategy]:
            if re.search(
                rf"\bbecome(?:s|ing|)\s+(?:the\s+|my\s+|a\s+)?{re.escape(forbidden)}\b",
                text_lower,
            ) or re.search(
                rf"\bbecame\s+(?:the\s+|my\s+|a\s+)?{re.escape(forbidden)}\b",
                text_lower,
            ):
                issues.append(
                    Issue(
                        severity="ERROR",
                        language="en",
                        verb_id=verb_id,
                        lemma=lemma,
                        example_index=example_index,
                        message=f"'become' expects a state/complement, not '{forbidden}'",
                        text=text,
                    )
                )

    elif strategy == "say_content":
        for forbidden in ENGLISH_FORBIDDEN_OBJECTS_BY_STRATEGY[strategy]:
            if re.search(
                rf"\bsay(?:s|ing|)\s+{re.escape(forbidden)}\b", text_lower
            ) or re.search(
                rf"\bsaid\s+{re.escape(forbidden)}\b",
                text_lower,
            ):
                issues.append(
                    Issue(
                        severity="ERROR",
                        language="en",
                        verb_id=verb_id,
                        lemma=lemma,
                        example_index=example_index,
                        message=f"'say' used with indirect-object pattern '{forbidden}'",
                        text=text,
                    )
                )

    return issues


def audit_near_duplicate_templates(
    language: str,
    verb_id: str,
    lemma: str,
    examples_object: list[dict[str, Any]],
) -> list[Issue]:
    issues: list[Issue] = []
    seen_skeletons: set[str] = set()

    for index, example in enumerate(examples_object, start=1):
        text = example.get("dst", "")
        if not isinstance(text, str) or not text.strip():
            continue

        skeleton = build_example_skeleton(text)

        if skeleton in seen_skeletons:
            issues.append(
                Issue(
                    severity="WARNING",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=index,
                    message="near-duplicate example template within verb",
                    text=text,
                )
            )
        seen_skeletons.add(skeleton)

    return issues


def audit_examples_for_verb(
    language: str,
    verb: dict[str, Any],
    english_strategy_map: dict[str, str],
) -> list[Issue]:
    issues: list[Issue] = []

    verb_id = str(verb.get("id", ""))
    lemma_object = verb.get("lemma", "")
    lemma = lemma_object if isinstance(lemma_object, str) else str(lemma_object)
    forms = flatten_forms(verb.get("forms", {}))
    examples_object = verb.get("examples", [])

    if not isinstance(examples_object, list):
        issues.append(
            Issue(
                severity="ERROR",
                language=language,
                verb_id=verb_id,
                lemma=lemma,
                example_index=0,
                message="examples is not a list",
                text="",
            )
        )
        return issues

    seen_texts: set[str] = set()
    strategy = english_strategy_map.get(verb_id)

    for index, example in enumerate(examples_object, start=1):
        if not isinstance(example, dict):
            issues.append(
                Issue(
                    severity="ERROR",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=index,
                    message="example is not an object",
                    text=str(example),
                )
            )
            continue

        text = example.get("dst", "")
        if not isinstance(text, str) or not text.strip():
            issues.append(
                Issue(
                    severity="ERROR",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=index,
                    message="example text is empty",
                    text="",
                )
            )
            continue

        normalized_text = normalize_text(text)
        # skeleton = build_example_skeleton(text) # reserved for future use

        if normalized_text in seen_texts:
            issues.append(
                Issue(
                    severity="ERROR",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=index,
                    message="duplicate example text within verb",
                    text=text,
                )
            )
        seen_texts.add(normalized_text)

        if not contains_any_form(text, forms, language, lemma):
            issues.append(
                Issue(
                    severity="ERROR",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=index,
                    message="example does not contain any listed form",
                    text=text,
                )
            )

        if len(text.strip()) < 4:
            issues.append(
                Issue(
                    severity="WARNING",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=index,
                    message="example is suspiciously short",
                    text=text,
                )
            )

        if not re.search(r"[.!?]$", text.strip()):
            issues.append(
                Issue(
                    severity="WARNING",
                    language=language,
                    verb_id=verb_id,
                    lemma=lemma,
                    example_index=index,
                    message="example does not end with sentence punctuation",
                    text=text,
                )
            )

        issues.extend(audit_bad_patterns(language, verb_id, lemma, index, text))

        if language == "en":
            issues.extend(audit_english_strategy(verb_id, lemma, index, text, strategy))

    return issues


def audit_language(language: str) -> list[Issue]:
    runtime_path = DATA_DIR / language / "lexicon.json"
    payload = load_json(runtime_path)

    verbs = payload.get("verbs", [])
    if not isinstance(verbs, list):
        fail(f"{runtime_path}: top-level 'verbs' must be a list")

    english_strategy_map = load_source_strategy_map(language)

    issues: list[Issue] = []
    for verb in verbs:
        if not isinstance(verb, dict):
            continue
        issues.extend(audit_examples_for_verb(language, verb, english_strategy_map))
    return issues


def print_report(issues: list[Issue]) -> None:
    if not issues:
        print("OK: no issues found")
        return

    for issue in issues:
        print(
            f"{issue.severity} {issue.language} {issue.verb_id} "
            f"(example {issue.example_index}): {issue.message}\n"
            f"  {issue.text}"
        )

    error_count = sum(1 for issue in issues if issue.severity == "ERROR")
    warning_count = sum(1 for issue in issues if issue.severity == "WARNING")
    print("")
    print(f"Total issues: {len(issues)}")
    print(f"Errors: {error_count}")
    print(f"Warnings: {warning_count}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit example quality in runtime lexicons"
    )
    parser.add_argument(
        "--language",
        required=True,
        choices=supported_languages_with_all(),
        help="Language to audit",
    )
    parser.add_argument(
        "--fail-on-warning",
        action="store_true",
        help="Exit non-zero on warnings too",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    languages = (
        supported_languages_list() if args.language == "all" else [args.language]
    )

    all_issues: list[Issue] = []
    for language in languages:
        all_issues.extend(audit_language(language))

    print_report(all_issues)

    error_count = sum(1 for issue in all_issues if issue.severity == "ERROR")
    warning_count = sum(1 for issue in all_issues if issue.severity == "WARNING")

    if error_count > 0:
        sys.exit(1)
    if args.fail_on_warning and warning_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
