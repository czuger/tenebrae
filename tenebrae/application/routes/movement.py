"""Movement: the squares a unit can reach, and moving it there.

The **server's board** says which piece stands where and which opponents oppose their zones of
control to it; the browser never decides the legality of a move. Movement is open only to the
active side during its movement phase.

Nor does the browser keep the count of what a unit has already walked: the booklet allots each unit
a capital of movement points for the phase, and the server holds it
(`tenebrae/engine/movement_register.py`). A unit is offered the squares **what is left** of its
allowance reaches, and a click asking for more is refused here, whatever the page shows.
"""

from typing import Optional

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from tenebrae.application.current_game import ALLOWANCES, BOARD, TURN, save_the_game
from tenebrae.application.logs.battle_log import LOG
from tenebrae.application.routes.authorization import (active_side_required,
                                                       while_the_game_lasts)
from tenebrae.application.routes.reading import read_a_hexagon, read_a_piece
from tenebrae.engine import movement
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import Piece

blueprint = Blueprint("movement", __name__)

# The refusals, French like everything the player reads. The first goes to the log, as the combat
# register's do: the counter is already greyed out, and the line says why it refuses the click.
EXHAUSTED_MESSAGE = "Cette unité a épuisé ses points de mouvement pour cette phase."
ILLEGAL_MESSAGE = "Cette unité ne peut pas atteindre cette case."

# What the browser is told, one message per refusal the engine names.
MESSAGES = {movement.EXHAUSTED: EXHAUSTED_MESSAGE, movement.ILLEGAL: ILLEGAL_MESSAGE}


@blueprint.route("/moves")
def moves() -> ResponseReturnValue:
    """Lists the hexagons a unit placed at (q, r, s) can reach with what it has left.

    The `piece` parameter only serves to query an empty square.

    A unit that has spent its whole allowance is offered nothing, and the refusal goes to the log -
    the page greys the counter out beforehand, but a click that lands on it must still say why.

    Returns:
        The move's description, the reachable `hexagons`, and a French `message` when the unit has
        nothing left to spend.
    """
    origin = read_a_hexagon(request.args)
    piece = read_a_piece(request.args.get("piece"))
    described = describe_a_move(origin, piece)
    # The exact fraction, not the float `described` carries for the browser: a third of a point
    # walked on a road must not come back as 0.333.
    left = movement.points_left(BOARD, ALLOWANCES, origin, piece)
    if left <= 0:
        LOG.info(EXHAUSTED_MESSAGE)
        return described | {"hexagons": [], "message": EXHAUSTED_MESSAGE}
    reachable = BOARD.moves(origin, piece, budget=left)
    return described | {"hexagons": [hexagon.to_dict() for hexagon in reachable],
                        "message": None}


@blueprint.route("/move", methods=["POST"])
@active_side_required
@while_the_game_lasts
def move() -> ResponseReturnValue:
    """Moves a unit from `origin` to `destination`, if the rules allow it.

    The server recomputes the reach **on what the unit has left** and applies the move to its
    board, charging the trip to the unit's allowance. Outside the active side's movement phase, and
    for a unit that has already spent its points, the move is refused without the board budging.

    Returns:
        The move's description, `allowed`, the destination, the tilt the board drew, what the trip
        `cost`, what is `remaining` and a French `message` when refused.
    """
    demand = request.get_json(silent=True) or {}
    origin = read_a_hexagon(demand.get("origin") or {})
    destination = read_a_hexagon(demand.get("destination") or {})
    piece = read_a_piece(demand.get("piece"))
    described = describe_a_move(origin, piece)
    placed = BOARD.piece_on(origin)
    if placed is not None and not TURN.allows_movement(placed.side):
        return described | {"allowed": False, "destination": destination.to_dict(),
                            "tilt": None, "cost": None, "message": None}

    outcome = movement.move(BOARD, ALLOWANCES, origin, destination, piece)
    message = MESSAGES.get(outcome.refusal or "")
    # Only the exhausted allowance is worth a line: a destination out of reach is an ordinary
    # miss-click, and the column would fill with it.
    if outcome.refusal == movement.EXHAUSTED:
        LOG.info(EXHAUSTED_MESSAGE)
    if outcome.allowed:
        save_the_game()
    return described | {"allowed": outcome.allowed, "destination": destination.to_dict(),
                        "tilt": BOARD.tilt_on(destination),
                        "cost": None if outcome.cost is None else float(outcome.cost),
                        "remaining": float(outcome.remaining),
                        "exhausted": outcome.remaining <= 0,
                        "message": message}


def describe_a_move(origin: Hex, piece: Optional[Piece]) -> dict[str, object]:
    """Serialises what the server knows of the departing unit.

    `movement` is what the counter is printed with, `remaining` what this phase has left of it -
    the two are equal until the unit moves.

    Args:
        origin: The departure square.
        piece: The piece to assume if the square is empty.

    Returns:
        `origin`, `piece`, `side`, `movement`, `remaining` and `exhausted`.
    """
    placed = BOARD.piece_on(origin) or piece
    left = movement.points_left(BOARD, ALLOWANCES, origin, piece)
    return {
        "origin": origin.to_dict(),
        "piece": placed.key if placed else None,
        "side": placed.side if placed else None,
        "movement": BOARD.movement_of(origin, piece),
        "remaining": float(left),
        "exhausted": left <= 0,
    }
