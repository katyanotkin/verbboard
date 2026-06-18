"""
Audit Hebrew verb data for nikud (vowel diacritics) coverage.

Checks each verb's `forms` field -- after Option A migration, forms carry full
nikud for both display and TTS. tts_forms is the legacy field (pre-migration).

Nikud = Unicode U+05B0..U+05C7 (Hebrew points, vowels, dagesh, etc.)

Run from project root (needs GCP auth / local Firestore):

    python -m tools.check_nikud
    python -m tools.check_nikud --verbose
    python -m tools.check_nikud --missing   # only verbs missing nikud in forms
"""

from __future__ import annotations

import argparse
import sys

import core.languages.he.plugin  # noqa: F401 -- registers HE plugin
from core.verb_loader import load_entries_for_language

_NIKUD_RANGE = range(0x05B0, 0x05C8)


def has_nikud(text: str) -> bool:
    return any(ord(ch) in _NIKUD_RANGE for ch in text)


def _audit_forms(d: dict | None) -> tuple[int, int, list[str]]:
    """Return (with_nikud, without_nikud, slots_missing_nikud) for a nested forms dict."""
    if not d:
        return 0, 0, []
    with_n = without_n = 0
    missing: list[str] = []
    for tense, subforms in d.items():
        if isinstance(subforms, dict):
            for slot, val in subforms.items():
                if isinstance(val, str) and val.strip():
                    if has_nikud(val):
                        with_n += 1
                    else:
                        without_n += 1
                        missing.append(f"{tense}.{slot}={val!r}")
        elif isinstance(subforms, str) and subforms.strip():
            if has_nikud(subforms):
                with_n += 1
            else:
                without_n += 1
                missing.append(f"{tense}={subforms!r}")
    return with_n, without_n, missing


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Hebrew nikud coverage in forms field")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show per-verb details")
    parser.add_argument("--missing", "-m", action="store_true", help="Only show verbs missing nikud")
    args = parser.parse_args()

    entries = load_entries_for_language(language="he")
    if not entries:
        sys.exit("No Hebrew verbs loaded. Check GOOGLE_CLOUD_PROJECT / Firestore connection.")

    total = len(entries)
    forms_ok = 0
    forms_partial = 0
    forms_missing = 0
    has_legacy_tts = 0

    print(f"Loaded {total} Hebrew verbs\n")

    for entry in sorted(entries, key=lambda e: e.rank):
        forms = entry.forms or {}
        tts = entry.tts_forms  # legacy field

        with_n, without_n, missing_slots = _audit_forms(forms)

        if without_n == 0 and with_n > 0:
            forms_ok += 1
            status = "OK"
        elif with_n > 0:
            forms_partial += 1
            status = f"PARTIAL {with_n}n/{without_n}plain"
        else:
            forms_missing += 1
            status = "MISSING"

        if tts:
            has_legacy_tts += 1

        show = args.verbose or (args.missing and status != "OK")
        if show:
            lemma = entry.display_lemma or entry.lemma
            legacy = " [legacy tts_forms still set]" if tts else ""
            print(f"  [{entry.rank:3d}] {entry.id:<28} {str(lemma):<15} forms:{status}{legacy}")
            if args.verbose and missing_slots:
                for s in missing_slots[:6]:
                    print(f"           plain: {s}")

    print()
    print("=" * 58)
    print(f"Total Hebrew verbs:               {total}")
    print(f"forms all nikud (OK):             {forms_ok} / {total}")
    print(f"forms partial nikud:              {forms_partial}")
    print(f"forms no nikud (need regen):      {forms_missing}")
    print(f"Legacy tts_forms still present:   {has_legacy_tts}")
    print()
    if forms_missing + forms_partial:
        need = forms_missing + forms_partial
        print(f"ACTION: {need} verbs need ⟳ Forms in admin Live Verbs panel.")
        print("        After regen, run: python -m tools.cache_audio --language he")
    else:
        print("All verbs have nikud in forms.")
        if has_legacy_tts:
            print(f"Note: {has_legacy_tts} verbs still have legacy tts_forms (cleared on next regen).")


if __name__ == "__main__":
    main()
