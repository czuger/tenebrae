"""Playing a move: the board judges the trip, the register judges the allowance.

The booklet ("Movement") gives each unit a capital of movement points for the phase - "each player
moves as many units as they wish, within the limit of the movement points allotted to each unit" -
and the two halves of that sentence live in two objects: `tenebrae.engine.board.Board` knows what
the terrain, the friends and the zones of control allow, `tenebrae.engine.movement_register`
knows what the unit has already spent. Neither can refuse a move on its own, and this module is
where they meet.

Everything that moves a unit **as a player would** comes through `move`: the server's route and
the artificial opponent both. `Board.move` stays what it was - a trip weighed against the map -
and is what a fall-back or a rule questioned by hand uses, where no allowance is spent.

The refusals are named in English, like the rest of the engine; the French sentence the player
reads is the application's (`tenebrae/application/routes/movement.py`).
"""

from collections.abc import Iterable
from fractions import Fraction
from typing import Optional

from tenebrae.engine.board import Board
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.movement_register import MovementRegister
from tenebrae.engine.piece import Piece

# Why a move was refused. `EXHAUSTED` is this module's own - the unit has nothing left to spend;
# `ILLEGAL` is the board's answer, whatever its reason: terrain, an occupied square, a zone of
# control, or simply too far for what is left.
EXHAUSTED, ILLEGAL = "exhausted", "illegal"


class MoveOutcome:
    """What playing a move gave: whether it was played, what it cost, and what is left.

    `cost` is `None` on a refusal, `remaining` always tells what the unit may still spend - the
    allowance untouched where the move was refused.
    """

    __slots__ = ("allowed", "cost", "remaining", "refusal")

    allowed: bool
    cost: Optional[Fraction]
    remaining: Fraction
    refusal: Optional[str]

    def __init__(self, allowed: bool, cost: Optional[Fraction], remaining: Fraction,
                 refusal: Optional[str] = None) -> None:
        """Keeps the result of a move.

        Args:
            allowed: Whether the board was changed.
            cost: The points the trip cost, `None` where none was made.
            remaining: What the unit may still spend this phase.
            refusal: `EXHAUSTED`, `ILLEGAL`, or `None` where the move was played.
        """
        self.allowed = allowed
        self.cost = cost
        self.remaining = remaining
        self.refusal = refusal

    def __repr__(self) -> str:
        """Whether it was played, its cost and what is left."""
        if not self.allowed:
            return f"MoveOutcome(refused: {self.refusal}, {self.remaining} left)"
        return f"MoveOutcome(played at {self.cost}, {self.remaining} left)"


def points_left(board: Board, register: MovementRegister, origin: Hex,
                piece: Optional[Piece] = None) -> Fraction:
    """Reads what the unit standing on a square may still spend this phase.

    Args:
        board: The board, read for the counter's printed allowance.
        register: What the phase has already consumed.
        origin: The square the unit stands on.
        piece: The piece to assume if the square is empty.

    Returns:
        The points left; the whole allowance for a unit that has not moved yet.
    """
    return register.points_left(origin.key, board.movement_of(origin, piece))


def is_exhausted(board: Board, register: MovementRegister, origin: Hex,
                 piece: Optional[Piece] = None) -> bool:
    """Says whether the unit on a square has spent its whole allowance this phase.

    Args:
        board: The board.
        register: What the phase has already consumed.
        origin: The square the unit stands on.
        piece: The piece to assume if the square is empty.

    Returns:
        True where nothing is left to spend.
    """
    return points_left(board, register, origin, piece) <= 0


def move(board: Board, register: MovementRegister, origin: Hex, destination: Hex,
         piece: Optional[Piece] = None) -> MoveOutcome:
    """Plays a move against both the map and what the unit has already spent.

    The allowance is checked first and the trip is then weighed **on what is left of it**, not on
    the counter's printed movement: a unit with one point left is offered the squares one point
    reaches, and a second click asking for more is refused by the board like any other move too far.

    Nothing is charged where nothing moved: an empty origin square is the way the rules are
    questioned by hand (`Board.move`), and no allowance is spent on a unit that is not there.

    Args:
        board: The board, modified in place.
        register: The phase's allowances, charged when the move is played.
        origin: The departure square.
        destination: The arrival square.
        piece: The piece to assume if the origin is empty.

    Returns:
        The outcome; `refusal` says why where the move was not played.
    """
    budget = board.movement_of(origin, piece)
    left = register.points_left(origin.key, budget)
    if left <= 0:
        return MoveOutcome(False, None, left, EXHAUSTED)

    cost = board.cost_of(origin, destination, piece, left)
    if cost is None:
        return MoveOutcome(False, None, left, ILLEGAL)

    placed = board.piece_on(origin)
    board.move(origin, destination, piece, left)
    if placed is None:
        return MoveOutcome(True, cost, left)
    return MoveOutcome(True, cost, register.spend(origin.key, destination.key, cost, budget))


def exhausted_squares(board: Board, register: MovementRegister,
                      sides: Optional[Iterable[str]] = None) -> list[str]:
    """Collects the squares whose unit can no longer move this phase.

    What the browser greys out: a counter that will refuse the click is shown as refusing it
    beforehand, exactly as one that has already fought is (`unavailable_units`).

    Args:
        board: The board.
        register: What the phase has already consumed.
        sides: The sides to look at; every placed piece when omitted.

    Returns:
        The "q,r,s" keys, sorted.
    """
    wanted = None if sides is None else set(sides)
    return sorted(key for key, piece in board.pieces.items()
                  if (wanted is None or piece.side in wanted)
                  and register.points_left(key, piece.movement_points) <= 0)
