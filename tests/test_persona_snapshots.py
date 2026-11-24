"""Persona snapshots (issue #143): parser, diff, evolution, publish, review helpers, publish tool."""

from __future__ import annotations

from pathlib import Path

import pytest

from core import persona_review_service as review_svc
from core import persona_snapshot_service as svc
from tools import persona_publish

REAL_PERSONAS = Path(__file__).resolve().parent.parent / "docs" / "marketing" / "personas.md"

FIXTURE = """# Personas

Last review: 2026-11-24. Next review: 2026-12-15.

## Claim statuses

- **assumed**: reasoning.

## Dana, the stuck intermediate

Phone-first learner.

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| Learners search for verbs | assumed | none yet | 0 | 2026-11-24 |
| Pipes survive | Observed | a | b evidence | 12 | 2026-11-24 |

Next test: #136

## Misha, English learner

Android user.

| Claim | Status | Evidence | n | Last checked |
|---|---|---|---|---|
| Communities bring users | refuted | #135 | 31 | 2026-11-24 |

Next test: #135

## Notes

Just prose, no claims table.

## Retired claims

None yet. Format: claim, evidence.
Old claim, evidence, 2026-01-01, learned X.
"""


def test_parser_reads_personas_claims_and_dates() -> None:
    parsed = svc.parse_personas_markdown(FIXTURE)

    assert parsed["last_review"] == "2026-11-24"
    assert parsed["next_review"] == "2026-12-15"
    assert [p["name"] for p in parsed["personas"]] == ["Dana, the stuck intermediate", "Misha, English learner"]
    dana = parsed["personas"][0]
    assert dana["summary"] == "Phone-first learner."
    assert dana["next_test"] == "#136"
    assert [c["claim"] for c in dana["claims"]] == ["Learners search for verbs", "Pipes survive"]
    assert parsed["unparsed_rows"] == []


def test_parser_keeps_pipe_in_evidence_and_lowercases_status() -> None:
    claim = svc.parse_personas_markdown(FIXTURE)["personas"][0]["claims"][1]

    assert claim["status"] == "observed"
    assert claim["evidence"] == "a | b evidence"
    assert claim["n"] == "12"
    assert claim["last_checked"] == "2026-11-24"


def test_parser_skips_special_sections_and_placeholder() -> None:
    parsed = svc.parse_personas_markdown(FIXTURE)
    names = [p["name"].lower() for p in parsed["personas"]]

    assert "claim statuses" not in names
    assert "retired claims" not in names
    assert "notes" not in names
    assert parsed["retired"] == ["Old claim, evidence, 2026-01-01, learned X."]


def test_misspelled_status_goes_to_unparsed_rows_but_header_does_not() -> None:
    text = FIXTURE.replace("| refuted |", "| refuted? |")

    parsed = svc.parse_personas_markdown(text)

    assert len(parsed["unparsed_rows"]) == 1
    assert "Misha" in parsed["unparsed_rows"][0]
    assert "Communities bring users" in parsed["unparsed_rows"][0]


def test_real_personas_file_parses_cleanly() -> None:
    parsed = svc.parse_personas_markdown(REAL_PERSONAS.read_text(encoding="utf-8"))

    assert len(parsed["personas"]) == 5
    assert parsed["unparsed_rows"] == []
    for persona in parsed["personas"]:
        assert persona["claims"]
        for claim in persona["claims"]:
            assert claim["status"] in svc.VALID_STATUSES


def _snap(date: str, claims: dict[str, tuple[str, str, str]], persona: str = "P") -> dict:
    return {
        "date": date,
        "personas": [
            {
                "name": persona,
                "claims": [
                    {"claim": text, "status": status, "n": n, "evidence": evidence}
                    for text, (status, n, evidence) in claims.items()
                ],
            }
        ],
    }


def _kinds(events: list[dict]) -> list[str]:
    return sorted(event["kind"] for event in events)


def test_diff_status_change() -> None:
    old = _snap("2026-01-01", {"c": ("assumed", "0", "x")})
    new = _snap("2026-01-22", {"c": ("observed", "0", "x")})

    events = svc.diff_snapshots(old, new)

    assert events == [{"kind": "status", "persona": "P", "claim": "c", "from": "assumed", "to": "observed"}]


def test_diff_evidence_or_n_change() -> None:
    old = _snap("a", {"c": ("assumed", "0", "x"), "d": ("assumed", "0", "x")})
    new = _snap("b", {"c": ("assumed", "5", "x"), "d": ("assumed", "0", "y")})

    assert _kinds(svc.diff_snapshots(old, new)) == ["evidence", "evidence"]


def test_diff_added_and_removed_claim() -> None:
    old = _snap("a", {"keep": ("assumed", "0", ""), "gone": ("assumed", "0", "")})
    new = _snap("b", {"keep": ("assumed", "0", ""), "fresh": ("assumed", "0", "")})

    events = svc.diff_snapshots(old, new)

    assert _kinds(events) == ["added", "removed"]
    assert {e["claim"] for e in events} == {"gone", "fresh"}


def test_diff_new_persona() -> None:
    old = _snap("a", {"c": ("assumed", "0", "")})
    new = _snap("b", {"c": ("assumed", "0", "")})
    new["personas"].append({"name": "Q", "claims": [{"claim": "z", "status": "assumed", "n": "0", "evidence": ""}]})

    assert _kinds(svc.diff_snapshots(old, new)) == ["added", "persona_added"]


