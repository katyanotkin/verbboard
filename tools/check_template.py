from pathlib import Path
import sys

required = {
    "{{title}}",
    "{{language}}",
    "{{voice}}",
    "{{sections}}",
    "{{examples}}",
}

template = Path("app/templates/board.html").read_text()

missing = [p for p in required if p not in template]

if missing:
    print("Missing template placeholders:", ", ".join(missing))
    sys.exit(1)
