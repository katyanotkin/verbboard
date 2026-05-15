"""
Audit suspicious cached example audio blobs in GCS.

This tool is intentionally REPORT-ONLY.
It does not delete or regenerate audio.

Strategy:
- group example audio blobs by language
- compute average blob size per language
- report the smallest N blobs per language
- include % distance from language average

Examples:

    python -m tools.audit_audio \
        --project knotmem26 \
        --bucket verbboard-audio-stage \
        --language all \
        --voice all \
        --csv suspects.csv

    python -m tools.audit_audio \
        --language he \
        --bottom-n 12

    python -m tools.audit_audio \
        --language ru \
        --voice female
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime
from statistics import mean
from typing import Any

from google.cloud import storage

from core.supported_languages import (
    supported_languages_list,
    supported_languages_with_all,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit suspicious cached example audio blobs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--language",
        required=True,
        choices=supported_languages_with_all(),
        help="Language code or 'all'",
    )

    parser.add_argument(
        "--voice",
        choices=["female", "male", "all"],
        default="all",
        help="Voice filter (default: all)",
    )

    parser.add_argument(
        "--project",
        default=os.getenv("GOOGLE_CLOUD_PROJECT", ""),
        help="GCP project ID (or set GOOGLE_CLOUD_PROJECT)",
    )

    parser.add_argument(
        "--bucket",
        default=os.getenv("AUDIO_BUCKET", ""),
        help="GCS bucket name (or set AUDIO_BUCKET)",
    )

    parser.add_argument(
        "--bottom-n",
        type=int,
        default=12,
        help="Report N smallest blobs per language",
    )

    parser.add_argument(
        "--csv",
        default="audio_suspects.csv",
        help="CSV output path",
    )

    return parser.parse_args()


def _parse_blob_name(blob_name: str) -> dict[str, str] | None:
    """
    Example blob path:

        audio/he/he_lehavi/female/example_1_abcdef.mp3
    """

    parts = blob_name.split("/")

    if len(parts) < 5:
        return None

    if parts[0] != "audio":
        return None

    language = parts[1]
    verb_id = parts[2]
    voice = parts[3]
    filename = parts[4]

    if "example_" not in filename:
        return None

    return {
        "language": language,
        "verb_id": verb_id,
        "voice": voice,
        "example_key": filename,
    }


def main() -> None:
    args = _parse_args()

    if not args.project:
        sys.exit("ERROR: --project or GOOGLE_CLOUD_PROJECT is required")

    if not args.bucket:
        sys.exit("ERROR: --bucket or AUDIO_BUCKET is required")

    client = storage.Client(project=args.project)
    bucket = client.bucket(args.bucket)

    languages = (
        supported_languages_list() if args.language == "all" else [args.language]
    )

    rows_by_language: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for language in languages:
        prefix = f"audio/{language}/"

        print(f"[{language}] scanning {prefix}")

        for blob in bucket.list_blobs(prefix=prefix):
            parsed = _parse_blob_name(blob.name)

            if not parsed:
                continue

            if args.voice != "all" and parsed["voice"] != args.voice:
                continue

            size_bytes = blob.size or 0

            row = {
                "language": parsed["language"],
                "voice": parsed["voice"],
                "verb_id": parsed["verb_id"],
                "example_key": parsed["example_key"],
                "size_bytes": size_bytes,
                "updated": (
                    blob.updated.isoformat()
                    if isinstance(blob.updated, datetime)
                    else ""
                ),
                "blob_name": blob.name,
            }

            rows_by_language[language].append(row)

    output_rows: list[dict[str, Any]] = []

    print()

    for language in languages:
        rows = rows_by_language.get(language, [])

        if not rows:
            print(f"[{language}] no example audio found")
            print()
            continue

        sizes = [row["size_bytes"] for row in rows]
        avg_size = mean(sizes)

        sorted_rows = sorted(rows, key=lambda row: row["size_bytes"])
        smallest_rows = sorted_rows[: args.bottom_n]

        print(
            f"[{language}] "
            f"count={len(rows)} "
            f"avg={round(avg_size)} "
            f"bottom={len(smallest_rows)}"
        )

        for row in smallest_rows:
            pct_from_avg = ((row["size_bytes"] - avg_size) / avg_size) * 100

            enriched_row = {
                **row,
                "avg_size_bytes": round(avg_size),
                "pct_from_avg": round(pct_from_avg, 2),
            }

            output_rows.append(enriched_row)

            print(
                f"  {row['size_bytes']:>8}  "
                f"{pct_from_avg:>7.2f}%  "
                f"{row['voice']:<6}  "
                f"{row['blob_name']}"
            )

        print()

    with open(args.csv, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "language",
                "voice",
                "verb_id",
                "example_key",
                "size_bytes",
                "avg_size_bytes",
                "pct_from_avg",
                "updated",
                "blob_name",
            ],
        )

        writer.writeheader()
        writer.writerows(output_rows)

    print(f"Wrote {len(output_rows)} rows " f"to {args.csv}")


if __name__ == "__main__":
    main()
