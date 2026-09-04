"""The engine's movement trace on disk: `logs/movement.log`, and nothing else in it.

`Board.moves` writes the whole of a computation to its module logger - the piece and its budget,
what the walk was told to avoid, and every square it reached with the reason it is not offered (see
`tenebrae/engine/README.md`). The engine imports nothing from the application and therefore knows
no path: it is here that this logger is given its file, as `battle_log.py` gives the game log its
own.

**Two logs, two files.** This one is read when a move looks wrong; the other is the game told to
the player, and shows in the browser's column. A movement recomputed at every click would drown it.

Wired by `create_app`, beside persistence and authentication, and opened at DEBUG - the level these
lines are written at, and the only one.
"""

import logging

from tenebrae.application.config import ROOT
from tenebrae.application.logs.rotating_log import open_the_log
from tenebrae.engine.board import LOG as MOVEMENT_LOG

MOVEMENT_LOG_PATH = ROOT / "logs" / "movement.log"


def wire_the_movement_log() -> None:
    """Gives the engine's movement logger its file, once.

    Called again - one application per test - it does nothing: a second handler would write every
    line twice.
    """
    if MOVEMENT_LOG.handlers:
        return
    MOVEMENT_LOG.addHandler(open_the_log(MOVEMENT_LOG_PATH))
    MOVEMENT_LOG.setLevel(logging.DEBUG)
