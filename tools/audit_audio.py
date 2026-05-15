"""
Audit suspicious cached example audio blobs in GCS.

Heuristic:
- example audio blobs smaller than a language-specific threshold are suspicious

This tool is intentionally REPORT-ONLY.
It does not delete or regenerate audio.

Examples:

    python -m tools.audit_audio \
        --project knotmem26 \
        --bucket verbboard-audio-stage \
        --language all \
        --voice all \
        --csv suspects.csv

    python -m tools.audit_audio \
        --language he \
        --voice female \
        --csv he_suspects.csv

    python -m tools.audit_audio \
        --language en \
        --min-bytes 5000
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

from google.cloud import storage

from core.supported_languages import (
    supported_languages_list,
    supported_languages_with_all,
)

DEFAULT_MIN_BYTES = {
    "en": 7000,
    "es": 9000,
    "he": 12000,
    "ru": 15000,
}


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
        "--min-bytes",
        type=int,
        default=None,
        help=(
            "Override language-specific threshold. "
            "If omitted, defaults are used per language."
        ),
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Max suspects to print per language",
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


def _threshold_for_language(
    language: str,
    override: int | None,
) -> int:
    if override is not None:
        return override

    return DEFAULT_MIN_BYTES.get(language, 10000)


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

    suspects: list[dict[str, Any]] = []

    for language in languages:
        prefix = f"audio/{language}/"
        threshold = _threshold_for_language(language, args.min_bytes)

        print(f"[{language}] scanning {prefix} " f"(threshold={threshold} bytes)")

        for blob in bucket.list_blobs(prefix=prefix):
            parsed = _parse_blob_name(blob.name)

            if not parsed:
                continue

            if args.voice != "all" and parsed["voice"] != args.voice:
                continue

            size_bytes = blob.size or 0

            if size_bytes >= threshold:
                continue

            suspects.append(
                {
                    "language": parsed["language"],
                    "voice": parsed["voice"],
                    "verb_id": parsed["verb_id"],
                    "example_key": parsed["example_key"],
                    "size_bytes": size_bytes,
                    "threshold_bytes": threshold,
                    "updated": (
                        blob.updated.isoformat()
                        if isinstance(blob.updated, datetime)
                        else ""
                    ),
                    "blob_name": blob.name,
                }
            )

    suspects.sort(key=lambda row: row["size_bytes"])

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in suspects:
        grouped[row["language"]].append(row)

    print()

    for language in languages:
        rows = grouped.get(language, [])

        print(f"[{language}] suspects={len(rows)}")

        for row in rows[: args.limit]:
            print(
                f"  {row['size_bytes']:>8}  "
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
                "threshold_bytes",
                "updated",
                "blob_name",
            ],
        )

        writer.writeheader()
        writer.writerows(suspects)

    print(f"Wrote {len(suspects)} suspects to {args.csv}")


if __name__ == "__main__":
    main()
