"""The game state, reduced to its essentials: which pieces are placed, where, and on which side.

The map does not change, nor do the counters; the positions do. This is the only mutable object in
the engine, and it is what makes zones of control computable: without knowing who occupies which
square, the rule of the six surrounding squares has nobody to apply to.

The board judges neither stacking, nor scenarios, nor game turns: it carries positions and knows
how to derive the moves they allow.

It carries a second thing, which is not a rule: the **tilt** of each placed piece, those few
degrees that make the counter look as though it had been dropped onto the map by hand. It is drawn
at random when the piece is placed, and that is all it has in common with a game die - but it
belongs here because it is part of the game state: it is saved with the positions, and it only
changes when the piece is picked up again. A board read back does not re-roll its dice: without
that, the piece would lie down differently every time the page was reloaded.
"""

import random

from tenebrae.engine.hexagon import DEFAULT_MOVEMENT, Hex, zone_of_control
from tenebrae.engine.piece import CATALOGUE, OPPONENTS

# The tilt runs between these two extremes, in degrees: beyond them the piece no longer looks
# placed askew, it looks badly placed.
MAXIMUM_TILT = 5.0

# Two decimals: the display shows no more (`toFixed(2)` in map.js), and a short number reads well
# in the saved game.
TILT_DECIMALS = 2


def draw_a_tilt():
    """A random angle, in degrees, within the bounds of `MAXIMUM_TILT`."""
    return round(random.uniform(-MAXIMUM_TILT, MAXIMUM_TILT), TILT_DECIMALS)


class Board:
    """The pieces placed on the map, at most one square per piece.

    Built empty, or from `(hexagon, piece)` pairs:

        board = Board([(Hex(1, 26, -27), piece("elfes-01-5-infanteries"))])
    """

    def __init__(self, positions=()):
        self._pieces = {}
        self._tilts = {}
        for hexagon, placed in positions:
            self.place(hexagon, placed)

    @property
    def pieces(self):
        """"q,r,s" -> `Piece` for everything placed, in the order it was placed."""
        return dict(self._pieces)

    @property
    def tilts(self):
        """"q,r,s" -> the angle, in degrees, of the counter lying there."""
        return dict(self._tilts)

    def place(self, hexagon, piece, tilt=None):
        """Places a piece on a square, replacing whatever was there.

        With no tilt given, one is drawn at random: placing is dropping the counter onto the map.
        A tilt is only passed to put a piece back exactly as it was - a saved game read back.
        """
        self._require_the_map(hexagon)
        self._pieces[hexagon.key] = piece
        self._tilts[hexagon.key] = draw_a_tilt() if tilt is None else tilt

    def remove(self, hexagon):
        """Removes the piece from the square and returns it; `None` if it was empty."""
        self._tilts.pop(hexagon.key, None)
        return self._pieces.pop(hexagon.key, None)

    def clear(self):
        """Removes every piece: the board becomes a bare map again."""
        self._pieces.clear()
        self._tilts.clear()

    def piece_on(self, hexagon):
        """The piece placed on this square, or `None`."""
        return self._pieces.get(hexagon.key)

    def tilt_on(self, hexagon):
        """The angle of the counter lying on this square, or `None` if it is empty."""
        return self._tilts.get(hexagon.key)

    def squares_held_by(self, side):
        """The squares this side occupies, as "q,r,s" keys."""
        return frozenset(key for key, piece in self._pieces.items() if piece.side == side)

    def opponents_of(self, side):
        """The squares held by the opposing side.

        The neutral side - flyers, conjurations, markers - has no opponent: it hinders nobody and
        nobody hinders it.
        """
        opposite = OPPONENTS.get(side)
        return self.squares_held_by(opposite) if opposite else frozenset()

    def zones_of_control_against(self, side):
        """The squares covered by the opposing zones of control, as "q,r,s" keys.

        Only opposing units that exert a zone of control count: markers exert none.
        """
        exerting = [Hex.from_key(key) for key in self.opponents_of(side)
                    if self._pieces[key].exerts_a_zone_of_control]
        return zone_of_control(exerting)

    def moves(self, origin, piece=None):
        """The squares the piece placed on `origin` can reach, zones of control included.

        The **placed** piece prevails; `piece` only serves to question an empty square, to find
        out where a given unit would go if it were put there. With no piece at all, the question
        is that of a move without a unit: the flat movement rate applies and, for want of a side,
        nobody is an opponent.

        A square occupied by a friend can be crossed - the booklet allows it - but not taken: "it
        is not possible to place more than one unit in the same square". It is therefore discarded
        from the destinations, not from the walk.
        """
        piece = self.piece_on(origin) or piece
        if piece is None:
            reachable = origin.moves()
        else:
            reachable = origin.moves(
                piece.movement_points,
                enemies=self.opponents_of(piece.side),
                under_control=self.zones_of_control_against(piece.side),
            )
        return [hexagon for hexagon in reachable if hexagon.key not in self._pieces]

    def movement_of(self, origin, piece=None):
        """The points of the piece placed on `origin` - the flat rate if the square is empty."""
        piece = self.piece_on(origin) or piece
        return piece.movement_points if piece else DEFAULT_MOVEMENT

    def move(self, origin, destination, piece=None):
        """Moves the piece from `origin` to `destination` if the rules allow; says whether it
        happened.

        The move is recomputed here, never taken on trust - the destination square is therefore
        free by construction. An empty origin square moves nothing but still answers: that is how
        the rules are questioned by hand.
        """
        if destination not in self.moves(origin, piece):
            return False
        placed = self.remove(origin)
        if placed is not None:
            # Put back without an angle: a counter picked up lies down differently than it was.
            # This is the only moment when the tilt changes.
            self.place(destination, placed)
        return True

    def to_dict(self):
        """"q,r,s" -> piece key, in placement order - the format of `Scenario.placement`.

        That is nearly the whole game: a placed piece has no state other than its square, its
        counter - found back in the catalogue by its key - and the angle it lies at, which `tilts`
        gives separately.
        """
        return {key: piece.key for key, piece in self._pieces.items()}

    def restore(self, placement, tilts=None):
        """Clears the board and places each piece back from a "square -> piece key" dict.

        The inverse of `to_dict`: counters are taken back from the catalogue, squares rechecked -
        a saved game citing a square off the map or an unknown piece is refused, not patched up.
        Everything is checked before the board is touched: refused means left as it was.

        `tilts` lays the counters back the way they were lying. A square that is not in it - a
        game saved before we started keeping them - gets a fresh angle: the piece lies down once,
        and does not move again.
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
    def _require_the_map(hexagon):
        if not hexagon.is_on_map:
            raise ValueError(f"hexagon {hexagon!r} is not on the map")

    def __len__(self):
        return len(self._pieces)

    def __repr__(self):
        return f"Board({len(self._pieces)} pieces placed)"
