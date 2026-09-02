"""Puts the repository and the application on `sys.path`: neither is an installed package.

This file makes it possible to run the whole suite from the root: `python3 -m pytest`.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

for path in (ROOT, ROOT / "application"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
