"""The game state, reduced to its essentials: which pieces are placed, where, and on which side.

The map does not change, nor do the counters; the positions do. This is the only mutable object in
the engine, and it is what makes zones of control computable: without knowing who occupies which
square, the rule of the six surrounding squares has nobody to apply to.

The board judges neither stacking, nor scenarios, nor game turns: it carries positions and knows
how to derive the moves they allow.

It carries a second thing, which is not a rule: the **tilt** of each placed piece, those few
degrees that make the counter look as though it had been dropped onto the map by hand. It is drawn
at random when the piece is placed and belongs to the game state: saved with the positions, it only
changes when the piece is picked up again, so that a reloaded page finds the counters lying as they
were.

`moves` traces its whole computation on the module's debug logger - the budget, what the walk was
told to avoid, and every square it reached with its distance, its terrain and the reason it is not
offered. It is not the game log, and the application gives it a file of its own (see `LOG`).
"""

import logging
import random
from collections.abc import Collection, Iterable, Mapping
from fractions import Fraction
from typing import Optional, Self

from tenebrae.engine.hexagon import DEFAULT_MOVEMENT, Hex, zone_of_control
from tenebrae.engine.piece import CATALOGUE, OPPONENTS, Piece

# The engine's own trace, and not the game log: `tenebrae.log` is what the player reads in the
# browser's column, and a movement recomputed at every click would drown it. Nothing is configured
# here - the engine writes to no file it has chosen: the application opens this one on
# `logs/movement.log` at DEBUG (`application/logs/movement_log.py`). Read from an interpreter with
# no application around, the logger stays at the root's level, hence silent, and `moves` does not
# even build its lines - `logging.basicConfig(level=logging.DEBUG)` is enough to see them.
LOG = logging.getLogger(__name__)

# The tilt runs between these two extremes, in degrees: beyond them the piece looks badly placed.
MAXIMUM_TILT = 5.0

# Two decimals: the display shows no more (`toFixed(2)` in map.js).
TILT_DECIMALS = 2


def draw_a_tilt() -> float:
    """Draws a random angle for a counter dropped onto the map.

    Returns:
        An angle in degrees, within the bounds of `MAXIMUM_TILT`.
    """
    return round(random.uniform(-MAXIMUM_TILT, MAXIMUM_TILT), TILT_DECIMALS)


