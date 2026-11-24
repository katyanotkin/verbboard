"""Persona snapshots for the admin personas page (issue #143).

`docs/marketing/personas.md` is the source of truth but is not in the image, so `tools/persona_publish.py`
parses it and stores a derived, read-only snapshot in Firestore `persona_snapshots/{YYYY-MM-DD}`. The admin
page reads snapshots and shows how claims changed between them. Nothing here edits the markdown or the claims.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any

from core.storage.firestore_db import get_db

logger = logging.getLogger(__name__)

COLLECTION = "persona_snapshots"
VALID_STATUSES = ("assumed", "observed", "refuted")
_SKIPPED_HEADINGS = ("claim statuses", "retired claims")
_SEPARATOR_ROW = re.compile(r"^\|\s*:?-{2,}")


def _split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _parse_claim_row(cells: list[str]) -> dict[str, str] | None:
    """`| claim | status | evidence | n | last checked |`; evidence may itself contain pipes."""
    if len(cells) < 5:
        return None
    status = cells[1].lower()
    if status not in VALID_STATUSES:
        return None  # the header row, or a malformed one
    return {
        "claim": cells[0],
        "status": status,
        "evidence": " | ".join(cells[2:-2]),
        "n": cells[-2],
        "last_checked": cells[-1],
    }


def parse_personas_markdown(text: str) -> dict[str, Any]:
    """Pure: personas.md text -> {last_review, next_review, personas, retired}."""
    personas: list[dict[str, Any]] = []
    retired: list[str] = []
    current: dict[str, Any] | None = None
    in_retired = False
    summary_lines: list[str] = []
    unparsed_rows: list[str] = []
    last_review = next_review = ""

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        review_match = re.search(r"Last review:\s*(\d{4}-\d{2}-\d{2})\.?\s*Next review:\s*(\d{4}-\d{2}-\d{2})", line)
        if review_match:
            last_review, next_review = review_match.groups()
        if line.startswith("## "):
            heading = line[3:].strip()
            in_retired = heading.lower() == "retired claims"
            if heading.lower() in _SKIPPED_HEADINGS:
                current = None
                continue
            current = {"name": heading, "summary": "", "claims": [], "next_test": ""}
            personas.append(current)
            summary_lines = []
            continue
        if in_retired:
            if line.strip() and not line.strip().lower().startswith("none"):
                retired.append(line.strip())
            continue
        if current is None:
            continue
        if line.startswith("|"):
            if _SEPARATOR_ROW.match(line):
                continue
            cells = _split_row(line)
            claim = _parse_claim_row(cells)
            if claim:
                current["claims"].append(claim)
            elif not (len(cells) > 1 and cells[1].lower() == "status"):  # the header row is expected
                # A typo in a status or a stray pipe must not silently look like a removed claim later.
                unparsed_rows.append(f"{current['name']}: {line.strip()[:80]}")
            continue
        if line.lower().startswith("next test:"):
            current["next_test"] = line.split(":", 1)[1].strip()
        elif line.strip() and not summary_lines:
            summary_lines.append(line.strip())
            current["summary"] = line.strip()
    # Only sections with a claims table are personas, so a future "## Notes" section is not shown as one.
    personas = [persona for persona in personas if persona["claims"]]
    return {
        "last_review": last_review,
        "next_review": next_review,
        "personas": personas,
        "retired": retired,
        "unparsed_rows": unparsed_rows,
    }


def diff_snapshots(previous: dict[str, Any] | None, current: dict[str, Any]) -> list[dict[str, str]]:
    """Pure: what changed between two parsed snapshots, as flat events for the timeline."""
    previous_claims = _claims_by_key(previous)
    current_claims = _claims_by_key(current)
    events: list[dict[str, str]] = []
    for key, claim in current_claims.items():
        persona, text = key
        old = previous_claims.get(key)
        if old is None:
            if previous is not None:
                events.append({"kind": "added", "persona": persona, "claim": text, "to": claim["status"]})
        elif old["status"] != claim["status"]:
            events.append(
                {"kind": "status", "persona": persona, "claim": text, "from": old["status"], "to": claim["status"]}
            )
        elif old["n"] != claim["n"] or old["evidence"] != claim["evidence"]:
            events.append({"kind": "evidence", "persona": persona, "claim": text, "to": claim["status"]})
    for key, claim in previous_claims.items():
        if key not in current_claims:
            events.append({"kind": "removed", "persona": key[0], "claim": key[1], "from": claim["status"]})
    previous_names = {p["name"] for p in (previous or {}).get("personas", [])}
    for persona_doc in current.get("personas", []):
        if previous is not None and persona_doc["name"] not in previous_names:
            events.append({"kind": "persona_added", "persona": persona_doc["name"], "claim": ""})
    return events


def _claims_by_key(snapshot: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, str]]:
    claims: dict[tuple[str, str], dict[str, str]] = {}
    for persona in (snapshot or {}).get("personas", []):
        for claim in persona.get("claims", []):
            claims[(persona["name"], claim["claim"])] = claim
    return claims


def publish_snapshot(markdown_text: str, snapshot_date: str, commit: str = "") -> dict[str, Any]:
    """Store (or replace) the snapshot for one date. Returns the stored document."""
    parsed = parse_personas_markdown(markdown_text)
    if not parsed["personas"]:
        raise ValueError("no personas found in the markdown")
    if parsed["unparsed_rows"]:
        raise ValueError(
            "table rows could not be read (check status spelling and pipes): " + "; ".join(parsed["unparsed_rows"])
        )
    document = {
        **parsed,
        "date": snapshot_date,
        "commit": commit,
        "published_at": datetime.now(UTC).isoformat(),
    }
    get_db().collection(COLLECTION).document(snapshot_date).set(document)
    return document


def list_snapshots() -> list[dict[str, Any]]:
    """All snapshots, oldest first. The collection gets one doc per review, so it stays tiny."""
    documents = [doc.to_dict() or {} for doc in get_db().collection(COLLECTION).stream()]
    return sorted((doc for doc in documents if doc.get("date")), key=lambda doc: doc["date"])


def build_evolution(snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Newest first: for every snapshot, the changes since the one before it (the first has none)."""
    timeline: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for snapshot in snapshots:
        timeline.append(
            {
                "date": snapshot["date"],
                "commit": snapshot.get("commit", ""),
                "events": diff_snapshots(previous, snapshot),
            }
        )
        previous = snapshot
    return list(reversed(timeline))
