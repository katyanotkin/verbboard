import subprocess
import sys
from pathlib import Path

root = Path("runtime/data")

for lang_dir in sorted(root.iterdir()):
    lex = lang_dir / "lexicon.json"
    if not lex.exists():
        continue

    print(f"Checking {lex}")
    result = subprocess.run(
        [sys.executable, "tools/check_lexicon.py", str(lex)],
    )

    if result.returncode != 0:
        sys.exit(result.returncode)
