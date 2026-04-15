import sys
import requests


def check(url: str, name: str) -> None:
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            print(f"[FAIL] {name}: {response.status_code}")
            sys.exit(1)
        print(f"[OK]   {name}")
    except Exception as exc:
        print(f"[ERROR] {name}: {exc}")
        sys.exit(1)


def main(base_url: str) -> None:
    print(f"\nSmoke testing: {base_url}\n")

    check(f"{base_url}/health", "health")
    check(f"{base_url}/", "home")

    # pick a known verb that must exist
    check(f"{base_url}/learn?language=en&verb_id=en_go", "learn en_go")
    check(f"{base_url}/learn?language=ru&verb_id=ru_delat", "learn ru_delat")

    print("\nAll smoke tests passed\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python smoke.py <base_url>")
        sys.exit(1)

    main(sys.argv[1])
