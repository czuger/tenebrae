"""Retreat or elimination: what becomes of a unit that combat forces to fall back.

The booklet (`tenebrae/game_box/ave_tenebrae_regles_en.md`, "Retreat or elimination of a unit"):

> A unit that finds itself unable to fall back (presence of a lake, a river or an enemy zone of
> control) is removed from play, unless it is surrounded by friendly units. In that case, it
> pushes one of those units and takes its place. This simultaneous falling back of one or more
> units must make the retreating unit fall back by seeking the least movement and by pushing back
> as few friendly units as possible.

Three rules in one sentence, and the third is a search: pushing the nearest friend may cost three
displacements where pushing another would cost one. The whole chain is therefore looked for, not
its first link - `fall_back` walks the friendly units outwards from the retreating one, breadth
first, and stops at the first free square that can be stood on. A breadth-first walk finds the
shortest chain, and a chain of *k* links is *k* units falling back, the retreating one included:
the same walk therefore satisfies "the least movement" and "as few friendly units as possible" at
once, without weighing one against the other.

A module of its own rather than a corner of `combat.py`: combat reads Table I, this walks the
board. `combat.fight` calls it where the table says `AR` or `DR`, and it is the only caller.

Nothing here rolls a die, and nothing here knows the application: the board is modified in place
and what happened is returned.
"""

from collections import deque
from collections.abc import Collection
from typing import Optional

from tenebrae.engine.board import Board
from tenebrae.engine.hexagon import UNINHABITABLE, Hex
from tenebrae.engine.piece import Piece


class RetreatOutcome:
    """What a fall-back came to: the squares walked, or the unit removed for want of one.

    `moves` gives every unit that fell back, `(origin, destination)`, **the retreating one first**
    and each pushed friend after it, in the order they were pushed. It is empty when the unit was
    eliminated, and `eliminated` then carries the square it was standing on. `piece` is the
    retreating unit itself, which the caller can no longer read off the board once it has fallen.
    """

    __slots__ = ("moves", "eliminated", "piece")

    moves: list[tuple[Hex, Hex]]
    eliminated: Optional[Hex]
    piece: Optional[Piece]

    def __init__(self, moves: Collection[tuple[Hex, Hex]] = (),
                 eliminated: Optional[Hex] = None, piece: Optional[Piece] = None) -> None:
        """Keeps what the fall-back did.

        Args:
            moves: `(origin, destination)` per unit that fell back, the retreating one first.
            eliminated: The square of the unit removed for want of a retreat, if there was one.
            piece: The unit that had to fall back.
        """
        self.moves = list(moves)
        self.eliminated = eliminated
        self.piece = piece

    @property
    def fell_back(self) -> bool:
        """True if the unit found somewhere to go - alone or by pushing friends."""
        return bool(self.moves)

    @property
    def pushed(self) -> int:
        """How many friendly units had to give way; 0 when the unit stepped back on its own."""
        return max(len(self.moves) - 1, 0)

    @property
    def destination(self) -> Optional[Hex]:
        """The square the retreating unit reached, or `None` if it was eliminated."""
        return self.moves[0][1] if self.moves else None

    def __repr__(self) -> str:
        """Where the unit went and how many friends it pushed, or its elimination."""
        if self.eliminated is not None:
            return f"RetreatOutcome(eliminated at {self.eliminated.key})"
        return f"RetreatOutcome(to {self.destination.key if self.destination else None}, " \
               f"{self.pushed} pushed)"


def can_be_stood_on(hexagon: Hex, controlled: Collection[str]) -> bool:
    """Says whether a retreating unit may end up on this square, whoever occupies it.

    The booklet names the three impediments in one breath - "a lake, a river or an enemy zone of
    control" - and nothing else: a retreat is not a movement, it spends no points, so the cost of
    the terrain and the mountains' access rule have no say in it. `UNINHABITABLE` is the engine's
    reading of "a lake, a river": the terrains no unit ever stands on, the Rift of Tsaroth
    included.

    Args:
        hexagon: The square considered.
        controlled: The "q,r,s" keys under the enemy's zones of control.

    Returns:
        True if the square is on the map, habitable, and free of enemy control.
    """
    return (hexagon.is_on_map
            and hexagon.terrain not in UNINHABITABLE
            and hexagon.key not in controlled)


def retreat_squares(board: Board, origin: Hex, controlled: Collection[str]) -> list[Hex]:
    """Lists the free squares the unit on `origin` may fall back to, in square order.

    Args:
        board: The board.
        origin: The square the unit must leave.
        controlled: The "q,r,s" keys under the enemy's zones of control.

    Returns:
        The adjacent squares that are free and can be stood on, sorted by key.
    """
    return sorted((neighbour for neighbour in origin.neighbours()
                   if board.piece_on(neighbour) is None
                   and can_be_stood_on(neighbour, controlled)),
                  key=lambda hexagon: hexagon.key)


def friendly_squares(board: Board, origin: Hex, side: str,
                     controlled: Collection[str]) -> list[Hex]:
    """Lists the adjacent squares held by a friend that the unit could take by pushing it.

    A square the retreating unit could not stand on is no more taken from a friend than it is
    entered empty: the ban on falling back into an enemy zone of control does not lift because
    somebody friendly is standing there (see the caveats in `tenebrae/engine/README.md`).

    Args:
        board: The board.
        origin: The square the unit must leave.
        side: The retreating unit's side.
        controlled: The "q,r,s" keys under the enemy's zones of control.

    Returns:
        The adjacent squares held by that side and habitable, sorted by key.
    """
    return sorted((neighbour for neighbour in origin.neighbours()
                   if (placed := board.piece_on(neighbour)) is not None and placed.side == side
                   and can_be_stood_on(neighbour, controlled)),
                  key=lambda hexagon: hexagon.key)


