"""
Remove unhashed audio blobs from GCS.

Hashed blobs (current format):  example_3_9ac443340b.mp3, present_1s_abc123def4.mp3
Unhashed blobs (old format):     example_3.mp3, present_1s.mp3

By default this is a dry run — pass --execute to actually delete.

Run from project root (needs GCP auth):

    python -m tools.clean_audio --language he \\
        --project knotmem26 --bucket verbboard-audio-stage

    python -m tools.clean_audio --language all --execute \\
        --project knotmem26 --bucket verbboard-audio-stage
"""

from __future__ import annotations

import argparse
import os
import re
import sys

from core.audio_backend.gcs import GCSAudioBackend
from core.supported_languages import (
    supported_languages_list,
    supported_languages_with_all,
)

# Matches filenames that end with _<10 hex chars>.mp3 — the current hashed format.
_HASHED_RE = re.compile(r"_[0-9a-f]{10}\.mp3$")


def _clean_language(
    language: str,
    audio_backend: GCSAudioBackend,
    execute: bool,
) -> dict[str, int]:
    prefix = f"audio/{language}/"
    print(f"\n[{language}] Listing blobs under {prefix}...")
    blobs = list(audio_backend.bucket.list_blobs(prefix=prefix))
    print(f"[{language}] {len(blobs)} total blobs")

    unhashed = [b for b in blobs if not _HASHED_RE.search(b.name)]
    print(f"[{language}] {len(unhashed)} unhashed blobs found")

    for blob in unhashed:
        if execute:
            blob.delete()
            print(f"  Deleted: {blob.name}")
        else:
            print(f"  Would delete: {blob.name}")

    return {"total": len(blobs), "deleted": len(unhashed)}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Remove unhashed (old-style) audio blobs from GCS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m tools.clean_audio --language he --dry-run\n"
            "  python -m tools.clean_audio --language all --execute \\\n"
            "      --project knotmem26 --bucket verbboard-audio-stage\n"
        ),
    )
    parser.add_argument(
        "--language",
        required=True,
        choices=supported_languages_with_all(),
        help="Language code or 'all'",
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
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete the blobs (default is dry-run)",
    )
    action.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Print what would be deleted without deleting (default)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if not args.project:
        sys.exit("ERROR: --project or GOOGLE_CLOUD_PROJECT is required")
    if not args.bucket:
        sys.exit("ERROR: --bucket or AUDIO_BUCKET is required")

    languages = supported_languages_list() if args.language == "all" else [args.language]
    audio_backend = GCSAudioBackend(project=args.project, bucket=args.bucket)

    execute = args.execute
    if not execute:
        print("DRY RUN — pass --execute to actually delete blobs\n")

    totals: dict[str, int] = {"total": 0, "deleted": 0}
    for language in languages:
        counts = _clean_language(language, audio_backend, execute)
        for k in totals:
            totals[k] += counts[k]

    action = "deleted" if execute else "would delete"
    print(f"\nSUMMARY: scanned={totals['total']}  {action}={totals['deleted']}")


if __name__ == "__main__":
    main()
