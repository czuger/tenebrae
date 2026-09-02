"""Puts the repository on `sys.path`: `tenebrae` is not an installed package.

This file makes it possible to run the whole suite from the root - `python3 -m pytest` - and to
import the code the way it imports itself: `from tenebrae.engine.hexagon import Hex`, `from
tenebrae.application.app import create_app`. Never a relative import, and never a bare module
name: only the absolute path from the root.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
