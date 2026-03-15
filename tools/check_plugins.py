import sys
from pathlib import Path

# ensure repo root on PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core.languages.en.plugin  # noqa: F401
import core.languages.he.plugin  # noqa: F401
import core.languages.ru.plugin  # noqa: F401

from core.registry import all_plugins

EXPECTED_LANGUAGES = {"en", "ru", "he"}


def main() -> None:
    actual_languages = set(all_plugins().keys())

    missing = EXPECTED_LANGUAGES - actual_languages
    if missing:
        raise RuntimeError(f"Missing plugins: {sorted(missing)}")

    print("Plugins OK")


if __name__ == "__main__":
    main()
