"""The game log: phase changes, combats declared, units out of range, results.

It is written in two places at once, through one logger: `logs/battle_log.log` at the root of the
repository - a rotating file of a thousand lines, kept in three archives behind it - and a bounded
in-memory queue, which the browser turns into a column under the unit card. The lines the routes
write are English; what the player reads in them (phase names, combat sentences) is French.

Configured once, at import: the logger is a module global, like the game state in `app.py`.
"""

import logging

from tenebrae.application.config import ROOT
from tenebrae.application.in_memory_log import InMemoryLog
from tenebrae.application.rotating_log import RotatingLog

LOG_PATH = ROOT / "logs" / "battle_log.log"

# `battle_log.log` plus `.1` to `.3`: at most 4,000 lines of game on disk, the oldest archive erased
# beyond that.
LINES_PER_FILE = 1000
LOGS_KEPT = 3

# What the browser's column shows: the last lines, and no more. The file remains the archive.
LINES_KEPT = 60

LOG = logging.getLogger("tenebrae.log")
LOG_MEMORY = InMemoryLog(LINES_KEPT)
if not LOG.handlers:
    _trace = RotatingLog(LOG_PATH, LINES_PER_FILE, LOGS_KEPT)
    _trace.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    LOG.addHandler(_trace)
    LOG.addHandler(LOG_MEMORY)
    LOG.setLevel(logging.INFO)


def log_lines() -> list[dict[str, str]]:
    """Reads the log as the page shows it.

    Returns:
        A copy of the last lines, oldest first, each `{"time", "text"}`. A copy because the queue
        goes on turning while the message travels.
    """
    return list(LOG_MEMORY.lines)
