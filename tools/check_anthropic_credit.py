"""Check that the Anthropic API key works and the account still has credit.

Sends one 1-token request (a fraction of a cent) and reports the result. Exit codes:
0 = OK, 2 = out of credit, 3 = key rejected, 1 = anything else (network, overload, rate limit).

    python -m tools.check_anthropic_credit            # key from .env / environment
    python -m tools.check_anthropic_credit --secret   # key from Secret Manager (what stage and prod use)

The key itself is never printed, only its length and prefix.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

import anthropic
from dotenv import load_dotenv

_SECRET_NAME = "verbboard-anthropic-api-key"
_MODEL = "claude-haiku-4-5-20251001"


def _key_from_secret_manager(project: str) -> str:
    result = subprocess.run(
        ["gcloud", "secrets", "versions", "access", "latest", f"--secret={_SECRET_NAME}", f"--project={project}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        sys.exit(f"Could not read secret {_SECRET_NAME}: {result.stderr.strip() or 'gcloud failed'}")
    return result.stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--secret", action="store_true", help="read the key from Secret Manager instead of .env")
    parser.add_argument("--project", default=os.getenv("GOOGLE_CLOUD_PROJECT", ""), help="GCP project for --secret")
    args = parser.parse_args()

    load_dotenv(override=True)
    if args.secret:
        if not args.project:
            sys.exit("--secret needs --project or GOOGLE_CLOUD_PROJECT")
        api_key, source = _key_from_secret_manager(args.project), "Secret Manager"
    else:
        api_key, source = os.getenv("ANTHROPIC_API_KEY", ""), ".env / environment"
    if not api_key:
        print(f"FAIL: no Anthropic key found in {source}")
        return 3

    print(f"Key source: {source} (length {len(api_key)}, prefix {api_key[:7]}...)")
    try:
        anthropic.Anthropic(api_key=api_key).messages.create(
            model=_MODEL, max_tokens=1, messages=[{"role": "user", "content": "hi"}]
        )
    except anthropic.AuthenticationError:
        print("FAIL: the key was rejected (invalid or revoked)")
        return 3
    except anthropic.BadRequestError as error:
        if "credit balance" in str(error).lower():
            print("OUT OF CREDIT: add credit at Plans & Billing in the Anthropic console")
            return 2
        print(f"FAIL: bad request: {error}")
        return 1
    except anthropic.APIError as error:
        print(f"FAIL: {type(error).__name__}: {error}")
        return 1
    print("OK: the key works and the account has credit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
