"""The turn's phases: where one stands, and stepping to the next.

Movement then combat, for one side then the other, round and round; magic is stepped over by
itself (`tenebrae/engine/phase.py`). Stepping empties both phase registers - what has already
fought, and what has already moved - and hands play to the AI if the next phase is its.
"""

from flask import Blueprint
from flask.typing import ResponseReturnValue

from tenebrae.application.current_game import (ALLOWANCES, REGISTER, TURN, current_phase,
                                               let_the_ai_play, save_the_game)
from tenebrae.application.logs.battle_log import LOG
from tenebrae.application.routes.authorization import (active_side_required,
                                                       while_the_game_lasts)

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
@while_the_game_lasts
def next_phase() -> ResponseReturnValue:
    """Steps to the next phase; magic is stepped over by itself, both registers emptied.

    The movement allowances go back to full here and nowhere else: the booklet allots the points
    "during their active phase", so a unit gets its capital back when the phase turns, and a game
    saved mid-phase reopens on what was left of it.

    Returns:
        The new phase.
    """
    TURN.advance()
    REGISTER.reset()
    ALLOWANCES.reset()
    LOG.info("Phase: %s (turn %s)", TURN.label, TURN.number)
    save_the_game()
    let_the_ai_play()
    return current_phase()
