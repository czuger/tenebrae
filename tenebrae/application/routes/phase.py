"""The turn's phases: where one stands, and stepping to the next.

Movement then combat, for one side then the other, round and round; magic is stepped over by
itself (`tenebrae/engine/phase.py`). Stepping empties the combat register, and hands play to the
AI if the next phase is its.
"""

from flask import Blueprint
from flask.typing import ResponseReturnValue

from tenebrae.application.current_game import (REGISTER, TURN, current_phase, let_the_ai_play,
                                               save_the_game)
from tenebrae.application.logs.battle_log import LOG
from tenebrae.application.routes.authorization import active_side_required

blueprint = Blueprint("phase", __name__)


@blueprint.route("/phase")
def phase() -> ResponseReturnValue:
    """Serves the current phase, for the browser's label and blocks.

    Returns:
        The phase as `current_phase` serialises it.
    """
    return current_phase()


@blueprint.route("/phase/next", methods=["POST"])
@active_side_required
def next_phase() -> ResponseReturnValue:
    """Steps to the next phase; magic is stepped over by itself, the combat register emptied.

    Returns:
        The new phase.
    """
    TURN.advance()
    REGISTER.reset()
    LOG.info("Phase: %s (turn %s)", TURN.label, TURN.number)
    save_the_game()
    let_the_ai_play()
    return current_phase()
