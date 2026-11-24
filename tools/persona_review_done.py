"""Clear the admin "Persona review due" banner once a review is finished (issue #142).

    python -m tools.persona_review_done 2026-12-14

Writes status=done on persona_reviews/<date> (needs GCP auth). Exit 1 if that review does not exist.
"""

from __future__ import annotations

import sys

from core.persona_review_service import mark_done


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(__doc__)
        return 2
    if not mark_done(args[0]):
        print(f"No review on {args[0]}")
        return 1
    print(f"Marked {args[0]} done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
