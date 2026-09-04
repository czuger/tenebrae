"""The units removed from play, kept for the count at the end of the game.

> Eliminated units are kept by the player who eliminated them, to establish their total of points
> at the end of the game.

The booklet counts them for the **eliminator**; a unit is also, and as plainly, a loss for the
army it came from. This register therefore keeps the fact, not the reading of it: each entry says
which piece fell, on which square, on which side it fought and which side took it. `points_taken_by`
counts the booklet's total, `points_lost_by` the other one, and neither invents anything the other
could contradict.

It is the third thing a game keeps beside its board, along with the turn and the combat register,
and it is kept the same way: a plain object, serialised into the saved game by the repository
(`repositories/game.py`), and knowing nothing of MongoDB.

A unit has no identity of its own in this engine - a counter stands for all the units it
represents - so an entry names the piece and the square it fell on, and nothing more. Two units of
the same counter eliminated on the same square in the same game make two entries, as they should.
"""

from collections.abc import Iterable, Mapping
from typing import Optional, TypedDict

from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import CATALOGUE, Piece


class Casualty(TypedDict):
    """One unit removed from play: what it was, where it fell, whose it was and who took it."""

    square: str
    piece: str
    side: str
    taken_by: str


class Casualties:
    """The graveyard of a game, in the order the units fell.

        casualties = Casualties()
        casualties.record(Hex(1, 26, -27), piece("nains-01-5-infanteries"), "tenebres")
        casualties.points_taken_by("tenebres")  # 12, the counter's strength
        casualties.lost_by("alliance")          # its one entry
    """

    _losses: list[Casualty]

    def __init__(self, losses: Iterable[Casualty] = ()) -> None:
        """Opens the register, empty or on entries read back from a saved game.

        Args:
            losses: The entries to start from, oldest first.
        """
        self._losses = list(losses)

    @property
    def losses(self) -> list[Casualty]:
        """Every unit removed from play, oldest first."""
        return list(self._losses)

    def record(self, hexagon: Hex, piece: Piece, taken_by: Optional[str] = None) -> Casualty:
        """Enters a unit removed from play.

        Args:
            hexagon: The square it was standing on.
            piece: The piece removed.
            taken_by: The side that eliminated it. `None` - a unit that fell for want of a
                retreat with nobody to claim it - is recorded as an empty side.

        Returns:
            The entry recorded.
        """
        loss: Casualty = {"square": hexagon.key, "piece": piece.key,
                          "side": piece.side, "taken_by": taken_by or ""}
        self._losses.append(loss)
        return loss

    def lost_by(self, side: str) -> list[Casualty]:
        """The units this side lost.

        Args:
            side: The side that fought them.

        Returns:
            Its entries, oldest first.
        """
        return [loss for loss in self._losses if loss["side"] == side]

    def taken_by(self, side: str) -> list[Casualty]:
        """The units this side eliminated.

        Args:
            side: The side that took them.

        Returns:
            Its entries, oldest first.
        """
        return [loss for loss in self._losses if loss["taken_by"] == side]

    def points_taken_by(self, side: str) -> int:
        """The total the booklet asks for at the end of the game.

        Args:
            side: The side that eliminated them.

        Returns:
            The strengths of the units it took; a counter with no legible strength counts 0.
        """
        return sum(_strength_of(loss["piece"]) for loss in self.taken_by(side))

    def points_lost_by(self, side: str) -> int:
        """What this side left on the field, counted the same way.

        Args:
            side: The side that fought them.

        Returns:
            The strengths of the units it lost.
        """
        return sum(_strength_of(loss["piece"]) for loss in self.lost_by(side))

    def reset(self) -> None:
        """Empties the register: a new game starts with nobody fallen."""
        self._losses.clear()

    def to_dict(self) -> dict[str, list[Casualty]]:
        """Serialises the register for the saved game.

        Returns:
            `{"casualties": [...]}`, oldest first.
        """
        return {"casualties": self.losses}

    def restore(self, losses: Optional[Iterable[Mapping[str, object]]]) -> None:
        """Puts the register back as a saved game held it.

        Entries missing a field are read with their field empty: a game saved before this register
        existed has none at all, and must stay resumable.

        Args:
            losses: The saved entries, or `None`. `Mapping[str, object]` and not `Casualty`: they
                come back from the base, where nothing guarantees the four fields.
        """
        self._losses = [{"square": str(loss.get("square", "")),
                         "piece": str(loss.get("piece", "")),
                         "side": str(loss.get("side", "")),
                         "taken_by": str(loss.get("taken_by", ""))}
                        for loss in losses or ()]

    def __len__(self) -> int:
        """The number of units removed from play."""
        return len(self._losses)

    def __repr__(self) -> str:
        """The number of units removed from play."""
        return f"Casualties({len(self._losses)} units removed from play)"


def _strength_of(piece_key: str) -> int:
    """Reads the strength a counter is worth in the end-of-game count.

    Args:
        piece_key: The piece's key.

    Returns:
        Its strength; 0 for an unknown counter, or one whose strength could not be read off the
        photograph.
    """
    piece = CATALOGUE.get(piece_key)
    if piece is None or piece.strength is None:
        return 0
    return piece.strength