class Board:
    """The pieces placed on the map, at most one square per piece.

    Built empty, or from `(hexagon, piece)` pairs:

        board = Board([(Hex(1, 26, -27), piece("elfes-01-5-infanteries"))])
    """

    _pieces: dict[str, Piece]
    _tilts: dict[str, float]

    def __init__(self, positions: Iterable[tuple[Hex, Piece]] = ()) -> None:
        """Places the given pieces.

        Args:
            positions: `(hexagon, piece)` pairs, placed in order.
        """
        self._pieces = {}
        self._tilts = {}
        for hexagon, placed in positions:
            self.place(hexagon, placed)

    @property
    def pieces(self) -> dict[str, Piece]:
        """"q,r,s" -> `Piece` for everything placed, in the order it was placed."""
        return dict(self._pieces)

    @property
    def tilts(self) -> dict[str, float]:
        """"q,r,s" -> the angle, in degrees, of the counter lying there."""
        return dict(self._tilts)

    def place(self, hexagon: Hex, piece: Piece, tilt: Optional[float] = None) -> None:
        """Places a piece on a square, replacing whatever was there.

        Args:
            hexagon: The square.
            piece: The piece to place.
            tilt: The angle to lay the counter at; drawn at random when omitted. Only a saved game
                read back passes one.

        Raises:
            ValueError: If the square is off the map.
        """
        self._require_the_map(hexagon)
        self._pieces[hexagon.key] = piece
        self._tilts[hexagon.key] = draw_a_tilt() if tilt is None else tilt

    def remove(self, hexagon: Hex) -> Optional[Piece]:
        """Removes the piece from a square.

        Args:
            hexagon: The square.

        Returns:
            The piece removed, or `None` if the square was empty.
        """
        self._tilts.pop(hexagon.key, None)
        return self._pieces.pop(hexagon.key, None)

    def clear(self) -> None:
        """Removes every piece: the board becomes a bare map again."""
        self._pieces.clear()
        self._tilts.clear()

    def piece_on(self, hexagon: Hex) -> Optional[Piece]:
        """Reads the piece placed on a square.

        Args:
            hexagon: The square.

        Returns:
            The piece, or `None` if the square is empty.
        """
        return self._pieces.get(hexagon.key)

    def tilt_on(self, hexagon: Hex) -> Optional[float]:
        """Reads the angle of the counter lying on a square.

        Args:
            hexagon: The square.

        Returns:
            The angle in degrees, or `None` if the square is empty.
        """
        return self._tilts.get(hexagon.key)

    def squares_held_by(self, side: str) -> frozenset[str]:
        """Collects the squares a side occupies.

        Args:
            side: `"alliance"`, `"tenebres"` or `"neutre"`.

        Returns:
            The "q,r,s" keys of its pieces.
        """
        return frozenset(key for key, piece in self._pieces.items() if piece.side == side)

    def opponents_of(self, side: str) -> frozenset[str]:
        """Collects the squares held by the opposing side.

        Args:
            side: The side asking. The neutral side has no opponent.

        Returns:
            The "q,r,s" keys of the opposing pieces; empty for the neutral side.
        """
        opposite = OPPONENTS.get(side)
        return self.squares_held_by(opposite) if opposite else frozenset()

    def zones_of_control_against(self, side: str) -> frozenset[str]:
        """Collects the squares covered by the zones of control opposing a side.

        Args:
            side: The side that suffers them.

        Returns:
            The "q,r,s" keys controlled by opposing units; markers exert none.
        """
        exerting = [Hex.from_key(key) for key in self.opponents_of(side)
                    if self._pieces[key].exerts_a_zone_of_control]
        return zone_of_control(exerting)

    def reach(self, origin: Hex, piece: Optional[Piece] = None,
              budget: Optional[Fraction] = None) -> dict[str, Fraction]:
        """Finds the squares the piece on `origin` can reach, and what each of them costs.

        A square occupied by a friend can be crossed but not taken: "it is not possible to place
        more than one unit in the same square". It is discarded from the destinations, not from
        the walk.

        Args:
            origin: The departure square.
            piece: Only serves to question an empty square: the **placed** piece prevails. With
                neither, the flat movement rate applies and nobody is an opponent.
            budget: The points to spend, where they are not the counter's full allowance - a unit
                that has already moved this phase (`tenebrae/engine/movement_register.py`).

        Returns:
            "q,r,s" -> the points the trip costs, for the unoccupied squares only.
        """
        piece = self.piece_on(origin) or piece
        enemies: frozenset[str] = frozenset()
        controlled: frozenset[str] = frozenset()
        if piece is None:
            reachable = origin.reach() if budget is None else origin.reach(budget)
        else:
            enemies = self.opponents_of(piece.side)
            controlled = self.zones_of_control_against(piece.side)
            allowance = piece.movement_points if budget is None else budget
            reachable = origin.reach(allowance, enemies=enemies, under_control=controlled)
        costs = {key: cost for key, cost in reachable.items() if key not in self._pieces}
        if LOG.isEnabledFor(logging.DEBUG):
            self._trace_the_moves(origin, piece, enemies, controlled,
                                  [Hex.from_key(key) for key in reachable],
                                  [Hex.from_key(key) for key in costs])
        return costs

    def moves(self, origin: Hex, piece: Optional[Piece] = None,
              budget: Optional[Fraction] = None) -> list[Hex]:
        """Finds the squares the piece on `origin` can reach, zones of control included.

        Args:
            origin: The departure square.
            piece: Only serves to question an empty square: the **placed** piece prevails.
            budget: The points to spend, where they are not the counter's full allowance.

        Returns:
            The reachable, unoccupied squares.
        """
        return [Hex.from_key(key) for key in self.reach(origin, piece, budget)]

    def cost_of(self, origin: Hex, destination: Hex, piece: Optional[Piece] = None,
                budget: Optional[Fraction] = None) -> Optional[Fraction]:
        """Reads what one legal move would cost the unit that plays it.

        Args:
            origin: The departure square.
            destination: The arrival square.
            piece: The piece to assume if the origin is empty.
            budget: The points to spend, where they are not the counter's full allowance.

        Returns:
            The points the trip costs, or `None` where the move is not one the rules allow -
            which is the same answer `move` refuses on.
        """
        return self.reach(origin, piece, budget).get(destination.key)

    def _trace_the_moves(self, origin: Hex, piece: Optional[Piece], enemies: Collection[str],
                         controlled: Collection[str], reachable: list[Hex],
                         destinations: list[Hex]) -> None:
        """Writes a movement computation to the debug log, step by step.

        What the returned list alone does not say: whose movement it is and out of how many points,
        what the walk was told to avoid, and **why** a square the walk reached is not offered. The
        squares are told outwards from the origin, each with its terrain and its distance, so that
        the ring the budget stopped at can be read at a glance.

        Called only when the debug level is on: everything here is built for the reading, and the
        caller keeps `isEnabledFor` in front of it.

        Args:
            origin: The departure square.
            piece: The piece that moves, or `None` for the flat rate.
            enemies: The squares the walk refused to enter.
            controlled: The squares under an opposing zone of control, entered but not left.
            reachable: What the walk returned, occupied squares included.
            destinations: What `moves` offers, which is what the caller will act on.
        """
        # The counts come after their label rather than before it: a number followed by a noun
        # would read "1 squares" as often as not, and this is read by eye.
        LOG.debug("moves from %s: %s, movement points: %s", origin.key,
                  f"{piece.key} ({piece.side})" if piece else "no piece, flat rate",
                  piece.movement_points if piece else DEFAULT_MOVEMENT)
        LOG.debug("moves from %s: enemy squares refused: %s, under an enemy zone of control: %s",
                  origin.key, len(enemies), len(controlled))
        LOG.debug("moves from %s: squares reached by the walk: %s, free to be taken: %s",
                  origin.key, len(reachable), len(destinations))
        offered = {hexagon.key for hexagon in destinations}
        for hexagon in sorted(reachable, key=lambda square: (origin.distance(square), square.key)):
            LOG.debug("moves from %s:   %s at %s (%s)%s", origin.key, hexagon.key,
                      origin.distance(hexagon), hexagon.terrain,
                      self._why_not(hexagon, offered, controlled))

    @staticmethod
    def _why_not(hexagon: Hex, offered: Collection[str], controlled: Collection[str]) -> str:
        """Says what keeps a square the walk reached from being an ordinary destination.

        Args:
            hexagon: The square reached.
            offered: The keys `moves` is about to return.
            controlled: The squares under an opposing zone of control.

        Returns:
            A clause to append to the square's line, empty when there is nothing to say. A
            friend standing under an enemy zone of control reads as the zone: it is the zone that
            stops the walk there, the friend only keeps the square from being taken.
        """
        if hexagon.key in controlled:
            return " - under an enemy zone of control: entered, not left"
        if hexagon.key not in offered:
            return " - occupied by a friend: crossed, not taken"
        return ""

    def movement_of(self, origin: Hex, piece: Optional[Piece] = None) -> int:
        """Reads the movement budget of the piece on `origin`.

        Args:
            origin: The square.
            piece: The piece to assume if the square is empty.

        Returns:
            The movement points; `DEFAULT_MOVEMENT` if there is no piece at all.
        """
        piece = self.piece_on(origin) or piece
        return piece.movement_points if piece else DEFAULT_MOVEMENT

    def move(self, origin: Hex, destination: Hex, piece: Optional[Piece] = None,
             budget: Optional[Fraction] = None) -> bool:
        """Moves the piece from `origin` to `destination` if the rules allow.

        The move is recomputed here, never taken on trust. An empty origin square moves nothing
        but still answers: that is how the rules are questioned by hand.

        What the phase has already consumed is **not** kept here: a board judges the trip, not the
        allowance. `tenebrae.engine.movement.move` plays a move against both, and is what the
        server and the AI go through.

        Args:
            origin: The departure square.
            destination: The arrival square.
            piece: The piece to assume if the origin is empty.
            budget: The points to spend, where they are not the counter's full allowance.

        Returns:
            True if the move is legal; the board is then updated.
        """
        if self.cost_of(origin, destination, piece, budget) is None:
            return False
        placed = self.remove(origin)
        if placed is not None:
            # No tilt passed: a counter picked up lies down differently than it was.
            self.place(destination, placed)
        return True

    def to_dict(self) -> dict[str, str]:
        """Serialises the positions in the format of `Scenario.placement`.

        Returns:
            "q,r,s" -> piece key, in placement order. The tilts are given separately by `tilts`.
        """
        return {key: piece.key for key, piece in self._pieces.items()}

    def restore(self, placement: Mapping[str, str],
                tilts: Optional[Mapping[str, float]] = None) -> Self:
        """Clears the board and places each piece back from a saved placement.

        Everything is checked before the board is touched: a saved game citing a square off the
        map or an unknown piece is refused, and the board left as it was.

        Args:
            placement: "q,r,s" -> piece key, the inverse of `to_dict`.
            tilts: "q,r,s" -> angle. A square not in it gets a fresh angle, once.

        Returns:
            The board itself.

        Raises:
            ValueError: If a square is off the map.
            KeyError: If a piece key is unknown to the catalogue.
        """
        tilts = tilts or {}
        placings = []
        for key, piece_key in placement.items():
            hexagon = Hex.from_key(key)
            self._require_the_map(hexagon)
            placings.append((hexagon, CATALOGUE[piece_key], tilts.get(key)))
        self.clear()
        for hexagon, piece, tilt in placings:
            self.place(hexagon, piece, tilt)
        return self

    @staticmethod
    def _require_the_map(hexagon: Hex) -> None:
        """Refuses a square that is not on the map.

        Args:
            hexagon: The square to check.

        Raises:
            ValueError: If it is off the map.
        """
        if not hexagon.is_on_map:
            raise ValueError(f"hexagon {hexagon!r} is not on the map")

    def __len__(self) -> int:
        """The number of pieces placed."""
        return len(self._pieces)

    def __repr__(self) -> str:
        """The number of pieces placed."""
        return f"Board({len(self._pieces)} pieces placed)"
