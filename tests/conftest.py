"""Make the project root and backend/ importable for the tests."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for folder in (ROOT, ROOT / "backend"):
    sys.path.insert(0, str(folder))
