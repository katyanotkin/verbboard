"""
Audit cached audio blobs in GCS.

Suspect scoring: linear fit (size ~ text_length) per language/voice replaces
the old deviation-from-mean metric. A short phrase that produces a tiny file
is normal; the fit detects files that are small *for their phrase length*.

Missing check (--missing): loads Firestore verbs, builds expected GCS keys
(same logic as _warm_verb_audio), and reports any that are absent.

Examples:

    python -m tools.audit_audio \\
        --project knotmem26 \\
        --bucket verbboard-audio-stage \\
        --language all --voice all --missing

    python -m tools.audit_audio --language he --bottom-n 12

    python -m tools.audit_audio \\
        --language ru --missing --missing-csv missing.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime
from typing import Any

# Snapshot env vars before any core import triggers load_dotenv(override=True).
_ENV_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
_ENV_BUCKET = os.getenv("AUDIO_BUCKET", "")

from google.cloud import storage  # noqa: E402

import core.languages.en.plugin  # noqa: E402, F401
import core.languages.es.plugin  # noqa: E402, F401
import core.languages.he.plugin  # noqa: E402, F401
import core.languages.ru.plugin  # noqa: E402, F401
from core.audio_service import build_audio_key, build_hashed_audio_key  # noqa: E402
from core.registry import get as get_plugin  # noqa: E402
from core.supported_languages import (  # noqa: E402
    supported_languages_list,
    supported_languages_with_all,
)
from core.tts import VOICES  # noqa: E402
from core.verb_loader import load_entries_for_language  # noqa: E402

# Mirrors _NO_AUDIO_ROW_KEYS in admin_candidates.py and render.py.
# These rows have no audio button and are never pre-warmed.
_NO_AUDIO_ROW_KEYS: frozenset[str] = frozenset({"aspect", "pair", "binyan", "root"})


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit cached audio blobs in GCS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
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
        default=_ENV_PROJECT,
        help="GCP project ID (or set GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--bucket",
        default=_ENV_BUCKET,
        help="GCS bucket name (or set AUDIO_BUCKET)",
    )
    parser.add_argument(
        "--bottom-n",
        type=int,
        default=12,
        help="Report N most-suspicious blobs per language/voice (default: 12)",
    )
    parser.add_argument(
        "--csv",
        default=None,
        help=(
            "Suspects CSV output path "
            "(default: audio_suspects_{env}.csv derived from bucket name)"
        ),
    )
    parser.add_argument(
        "--missing",
        action="store_true",
        help="Also report expected audio files absent from GCS",
    )
    parser.add_argument(
        "--missing-csv",
        default=None,
        help=(
            "Missing audio CSV output path "
            "(default: audio_missing_{env}.csv derived from bucket name)"
        ),
    )
    return parser.parse_args()


def _parse_blob_name(blob_name: str) -> dict[str, str] | None:
    """audio/{language}/{verb_id}/{voice}/{form_key}.mp3"""
    parts = blob_name.split("/")
    if len(parts) < 5 or parts[0] != "audio":
        return None
    return {
        "language": parts[1],
        "verb_id": parts[2],
        "voice": parts[3],
        "form_key": parts[4].removesuffix(".mp3"),
    }


def _iter_board_items(
    verb: Any,
    language: str,
    voice_key: str,
    *,
    skip_no_audio: bool = False,
):
    """Yield (base_form_key, text) for every audio item on the board."""
    voice_meta = VOICES[language][voice_key]
    plugin = get_plugin(language)
    board = plugin.build_board(verb, voice_key, voice_meta.label)

    for section in board.sections:
        for row in section["rows"]:
            base_key = str(row["key"])
            if skip_no_audio and base_key in _NO_AUDIO_ROW_KEYS:
                continue
            text = str(row["text"] or "").strip()
            if text:
                yield base_key, text

    for index, example in enumerate(board.verb.examples, start=1):
        text = example.dst.strip()
        if text:
            yield f"example_{index}", text


def _build_lookups(
    languages: list[str],
    voices_filter: str,
) -> tuple[
    dict[tuple[str, str, str], str],
    dict[tuple[str, str, str, str], str],
]:
    """
    Returns:
      text_lookup:   (language, verb_id, form_key) -> text
                     form_key = build_hashed_audio_key(base_key, text)
      expected_keys: (language, verb_id, voice, form_key) -> gcs_blob_name
                     only for voices matching voices_filter
    """
    text_lookup: dict[tuple[str, str, str], str] = {}
    expected_keys: dict[tuple[str, str, str, str], str] = {}

    for language in languages:
        print(f"[{language}] loading verbs from Firestore...")
        entries = load_entries_for_language(language=language)
        print(f"[{language}] {len(entries)} verbs")

        all_voices = list(VOICES.get(language, {}).keys())
        active_voices = (
            all_voices
            if voices_filter == "all"
            else [v for v in all_voices if v == voices_filter]
        )

        for verb in entries:
            # Text is voice-independent; build lookup from the first available voice.
            if all_voices:
                for base_key, text in _iter_board_items(verb, language, all_voices[0]):
                    form_key = build_hashed_audio_key(base_key, text)
                    text_lookup[(language, verb.id, form_key)] = text

            for voice_key in active_voices:
                for base_key, text in _iter_board_items(
                    verb, language, voice_key, skip_no_audio=True
                ):
                    form_key = build_hashed_audio_key(base_key, text)
                    gcs_key = build_audio_key(language, verb.id, voice_key, form_key)
                    expected_keys[(language, verb.id, voice_key, form_key)] = gcs_key

    return text_lookup, expected_keys


def _linear_fit(pairs: list[tuple[int, int]]) -> tuple[float, float]:
    """Least-squares: size = intercept + slope * text_len. Returns (intercept, slope)."""
    n = len(pairs)
    if n < 3:
        avg = sum(y for _, y in pairs) / max(n, 1)
        return (avg, 0.0)
    sum_x = sum(x for x, _ in pairs)
    sum_y = sum(y for _, y in pairs)
    sum_xy = sum(x * y for x, y in pairs)
    sum_xx = sum(x * x for x, _ in pairs)
    denom = n * sum_xx - sum_x * sum_x
    if denom == 0:
        return (sum_y / n, 0.0)
    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n
    return (intercept, slope)


def _env_suffix(bucket: str) -> str:
    """Extract 'stage' / 'prod' (or last segment) from a bucket name."""
    return bucket.rsplit("-", 1)[-1] if "-" in bucket else bucket


def main() -> None:
    args = _parse_args()

    if not args.project:
        sys.exit("ERROR: --project or GOOGLE_CLOUD_PROJECT is required")
    if not args.bucket:
        sys.exit("ERROR: --bucket or AUDIO_BUCKET is required")

    env = _env_suffix(args.bucket)
    suspects_csv = args.csv or f"audio_suspects_{env}.csv"
    missing_csv = args.missing_csv or f"audio_missing_{env}.csv"

    languages = (
        supported_languages_list() if args.language == "all" else [args.language]
    )

    text_lookup, expected_keys = _build_lookups(languages, args.voice)

    gcs_client = storage.Client(project=args.project)
    bucket = gcs_client.bucket(args.bucket)

    # (language, voice) -> list of enriched blob rows
    rows_by_lang_voice: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    actual_blob_names: set[str] = set()

    for language in languages:
        prefix = f"audio/{language}/"
        print(f"[{language}] scanning GCS {prefix}...")

        for blob in bucket.list_blobs(prefix=prefix):
            actual_blob_names.add(blob.name)
            parsed = _parse_blob_name(blob.name)
            if not parsed:
                continue
            if args.voice != "all" and parsed["voice"] != args.voice:
                continue

            text = text_lookup.get(
                (parsed["language"], parsed["verb_id"], parsed["form_key"]), ""
            )
            rows_by_lang_voice[(parsed["language"], parsed["voice"])].append(
                {
                    "language": parsed["language"],
                    "voice": parsed["voice"],
                    "verb_id": parsed["verb_id"],
                    "form_key": parsed["form_key"],
                    "text": text,
                    "text_len": len(text),
                    "size_bytes": blob.size or 0,
                    "updated": (
                        blob.updated.isoformat()
                        if isinstance(blob.updated, datetime)
                        else ""
                    ),
                    "blob_name": blob.name,
                }
            )

    # --- Suspects ---
    suspect_rows: list[dict[str, Any]] = []
    print()

    for (language, voice), rows in sorted(rows_by_lang_voice.items()):
        # Fit size ~ intercept + slope * text_len using rows where text is known.
        fit_pairs = [
            (row["text_len"], row["size_bytes"]) for row in rows if row["text_len"] > 0
        ]
        intercept, slope = _linear_fit(fit_pairs) if fit_pairs else (0.0, 1.0)

        def expected_size(
            text_len: int, _ic: float = intercept, _sl: float = slope
        ) -> float:
            if text_len == 0:
                # No text data: use intercept as a rough baseline
                return max(1.0, _ic)
            return max(1.0, _ic + _sl * text_len)

        scored: list[dict[str, Any]] = []
        for row in rows:
            exp = expected_size(row["text_len"])
            residual_pct = ((row["size_bytes"] - exp) / exp) * 100
            scored.append(
                {
                    **row,
                    "expected_size_bytes": round(exp),
                    "residual_pct": round(residual_pct, 2),
                }
            )

        scored.sort(key=lambda r: r["residual_pct"])
        bottom = scored[: args.bottom_n]

        print(
            f"[{language}/{voice}]  "
            f"blobs={len(rows)}  "
            f"fit: intercept={round(intercept)} slope={round(slope, 1)}  "
            f"bottom={len(bottom)}"
        )
        for row in bottom:
            print(
                f"  size={row['size_bytes']:>8}  "
                f"exp={row['expected_size_bytes']:>8}  "
                f"{row['residual_pct']:>8.2f}%  "
                f"len={row['text_len']:>4}  "
                f"{row['blob_name']}"
            )
            suspect_rows.append(row)

        print()

    with open(suspects_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "language",
                "voice",
                "verb_id",
                "form_key",
                "text",
                "text_len",
                "size_bytes",
                "expected_size_bytes",
                "residual_pct",
                "updated",
                "blob_name",
            ],
        )
        writer.writeheader()
        writer.writerows(suspect_rows)

    print(f"Wrote {len(suspect_rows)} suspect rows to {suspects_csv}")

    if not args.missing:
        return

    # --- Missing ---
    print()
    missing_rows: list[dict[str, Any]] = []

    for (language, verb_id, voice_key, form_key), gcs_key in sorted(
        expected_keys.items()
    ):
        if gcs_key not in actual_blob_names:
            text = text_lookup.get((language, verb_id, form_key), "")
            missing_rows.append(
                {
                    "language": language,
                    "verb_id": verb_id,
                    "voice": voice_key,
                    "form_key": form_key,
                    "text": text,
                    "text_len": len(text),
                    "expected_gcs_key": gcs_key,
                }
            )

    print(f"[missing] {len(missing_rows)} expected audio files absent from GCS")
    by_lang: dict[str, int] = defaultdict(int)
    for row in missing_rows:
        by_lang[row["language"]] += 1
    for lang, count in sorted(by_lang.items()):
        print(f"  [{lang}] {count} missing")

    with open(missing_csv, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "language",
                "verb_id",
                "voice",
                "form_key",
                "text",
                "text_len",
                "expected_gcs_key",
            ],
        )
        writer.writeheader()
        writer.writerows(missing_rows)

    print(f"Wrote {len(missing_rows)} missing rows to {missing_csv}")


if __name__ == "__main__":
    main()
