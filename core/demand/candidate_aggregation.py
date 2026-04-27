from __future__ import annotations

from typing import Any

from core.demand.query_resolution import resolve_query
from core.demand.recommendation import recommend


def aggregate_candidates(
    *,
    events: list[dict[str, Any]],
    cutoff: int,
) -> dict[str, list[dict[str, Any]]]:
    resolved_map: dict[str, dict[str, Any]] = {}
    unresolved_map: dict[tuple[str, str], dict[str, Any]] = {}

    for event in events:
        language = event["language"]
        query = event["query"]
        created_at = event["created_at"]

        resolution = resolve_query(language=language, query=query)

        if resolution["resolved"]:
            key = resolution["verb_id"]

            bucket = resolved_map.setdefault(
                key,
                {
                    "language": language,
                    "verb_id": resolution["verb_id"],
                    "lemma": resolution["lemma"],
                    "count": 0,
                    "first_seen_at": created_at,
                    "last_seen_at": created_at,
                    "queries": set(),
                },
            )

            bucket["count"] += 1
            bucket["queries"].add(query)

            if created_at < bucket["first_seen_at"]:
                bucket["first_seen_at"] = created_at
            if created_at > bucket["last_seen_at"]:
                bucket["last_seen_at"] = created_at

        else:
            key = (language, resolution["normalized_query"])

            bucket = unresolved_map.setdefault(
                key,
                {
                    "language": language,
                    "normalized_query": resolution["normalized_query"],
                    "lemma_candidate": resolution["normalized_query"],
                    "count": 0,
                    "first_seen_at": created_at,
                    "last_seen_at": created_at,
                    "queries": set(),
                },
            )

            bucket["count"] += 1
            bucket["queries"].add(query)

            if created_at < bucket["first_seen_at"]:
                bucket["first_seen_at"] = created_at
            if created_at > bucket["last_seen_at"]:
                bucket["last_seen_at"] = created_at

    resolved = [
        {**value, "queries": sorted(value["queries"])}
        for value in resolved_map.values()
        if value["count"] >= cutoff
    ]

    unresolved = []

    for value in unresolved_map.values():
        if value["count"] < cutoff:
            continue

        recommendation, reason = recommend(
            language=value["language"],
            normalized_query=value["normalized_query"],
            count=value["count"],
            cutoff=cutoff,
        )

        unresolved.append(
            {
                **value,
                "queries": sorted(value["queries"]),
                "recommendation": recommendation,
                "reason": reason,
            }
        )

    resolved.sort(key=lambda item: (-item["count"], item["language"], item["verb_id"]))
    unresolved.sort(
        key=lambda item: (-item["count"], item["language"], item["normalized_query"])
    )

    return {
        "resolved": resolved,
        "unresolved": unresolved,
    }
