"""Opening a log file that rotates: the standard handler, and the one thing it does not do.

`logging.handlers.RotatingFileHandler` sets the file aside by size and keeps a few archives behind
it, which is all these logs need. What it does not do is create the directory it writes into, and
`logs/` is not versioned: a fresh clone has none. Hence this one function, which both logs go
through - the game log (`battle_log.py`) and the engine's movement trace (`movement_log.py`).
"""

import logging
import logging.handlers
from pathlib import Path

# 50 KB per file and three archives behind it: 200 KB on disk, the oldest erased beyond that.
MAX_BYTES = 50 * 1024
FILES_KEPT = 3


def open_the_log(path: Path, max_bytes: int = MAX_BYTES,
                 files_kept: int = FILES_KEPT) -> logging.handlers.RotatingFileHandler:
    """Opens a rotating log file, creating its directory if it is missing.

    Args:
        path: The current file; the archives are `path.1`, `path.2`, ...
        max_bytes: The size beyond which the file is set aside.
        files_kept: How many archives are kept behind it.

    Returns:
        The handler, formatted as the logs are read: the time, then the line.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=max_bytes, backupCount=files_kept, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    return handler
