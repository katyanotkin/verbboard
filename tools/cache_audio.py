"""
Pre-cache verb audio to GCS for a given language.

Pass --bucket once for a single target or multiple times to write to several
buckets with a single TTS call per file (stage + prod in one run).

Run from project root (needs GCP auth):

    python -m tools.cache_audio --language he \\
        --bucket verbboard-audio-stage --bucket verbboard-audio-prod

    GOOGLE_CLOUD_PROJECT=knotmem26 AUDIO_BUCKET=verbboard-audio-prod \\
        python -m tools.cache_audio --language all

    python -m tools.cache_audio --language ru --voice female --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# Snapshot env vars before any core import triggers load_dotenv(override=True).
_ENV_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
_ENV_BUCKET = os.getenv("AUDIO_BUCKET", "")

# Register all language plugins before registry lookups.
import core.languages.en.plugin  # noqa: E402, F401
import core.languages.es.plugin  # noqa: E402, F401
import core.languages.he.plugin  # noqa: E402, F401
import core.languages.ru.plugin  # noqa: E402, F401
from core.audio_backend.gcs import GCSAudioBackend  # noqa: E402
from core.audio_service import build_audio_key, build_hashed_audio_key  # noqa: E402
from core.registry import get as get_plugin  # noqa: E402
from core.supported_languages import (  # noqa: E402
    supported_languages_list,
    supported_languages_with_all,
)
from core.tts import VOICES, tts_to_mp3  # noqa: E402
from core.verb_loader import load_entries_for_language  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")


def _iter_form_items(verb, language: str, voice_key: str):
    """Yield (base_form_key, text) for every audio item on the board."""
    voice_meta = VOICES[language][voice_key]
    plugin = get_plugin(language)
    board = plugin.build_board(verb, voice_key, voice_meta.label)

    for section in board.sections:
        for row in section["rows"]:
            text = str(row["text"] or "").strip()
            if text:
                yield str(row["key"]), text

    for index, example in enumerate(board.verb.examples, start=1):
        text = example.dst.strip()
        if text:
            yield f"example_{index}", text


async def _generate_and_upload(
    backends: list[GCSAudioBackend],
    missing_indices: list[int],
    text: str,
    gcs_key: str,
    voice_edge_id: str,
) -> None:
    """Call TTS once, upload resulting bytes to every backend in missing_indices."""
    with TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "audio.mp3"
        await tts_to_mp3(text, out_path, voice_edge_id)
        audio_bytes = out_path.read_bytes()

    await asyncio.gather(*[asyncio.to_thread(backends[i].write_bytes, gcs_key, audio_bytes) for i in missing_indices])


async def _cache_language(
    language: str,
    voices: list[str],
    backends: list[GCSAudioBackend],
    dry_run: bool,
) -> dict[str, int]:
    print(f"\n[{language}] Loading verbs from Firestore...")
    entries = load_entries_for_language(language=language)
    print(f"[{language}] {len(entries)} verbs")

    # Bulk-list each backend once -- avoids N exists() calls per file.
    existing_per_backend: list[set[str]] = []
    for backend in backends:
        prefix = f"audio/{language}/"
        print(f"[{language}] [{backend.bucket.name}] listing GCS keys under {prefix}...")
        existing: set[str] = {blob.name for blob in backend.bucket.list_blobs(prefix=prefix)}
        print(f"[{language}] [{backend.bucket.name}] {len(existing)} cached")
        existing_per_backend.append(existing)

    counts: dict[str, int] = {"total": 0, "cached": 0, "generated": 0, "failed": 0}

    for verb in entries:
        for voice_key in voices:
            voice_meta = VOICES[language][voice_key]
            # (form_key, text, edge_id, gcs_key, indices of backends missing this key)
            pending: list[tuple[str, str, str, str, list[int]]] = []

            for base_key, text in _iter_form_items(verb, language, voice_key):
                form_key = build_hashed_audio_key(base_key, text)
                gcs_key = build_audio_key(language, verb.id, voice_key, form_key)
                counts["total"] += 1

                missing = [i for i, existing in enumerate(existing_per_backend) if gcs_key not in existing]

                if not missing:
                    counts["cached"] += 1
                else:
                    pending.append((form_key, text, voice_meta.edge_id, gcs_key, missing))

            if not pending:
                continue

            if dry_run:
                targets = ", ".join(backends[i].bucket.name for i in pending[0][4])
                print(f"  DRY-RUN {verb.id} [{voice_key}]: would generate {len(pending)} to [{targets}]")
                counts["generated"] += len(pending)
                continue

            tasks = [
                _generate_and_upload(backends, missing, text, gcs_key, edge_id)
                for _, text, edge_id, gcs_key, missing in pending
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    form_key = pending[i][0]
                    print(f"  ERROR {verb.id}/{voice_key}/{form_key}: {result}")
                    counts["failed"] += 1
                else:
                    counts["generated"] += 1

            ok = sum(1 for r in results if not isinstance(r, Exception))
            if ok:
                print(f"  {verb.id} [{voice_key}]: +{ok} generated")

    return counts


async def _run(
    languages: list[str],
    voices_filter: str,
    backends: list[GCSAudioBackend],
    dry_run: bool,
) -> None:
    totals: dict[str, int] = {"total": 0, "cached": 0, "generated": 0, "failed": 0}

    for language in languages:
        available = list(VOICES.get(language, {}).keys())
        if voices_filter == "all":
            voices = available
        elif voices_filter in available:
            voices = [voices_filter]
        else:
            print(f"[{language}] voice '{voices_filter}' not available, skipping")
            continue

        counts = await _cache_language(language, voices, backends, dry_run)
        for k in totals:
            totals[k] += counts[k]
        print(
            f"[{language}] total={counts['total']}  cached={counts['cached']}  "
            f"generated={counts['generated']}  failed={counts['failed']}"
        )

    bucket_names = ", ".join(b.bucket.name for b in backends)
    print(
        f"\nSUMMARY [{bucket_names}]: "
        f"total={totals['total']}  cached={totals['cached']}  "
        f"generated={totals['generated']}  failed={totals['failed']}"
    )
    if totals["failed"]:
        sys.exit(1)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-cache verb audio to GCS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python -m tools.cache_audio --language he\n"
            "  python -m tools.cache_audio --language all --voice female\n"
            "  python -m tools.cache_audio --language ru --dry-run\n"
            "  python -m tools.cache_audio --language all \\\n"
            "      --bucket verbboard-audio-stage --bucket verbboard-audio-prod\n"
        ),
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
        help="Which voice(s) to cache (default: all)",
    )
    parser.add_argument(
        "--project",
        default=_ENV_PROJECT,
        help="GCP project ID (or set GOOGLE_CLOUD_PROJECT)",
    )
    parser.add_argument(
        "--bucket",
        action="append",
        dest="buckets",
        metavar="BUCKET",
        help=("GCS bucket name; repeat for multiple buckets (default: AUDIO_BUCKET env var)"),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be generated without making TTS calls",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if not args.project:
        sys.exit("ERROR: --project or GOOGLE_CLOUD_PROJECT is required")

    buckets = args.buckets or ([_ENV_BUCKET] if _ENV_BUCKET else [])
    if not buckets:
        sys.exit("ERROR: --bucket or AUDIO_BUCKET is required")

    languages = supported_languages_list() if args.language == "all" else [args.language]
    backends = [GCSAudioBackend(project=args.project, bucket=b) for b in buckets]
    asyncio.run(_run(languages, args.voice, backends, args.dry_run))


if __name__ == "__main__":
    main()
