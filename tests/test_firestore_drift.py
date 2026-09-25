"""tools/check_firestore_drift.py: comparison logic (issue #39/#51). No network."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.check_firestore_drift import committed_index_keys, find_drift, rules_differ

RULES = "rules_version = '2';\nservice cloud.firestore {\n  match /databases/{database}/documents {\n    match /{document=**} {\n      allow read, write: if false;\n    }\n  }\n}\n"


def _committed(*indexes: dict) -> dict:
    return {"indexes": list(indexes), "fieldOverrides": []}


def _index(collection: str, *fields: tuple[str, str]) -> dict:
    return {
        "collectionGroup": collection,
        "queryScope": "COLLECTION",
        "fields": [{"fieldPath": path, "order": order} for path, order in fields],
    }


def _live(collection: str, *fields: tuple[str, str]) -> dict:
    return {
        "name": f"projects/p/databases/(default)/collectionGroups/{collection}/indexes/abc",
        "queryScope": "COLLECTION",
        "fields": [{"fieldPath": path, "order": order} for path, order in fields]
        + [{"fieldPath": "__name__", "order": "ASCENDING"}],
    }


def _repo(tmp_path: Path, committed: dict, rules: str = RULES) -> Path:
    (tmp_path / "firestore.indexes.json").write_text(json.dumps(committed))
    (tmp_path / "firestore.rules").write_text(rules)
    return tmp_path


def test_matching_state_reports_no_drift(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _committed(_index("verbs", ("language", "ASCENDING"), ("created_at", "DESCENDING"))))
    live = [_live("verbs", ("language", "ASCENDING"), ("created_at", "DESCENDING"))]
    assert find_drift(live_indexes=live, live_rules=RULES, repo_root=repo) == []


def test_the_implicit_name_field_and_rule_whitespace_are_ignored(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _committed(_index("verbs", ("language", "ASCENDING"))))
    assert (
        find_drift(
            live_indexes=[_live("verbs", ("language", "ASCENDING"))], live_rules=RULES + "   \n\n", repo_root=repo
        )
        == []
    )


def test_an_index_only_live_and_an_index_only_committed_are_both_reported(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _committed(_index("verbs", ("language", "ASCENDING"))))
    findings = find_drift(live_indexes=[_live("users", ("email", "ASCENDING"))], live_rules=RULES, repo_root=repo)
    assert len(findings) == 2
    assert any("live but not in firestore.indexes.json" in f and "users" in f for f in findings)
    assert any("in firestore.indexes.json but not live" in f and "verbs" in f for f in findings)


def test_field_order_and_direction_matter(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _committed(_index("verbs", ("a", "ASCENDING"), ("b", "DESCENDING"))))
    assert find_drift(
        live_indexes=[_live("verbs", ("b", "DESCENDING"), ("a", "ASCENDING"))], live_rules=RULES, repo_root=repo
    )
    assert find_drift(
        live_indexes=[_live("verbs", ("a", "ASCENDING"), ("b", "ASCENDING"))], live_rules=RULES, repo_root=repo
    )


def test_a_changed_ruleset_is_reported(tmp_path: Path) -> None:
    repo = _repo(tmp_path, _committed())
    findings = find_drift(live_indexes=[], live_rules=RULES.replace("if false", "if true"), repo_root=repo)
    assert findings == ["live Firestore ruleset differs from firestore.rules"]
    assert rules_differ("a", "b") and not rules_differ("a \n", "a")


def test_the_real_committed_files_parse_into_index_keys() -> None:
    committed = json.loads((Path(__file__).resolve().parent.parent / "firestore.indexes.json").read_text())
    assert committed_index_keys(committed)  # non-empty: the repo really tracks its indexes


def test_array_config_indexes_are_compared_by_their_array_mode(tmp_path: Path) -> None:
    committed = _committed(
        {
            "collectionGroup": "verbs",
            "queryScope": "COLLECTION",
            "fields": [
                {"fieldPath": "language", "order": "ASCENDING"},
                {"fieldPath": "search_extract", "arrayConfig": "CONTAINS"},
            ],
        }
    )
    live: dict[str, Any] = {
        "name": "projects/p/databases/(default)/collectionGroups/verbs/indexes/x",
        "queryScope": "COLLECTION",
        "fields": [
            {"fieldPath": "language", "order": "ASCENDING"},
            {"fieldPath": "search_extract", "arrayConfig": "CONTAINS"},
            {"fieldPath": "__name__", "order": "ASCENDING"},
        ],
    }
    repo = _repo(tmp_path, committed)
    assert find_drift(live_indexes=[live], live_rules=RULES, repo_root=repo) == []
    live["fields"][1] = {"fieldPath": "search_extract", "order": "ASCENDING"}
    assert find_drift(live_indexes=[live], live_rules=RULES, repo_root=repo)
