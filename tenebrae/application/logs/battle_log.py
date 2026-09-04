"""The game log: phase changes, combats declared, units out of range, results.

It is written in two places at once, through one logger: `logs/battle_log.log` at the root of the
repository - a rotating file of 50 KB, kept in three archives behind it - and a bounded in-memory
queue, which the browser turns into a column under the unit card. The lines the routes write are
English; what the player reads in them (phase names, combat sentences) is French.

The engine's movement trace does **not** come here: it has a file of its own, `movement_log.py`.

Configured once, at import: the logger is a module global, like the game state in
`current_game.py`.
"""

import logging

from tenebrae.application.config import ROOT
from tenebrae.application.logs.in_memory_log import InMemoryLog
from tenebrae.application.logs.rotating_log import open_the_log

LOG_PATH = ROOT / "logs" / "battle_log.log"

# What the browser's column shows: the last lines, and no more. The file remains the archive.
LINES_KEPT = 60

LOG = logging.getLogger("tenebrae.log")
LOG_MEMORY = InMemoryLog(LINES_KEPT)
if not LOG.handlers:
    LOG.addHandler(open_the_log(LOG_PATH))
    LOG.addHandler(LOG_MEMORY)
    LOG.setLevel(logging.DEBUG)


def log_lines() -> list[dict[str, str]]:
    """Reads the log as the page shows it.

    Returns:
        A copy of the last lines, oldest first, each `{"time", "text"}`. A copy because the queue
        goes on turning while the message travels.
    """
    return list(LOG_MEMORY.lines)
