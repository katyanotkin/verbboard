"""Detect drift between the live Firestore rules/indexes and the committed files.

Issue #39/#51: firestore.rules and firestore.indexes.json are source-controlled
copies of the live console state, but nothing deploys them, so the two can drift
apart silently. This is the lightweight, read-only detection step: it compares
the live ruleset and the live composite indexes against the committed files and
exits non-zero on any difference. It changes nothing.

Usage (run from the project root; needs `gcloud` authenticated with read access):

    python -m tools.check_firestore_drift
    python -m tools.check_firestore_drift --project knotmem26

Exit codes: 0 no drift, 1 drift found, 2 could not check (auth/network/tooling).

Scope: composite indexes and the Firestore ruleset only. Single-field index
overrides are not compared. Stage and prod share this one Firestore project, so
one check covers both.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from core.settings import load_settings

REPO_ROOT = Path(__file__).resolve().parent.parent
_NAME_PATTERN = re.compile(r"[a-z0-9-]+")


# ── pure comparison ─────────────────────────────────────────────────────────


def _index_key(collection: str, scope: str | None, fields: list[tuple[str, str]]) -> tuple:
    return (collection, scope, tuple(fields))


def committed_index_keys(committed: dict[str, Any]) -> set[tuple]:
    """Keys for the indexes in firestore.indexes.json."""
    return {
        _index_key(
            index["collectionGroup"],
            index.get("queryScope"),
            [(f["fieldPath"], f.get("order") or f.get("arrayConfig")) for f in index["fields"]],
        )
        for index in committed.get("indexes", [])
    }


def live_index_keys(live: list[dict[str, Any]]) -> set[tuple]:
    """Keys for `gcloud firestore indexes composite list --format=json` output.

    The implicit trailing `__name__` field the API appends is ignored.
    """
    keys = set()
    for index in live:
        collection = index["name"].split("/collectionGroups/")[1].split("/")[0]
        fields = [
            (f["fieldPath"], f.get("order") or f.get("arrayConfig"))
            for f in index.get("fields", [])
            if f["fieldPath"] != "__name__"
        ]
        keys.add(_index_key(collection, index.get("queryScope"), fields))
    return keys


def _normalize_rules(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def rules_differ(live_rules: str, committed_rules: str) -> bool:
    return _normalize_rules(live_rules) != _normalize_rules(committed_rules)


def find_drift(*, live_indexes: list[dict[str, Any]], live_rules: str, repo_root: Path = REPO_ROOT) -> list[str]:
    """Human-readable drift findings; an empty list means no drift."""
    findings: list[str] = []
    committed = json.loads((repo_root / "firestore.indexes.json").read_text())
    live_keys, committed_keys = live_index_keys(live_indexes), committed_index_keys(committed)
    for key in sorted(live_keys - committed_keys, key=str):
        findings.append(f"index exists live but not in firestore.indexes.json: {key}")
    for key in sorted(committed_keys - live_keys, key=str):
        findings.append(f"index is in firestore.indexes.json but not live: {key}")
    if rules_differ(live_rules, (repo_root / "firestore.rules").read_text()):
        findings.append("live Firestore ruleset differs from firestore.rules")
    return findings


# ── live state (read-only) ──────────────────────────────────────────────────


def _gcloud(*args: str) -> str:
    try:
        return subprocess.run(["gcloud", *args], capture_output=True, text=True, check=True).stdout
    except FileNotFoundError as error:
        raise RuntimeError("gcloud is not installed or not on PATH") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"gcloud {args[0]} failed: {(error.stderr or '').strip()}") from error


def read_live_indexes(project: str) -> list[dict[str, Any]]:
    return json.loads(
        _gcloud("firestore", "indexes", "composite", "list", f"--project={project}", "--format=json") or "[]"
    )


def _rules_api(path: str, project: str, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"https://firebaserules.googleapis.com/v1/{path}",
        headers={"Authorization": f"Bearer {token}", "x-goog-user-project": project},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed https googleapis URL
        return json.loads(response.read())


def read_live_rules(project: str) -> str:
    token = _gcloud("auth", "print-access-token").strip()
    release = None
    page_token = ""
    while release is None:
        query = f"?pageToken={page_token}" if page_token else ""
        page = _rules_api(f"projects/{project}/releases{query}", project, token)
        release = next((r for r in page.get("releases", []) if r["name"].endswith("/releases/cloud.firestore")), None)
        page_token = page.get("nextPageToken", "")
        if not page_token:
            break
    if release is None:
        raise RuntimeError("no cloud.firestore release found: no rules are deployed")
    ruleset = _rules_api(release["rulesetName"], project, token)
    return "\n".join(file["content"] for file in ruleset["source"]["files"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--project", default=load_settings().google_cloud_project, help="GCP project id")
    args = parser.parse_args()
    if not _NAME_PATTERN.fullmatch(args.project):
        print(f"check_firestore_drift: invalid project name: {args.project!r}", file=sys.stderr)
        raise SystemExit(2)  # 2 = could not check; 1 is reserved for drift

    try:
        findings = find_drift(live_indexes=read_live_indexes(args.project), live_rules=read_live_rules(args.project))
    except (RuntimeError, OSError, ValueError, KeyError) as error:
        print(f"check_firestore_drift: could not check: {error}", file=sys.stderr)
        raise SystemExit(2) from error

    if findings:
        print(f"Firestore drift in {args.project}:")
        for finding in findings:
            print(f"  - {finding}")
        raise SystemExit(1)
    print(f"No drift: live rules and composite indexes in {args.project} match the committed files.")


if __name__ == "__main__":
    main()