def test_diff_first_snapshot_has_no_events() -> None:
    assert svc.diff_snapshots(None, _snap("a", {"c": ("assumed", "0", "")})) == []


def test_diff_identical_snapshots_have_no_events() -> None:
    snap = _snap("a", {"c": ("assumed", "0", "x")})

    assert svc.diff_snapshots(snap, dict(snap)) == []


def test_build_evolution_newest_first_with_baseline() -> None:
    first = _snap("2026-01-01", {"c": ("assumed", "0", "")})
    second = _snap("2026-01-22", {"c": ("observed", "0", "")})
    second["commit"] = "abc123"

    timeline = svc.build_evolution([first, second])

    assert [entry["date"] for entry in timeline] == ["2026-01-22", "2026-01-01"]
    assert timeline[0]["commit"] == "abc123"
    assert [e["kind"] for e in timeline[0]["events"]] == ["status"]
    assert timeline[1]["events"] == []


def test_build_evolution_empty() -> None:
    assert svc.build_evolution([]) == []


def test_publish_snapshot_stores_document(fake_db) -> None:
    document = svc.publish_snapshot(FIXTURE, "2026-11-24", "abc123")

    stored = fake_db._docs[f"{svc.COLLECTION}/2026-11-24"]
    assert stored["date"] == "2026-11-24"
    assert stored["commit"] == "abc123"
    assert len(stored["personas"]) == 2
    assert document["published_at"]
    assert [s["date"] for s in svc.list_snapshots()] == ["2026-11-24"]


def test_publish_snapshot_same_date_replaces(fake_db) -> None:
    svc.publish_snapshot(FIXTURE, "2026-11-24", "one")
    svc.publish_snapshot(FIXTURE, "2026-11-24", "two")

    paths = [p for p in fake_db._docs if p.startswith(f"{svc.COLLECTION}/")]
    assert paths == [f"{svc.COLLECTION}/2026-11-24"]
    assert fake_db._docs[paths[0]]["commit"] == "two"


def test_publish_snapshot_rejects_unparsed_rows(fake_db) -> None:
    with pytest.raises(ValueError, match="could not be read"):
        svc.publish_snapshot(FIXTURE.replace("| refuted |", "| refuted? |"), "2026-11-24")

    assert not [p for p in fake_db._docs if p.startswith(f"{svc.COLLECTION}/")]


def test_publish_snapshot_rejects_empty_markdown(fake_db) -> None:
    with pytest.raises(ValueError, match="no personas"):
        svc.publish_snapshot("# nothing here\n", "2026-11-24")


def test_list_snapshots_oldest_first(fake_db) -> None:
    svc.publish_snapshot(FIXTURE, "2026-12-15")
    svc.publish_snapshot(FIXTURE, "2026-11-24")

    assert [s["date"] for s in svc.list_snapshots()] == ["2026-11-24", "2026-12-15"]


def _seed_review(fake_db, day: str, status: str = "open", **extra) -> None:
    fake_db._docs[f"{review_svc.COLLECTION}/{day}"] = {
        "date": day,
        "status": status,
        "window": {"date_from": "2026-10-01", "date_to": "2026-10-21"},
        "body": "figures",
        **extra,
    }


def test_mark_done_unknown_date_is_false(fake_db) -> None:
    assert review_svc.mark_done("2026-01-01") is False


def test_mark_done_is_idempotent_and_keeps_done_at(fake_db) -> None:
    _seed_review(fake_db, "2026-11-24")

    assert review_svc.mark_done("2026-11-24") is True
    doc = fake_db._docs[f"{review_svc.COLLECTION}/2026-11-24"]
    assert doc["status"] == "done"
    first_done_at = doc["done_at"]
    assert first_done_at

    assert review_svc.mark_done("2026-11-24") is True
    assert fake_db._docs[f"{review_svc.COLLECTION}/2026-11-24"]["done_at"] == first_done_at


def test_list_reviews_newest_first_without_body(fake_db) -> None:
    _seed_review(fake_db, "2026-10-01", status="done")
    _seed_review(fake_db, "2026-11-24", issue_number=7)

    rows = review_svc.list_reviews()

    assert [r["date"] for r in rows] == ["2026-11-24", "2026-10-01"]
    assert rows[0]["issue_number"] == 7
    assert all("body" not in r for r in rows)


def test_get_open_review_detail_and_banner(fake_db) -> None:
    assert review_svc.get_open_review_detail() is None
    assert review_svc.banner_text() is None

    _seed_review(fake_db, "2026-11-24")

    detail = review_svc.get_open_review_detail()
    assert detail is not None
    assert detail["date"] == "2026-11-24"
    assert detail["body"] == "figures"
    banner = review_svc.banner_text()
    assert banner is not None
    assert "2026-11-24" in banner


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "personas.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_publish_tool_dry_run_real_file_returns_zero(capsys) -> None:
    assert persona_publish.main(["--dry-run"]) == 0
    assert "claims" in capsys.readouterr().out


def test_publish_tool_bad_file_returns_one(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setattr(persona_publish, "PERSONAS_FILE", _write(tmp_path, FIXTURE.replace("| refuted |", "| oops |")))

    assert persona_publish.main(["--dry-run"]) == 1
    assert "UNREADABLE ROW" in capsys.readouterr().out