def shortest_chain(board: Board, origin: Hex, side: str,
                   controlled: Collection[str]) -> Optional[list[Hex]]:
    """Finds the shortest run of squares taking the unit on `origin` off the board's front.

    A breadth-first walk from `origin`, hopping from friend to friend and stopping at the first
    free square that can be stood on. The chain it returns is `[origin, …, free square]`: the unit
    on each square steps onto the next one, so a chain of *n* squares moves *n - 1* units - the
    retreating one, then each friend it pushed.

    The square being left is never a destination: the unit is falling back from it under fire, and
    handing it to a friend would be an exchange of places, not a fall-back.

    Args:
        board: The board.
        origin: The square the retreating unit must leave.
        side: Its side; only its own army gives way to it.
        controlled: The "q,r,s" keys under the enemy's zones of control.

    Returns:
        The chain of squares, or `None` if no free square can be reached that way.
    """
    previous: dict[str, Hex] = {}
    seen = {origin.key}
    queue = deque([origin])
    while queue:
        square = queue.popleft()
        free = retreat_squares(board, square, controlled)
        if free:
            # The lowest square key among the equally good ones: the engine breaks every tie that
            # way (see `ai.py`), so two identical games fall back identically.
            return _chain_to(previous, origin, square) + [free[0]]
        for friendly in friendly_squares(board, square, side, controlled):
            if friendly.key in seen:
                continue
            seen.add(friendly.key)
            previous[friendly.key] = square
            queue.append(friendly)
    return None


def _chain_to(previous: dict[str, Hex], origin: Hex, square: Hex) -> list[Hex]:
    """Walks the parents back from `square` to `origin`.

    Args:
        previous: Square key -> the square it was reached from.
        origin: The start of the walk.
        square: The square reached.

    Returns:
        The squares from `origin` to `square`, inclusive.
    """
    chain = [square]
    while chain[0].key != origin.key:
        chain.insert(0, previous[chain[0].key])
    return chain


def push_along(board: Board, chain: list[Hex]) -> list[tuple[Hex, Hex]]:
    """Steps every unit of the chain one square along it, from the far end backwards.

    Backwards so that no square ever carries two pieces: the last friend enters the free square
    before the one behind it takes the square it is leaving. The counters are picked up, so they
    lie down at a fresh angle, as they do after a move.

    Args:
        board: The board, modified in place.
        chain: `[origin, …, free square]`, as `shortest_chain` returns it.

    Returns:
        The `(origin, destination)` pairs, the retreating unit's first.
    """
    for rank in range(len(chain) - 2, -1, -1):
        piece = board.remove(chain[rank])
        if piece is not None:
            board.place(chain[rank + 1], piece)
    return [(chain[rank], chain[rank + 1]) for rank in range(len(chain) - 1)]


def fall_back_together(board: Board, origins: Collection[Hex]) -> list[RetreatOutcome]:
    """Makes a whole group of units fall back - the attackers of an `AR`, and nothing else so far.

    The booklet calls it a "simultaneous falling back"; here they go one after another, in square
    order, each seeing the board as the one before it left it. Two consequences, both of them
    interpretations (see `tenebrae/engine/README.md`):

    - a unit **already pushed** by a comrade's chain has given its ground and does not give it
      twice: it is passed over;
    - the order being the square keys', two identical games fall back identically.

    Args:
        board: The board, modified in place.
        origins: The squares of the units that must fall back.

    Returns:
        One outcome per unit that actually had to fall back, in the order they did.
    """
    outcomes: list[RetreatOutcome] = []
    given_ground: set[str] = set()
    for origin in sorted(origins, key=lambda hexagon: hexagon.key):
        if origin.key in given_ground:
            continue
        outcome = fall_back(board, origin)
        outcomes.append(outcome)
        given_ground.update(moved.key for moved, _ in outcome.moves)
    return outcomes


def fall_back(board: Board, origin: Hex) -> RetreatOutcome:
    """Makes the unit on `origin` fall back one square, or removes it from play.

    The rule in full: the unit steps onto a free adjacent square that is neither a lake, nor a
    river, nor under an enemy zone of control; failing that it pushes a friend and takes its
    place, that friend falling back in its turn under the same rule; failing that too, it is
    removed from play. The chain of pushes is the shortest there is (see `shortest_chain`).

    Args:
        board: The board, modified in place.
        origin: The square of the unit that has to fall back.

    Returns:
        What happened. An empty square gives an outcome with nothing in it: there was nothing to
        fall back.
    """
    piece: Optional[Piece] = board.piece_on(origin)
    if piece is None:
        return RetreatOutcome()

    controlled = board.zones_of_control_against(piece.side)
    chain = shortest_chain(board, origin, piece.side, controlled)
    if chain is None:
        board.remove(origin)
        return RetreatOutcome(eliminated=origin, piece=piece)
    return RetreatOutcome(moves=push_along(board, chain), piece=piece)
