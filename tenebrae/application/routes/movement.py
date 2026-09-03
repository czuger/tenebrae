"""Movement: the squares a unit can reach, and moving it there.

The **server's board** says which piece stands where and which opponents oppose their zones of
control to it; the browser never decides the legality of a move. Movement is open only to the
active side during its movement phase.
"""

from typing import Optional

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from tenebrae.application.current_game import BOARD, TURN, save_the_game
from tenebrae.application.routes.authorization import active_side_required
from tenebrae.application.routes.reading import read_a_hexagon, read_a_piece
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import Piece

blueprint = Blueprint("movement", __name__)


@blueprint.route("/moves")
def moves() -> ResponseReturnValue:
    """Lists the hexagons a unit placed at (q, r, s) can reach.

    The `piece` parameter only serves to query an empty square.

    Returns:
        The move's description and the reachable `hexagons`.
    """
    origin = read_a_hexagon(request.args)
    piece = read_a_piece(request.args.get("piece"))
    return describe_a_move(origin, piece) | {
        "hexagons": [hexagon.to_dict() for hexagon in BOARD.moves(origin, piece)],
    }


@blueprint.route("/move", methods=["POST"])
@active_side_required
def move() -> ResponseReturnValue:
    """Moves a unit from `origin` to `destination`, if the rules allow it.

    The server recomputes the reach and applies the move to its board. Outside the active side's
    movement phase, the move is refused without the board budging.

    Returns:
        The move's description, `allowed`, the destination and the tilt the board drew.
    """
    demand = request.get_json(silent=True) or {}
    origin = read_a_hexagon(demand.get("origin") or {})
    destination = read_a_hexagon(demand.get("destination") or {})
    piece = read_a_piece(demand.get("piece"))
    described = describe_a_move(origin, piece)
    placed = BOARD.piece_on(origin)
    out_of_phase = placed is not None and not TURN.allows_movement(placed.side)
    allowed = not out_of_phase and BOARD.move(origin, destination, piece)
    if allowed:
        save_the_game()
    return described | {"allowed": allowed, "destination": destination.to_dict(),
                        "tilt": BOARD.tilt_on(destination)}


def describe_a_move(origin: Hex, piece: Optional[Piece]) -> dict[str, object]:
    """Serialises what the server knows of the departing unit.

    Args:
        origin: The departure square.
        piece: The piece to assume if the square is empty.

    Returns:
        `origin`, `piece`, `side` and `movement`.
    """
    placed = BOARD.piece_on(origin) or piece
    return {
        "origin": origin.to_dict(),
        "piece": placed.key if placed else None,
        "side": placed.side if placed else None,
        "movement": BOARD.movement_of(origin, piece),
    }
