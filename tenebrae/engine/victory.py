"""The end of a game: a side whose troops have all been annihilated has lost.

The booklet (`tenebrae/game_box/ave_tenebrae_regles_en.md`, "Object of the game"): "To crush the
opponent by annihilating their troops; or else to fulfil the scenario's victory conditions." The
second half is out of reach - the conditions differ from scenario to scenario, several of them
count ground held or a capital taken, and none is transcribed - so what is held here is the first,
which every scenario shares: a side with no unit left on the board has been crushed.

**Troops, not pieces.** A marker left on the map by a spell is neutral and fights nobody, and a
counter carrying no printed value is not a unit at all (`Piece.is_a_unit`): a side can be
annihilated with its markers still lying about.

Nothing here decides that a game is over - it counts. A board cleared before a set-up is laid out
carries no unit of either side, which is an empty table and not a victory; it is the caller, which
knows whether a game is being played at all, that reads these counts
(`tenebrae/application/current_game.py`).
"""

from collections.abc import Iterable

from tenebrae.engine.board import Board


def troops_of(board: Board, side: str) -> list[str]:
    """Lists the squares where a side still has a unit.

    Args:
        board: The board.
        side: `"alliance"`, `"tenebres"` or `"neutre"`.

    Returns:
        The "q,r,s" keys of its units; markers and unreadable counters are not in it.
    """
    placed = board.pieces
    return sorted(key for key in board.squares_held_by(side) if placed[key].is_a_unit)


def annihilated_sides(board: Board, sides: Iterable[str]) -> list[str]:
    """Names, among the sides given, those with no unit left on the board.

    Args:
        board: The board.
        sides: The sides the set-up fields, in player order.

    Returns:
        Those of them that have been wiped out, in the order given; empty while each still has a
        unit standing.
    """
    return [side for side in sides if not troops_of(board, side)]
