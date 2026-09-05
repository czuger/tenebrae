"""What a movement phase has already consumed: the points each unit has left of its allowance.

The booklet ("Movement"): "during their active phase, each player moves as many units as they wish,
**within the limit of the movement points allotted to each unit**". The limit is a capital for the
phase and not a rate per click: a unit with three points may walk three squares of plain one after
another, and a fourth click must be refused. `MovementRegister` keeps that capital and nothing
else - it is a register, not a walk: it touches neither the board nor the turn, and is emptied at
each new movement phase, exactly as `tenebrae.engine.combat_register.CombatRegister` is at each new
combat phase.

The register keeps **squares**, as "q,r,s" keys, and not piece keys: one counter stands for all the
units it represents - `orques-01-15-infanteries` is placed fifteen times in scenario no. 4 - and the
engine gives the unit no identity. Unlike a combat phase, a movement phase is made of units
changing squares, so what a unit has left travels with it: `spend` writes the remainder on the
square arrived at and clears the one left behind.

Points are exact fractions, as everywhere movement is counted: a road is worth a third of a point
and five thirds must not drift. They are serialised as the fractions they are - "5/3" - so that a
saved game reopens on the very budget it was left with.
"""

from collections.abc import Iterable, Mapping
from fractions import Fraction
from typing import Self

# What a unit that has not moved yet has left: everything the counter is printed with. Kept as a
# name because the register answers "nothing recorded" and "the whole budget" with one value.
NOTHING_SPENT = None


class MovementRegister:
    """The points each unit has left of its movement allowance, this movement phase.

        register = MovementRegister()
        register.points_left("1,26,-27", 3)               # Fraction(3), it has not moved
        register.spend("1,26,-27", "2,26,-28", Fraction(1), 3)
        register.points_left("2,26,-28", 3)               # Fraction(2)

    A square the register knows nothing of is a unit that has not moved: it has its whole budget.
    That is what makes the register empty at the start of a phase rather than filled with every
    counter on the board.
    """

    __slots__ = ("_remaining",)

    _remaining: dict[str, Fraction]

    def __init__(self) -> None:
        """Opens an empty register: every unit with its whole allowance."""
        self._remaining = {}

    @property
    def remaining(self) -> dict[str, Fraction]:
        """"q,r,s" -> the points left, for the units that have moved this phase."""
        return dict(self._remaining)

    def points_left(self, square: str, budget: int) -> Fraction:
        """Reads what the unit on a square may still spend this phase.

        Args:
            square: The "q,r,s" key.
            budget: The movement printed on its counter, which is what a unit that has not moved
                yet has left.

        Returns:
            The points left, never negative.
        """
        spent = self._remaining.get(square, NOTHING_SPENT)
        return Fraction(budget) if spent is NOTHING_SPENT else spent

    def has_moved(self, square: str) -> bool:
        """Says whether the unit on a square has already moved this phase.

        Args:
            square: The "q,r,s" key.

        Returns:
            True if something has been spent from that square's allowance.
        """
        return square in self._remaining

    def is_exhausted(self, square: str, budget: int) -> bool:
        """Says whether the unit on a square has nothing left to spend.

        Args:
            square: The "q,r,s" key.
            budget: The movement printed on its counter.

        Returns:
            True where not a single point is left; a unit with a fraction of one still has the
            right to try, and it is the terrain that will refuse it.
        """
        return self.points_left(square, budget) <= 0

    def spend(self, origin: str, destination: str, cost: Fraction, budget: int) -> Fraction:
        """Charges a move to the unit's allowance and moves that allowance with it.

        The remainder is written on the square arrived at and the square left behind is cleared:
        the unit is designated by where it stands, and a leftover entry would charge the next
        counter to take that square with a move it never made.

        Args:
            origin: The square left, "q,r,s".
            destination: The square reached, "q,r,s".
            cost: What the move cost, in points.
            budget: The movement printed on the counter.

        Returns:
            What is left after the move, never negative.
        """
        left = max(Fraction(0), self.points_left(origin, budget) - cost)
        self._remaining.pop(origin, None)
        self._remaining[destination] = left
        return left

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Serialises the register.

        Returns:
            `remaining`, "q,r,s" -> the points left written as an exact fraction ("5/3"), sorted by
            square. Sorting keeps the shape stable from one saved game to the next, and the
            fraction keeps it exact - a float would drift a third of a point at a time.
        """
        return {"remaining": {square: str(left)
                              for square, left in sorted(self._remaining.items())}}

    def restore(self, remaining: Mapping[str, str] | Iterable[tuple[str, str]]) -> Self:
        """Replaces the register's contents with those of a saved game.

        Args:
            remaining: "q,r,s" -> the points left, as `to_dict` writes them. A game saved before
                movement was counted carries none, and reopens with every unit at its full
                allowance - which is what a movement phase starts with anyway.

        Returns:
            The register itself.
        """
        entries = remaining.items() if isinstance(remaining, Mapping) else remaining
        self._remaining = {square: Fraction(left) for square, left in entries}
        return self

    def reset(self) -> Self:
        """Empties the register: a new movement phase gives every unit its allowance back.

        Returns:
            The register itself.
        """
        self._remaining.clear()
        return self

    def __repr__(self) -> str:
        """How many units have already spent something."""
        return f"MovementRegister({len(self._remaining)} units having moved)"
