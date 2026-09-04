"""Two players, two sides: taking a seat at the table, and giving it up.

The table itself is the engine's (`tenebrae/engine/models/seats.py`); it holds the "one side, one
occupant" rule. The "one player, one side" rule is here and nowhere else - the test suite seats
one player on both, straight on the register.
"""

from flask import Blueprint, abort, request
from flask.typing import ResponseReturnValue

from tenebrae.application import current_game
from tenebrae.application.current_game import SEATS, save_the_game
from tenebrae.application.logs.battle_log import LOG
from tenebrae.application.players import logged_in_player, the_table
from tenebrae.application.routes.authorization import login_required

blueprint = Blueprint("seats", __name__)


@blueprint.route("/game/seat", methods=["POST"])
@login_required
def take_a_seat() -> ResponseReturnValue:
    """Seats the requester at a free side - body `{"side": "alliance"}`.

    Two rules, in two places: an occupied side is not taken over, and the register holds that one;
    a player holds only one side, and that is here and nowhere else.

    Returns:
        `seated`, the side and the table; 400 for an unknown side, 409 for a refused seat.
    """
    side = (request.get_json(silent=True) or {}).get("side")
    if side not in current_game.SCENARIO.sides:
        abort(400, "unknown side; expected one of "
              f"{', '.join(current_game.SCENARIO.sides)}")

    player = logged_in_player()["discord_id"]
    if SEATS.holds(player, side):
        return {"seated": True, "side": side} | the_table()
    if SEATS.sides_of(player):
        return {"seated": False, "message": "Vous tenez déjà un camp."} | the_table(), 409
    if not SEATS.is_free(side):
        return {"seated": False, "message": "Ce camp est déjà tenu."} | the_table(), 409

    SEATS.seat(side, player)
    LOG.info("Seat taken: %s by %s", side, logged_in_player()["nickname"])
    save_the_game()
    return {"seated": True, "side": side} | the_table()


@blueprint.route("/game/seat/leave", methods=["POST"])
@login_required
def leave_the_seat() -> ResponseReturnValue:
    """Gives up the requester's seat: the side becomes free again, the game stays where it is.

    Returns:
        `{"seated": False}` and the table.
    """
    player = logged_in_player()["discord_id"]
    for side in SEATS.sides_of(player):
        SEATS.free(side)
    save_the_game()
    return {"seated": False} | the_table()
