import re
import sys
from pathlib import Path

# Variables that board.html must expose to the Jinja2 template context.
# Each is checked as a Jinja2 expression: {{ var }} or {{ var | filter }}.
REQUIRED_VARS = [
    "title",
    "language",
    "sections_meta",
    "sections_conj",
    "examples",
]

template = Path("app/templates/board.html").read_text()

missing = []
for var in REQUIRED_VARS:
    # Match {{ var }} or {{ var | somefilter }} -- spaces optional around braces
    if not re.search(r"\{\{-?\s*" + re.escape(var) + r"[\s|}]", template):
        missing.append(var)

if missing:
    print("Missing template variables:", ", ".join(missing))
    sys.exit(1)
