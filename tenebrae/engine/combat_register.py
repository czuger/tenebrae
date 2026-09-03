"""What a combat phase has already consumed: which squares have attacked, which have been attacked.

The booklet requires that a unit fight only one combat per phase - alone or within a group of
attackers - and that a unit be taken as a target only once. `CombatRegister` keeps that and nothing
else: it is a register, not a resolution - it touches neither the board nor the turn, and is emptied
at each new combat phase.

The register keeps **squares**, as "q,r,s" keys, and not piece keys: one counter stands for all the
units it represents - `orques-01-15-infanteries` is placed fifteen times in scenario no. 4 - and the
engine gives the unit no identity. The square designates a single one, and nothing moves during a
combat phase. That is what makes the equivalence exact for as long as the register lives.
"""

from collections.abc import Iterable
from typing import Self


class CombatRegister:
    """The squares that have attacked, and those that have been attacked, this combat phase.

        register = CombatRegister()
        register.can_attack("1,26,-27")           # True
        register.record(["1,26,-27"], "2,26,-28")
        register.can_attack("1,26,-27")           # False

    A combat counts as soon as it is fought: an outcome the engine leaves without effect - a
    retreat - engages the units just as much as an elimination.
    """

    __slots__ = ("engaged_attackers", "engaged_targets")

    engaged_attackers: set[str]
    engaged_targets: set[str]

    def __init__(self) -> None:
        """Opens an empty register: every unit available."""
        self.engaged_attackers = set()
        self.engaged_targets = set()

    def can_attack(self, square: str) -> bool:
        """Says whether the unit on a square has not attacked yet this phase.

        Args:
            square: The "q,r,s" key.

        Returns:
            True if the square has not been recorded as an attacker.
        """
        return square not in self.engaged_attackers

    def can_be_targeted(self, square: str) -> bool:
        """Says whether the unit on a square has not been attacked yet this phase.

        Args:
            square: The "q,r,s" key.

        Returns:
            True if the square has not been recorded as a target.
        """
        return square not in self.engaged_targets

    def record(self, attacking_squares: Iterable[str], target_square: str) -> Self:
        """Marks a combat as fought: the attackers attacked, the target was attacked.

        Args:
            attacking_squares: The "q,r,s" keys of the attackers.
            target_square: The "q,r,s" key of the target.

        Returns:
            The register itself.
        """
        self.engaged_attackers.update(attacking_squares)
        self.engaged_targets.add(target_square)
        return self

    def to_dict(self) -> dict[str, list[str]]:
        """Serialises the register.

        Returns:
            Two sorted lists of squares, `engaged_attackers` and `engaged_targets`. Sorting keeps
            the shape stable from one saved game to the next.
        """
        return {"engaged_attackers": sorted(self.engaged_attackers),
                "engaged_targets": sorted(self.engaged_targets)}

    def restore(self, engaged_attackers: Iterable[str], engaged_targets: Iterable[str]) -> Self:
        """Replaces the register's contents with those of a saved game.

        Args:
            engaged_attackers: The "q,r,s" keys that have attacked.
            engaged_targets: The "q,r,s" keys that have been attacked.

        Returns:
            The register itself.
        """
        self.engaged_attackers.clear()
        self.engaged_attackers.update(engaged_attackers)
        self.engaged_targets.clear()
        self.engaged_targets.update(engaged_targets)
        return self

    def reset(self) -> Self:
        """Empties the register: a new combat phase makes every unit available again.

        A movement phase always separates two combat phases, so the register is already empty when
        the units change squares.

        Returns:
            The register itself.
        """
        self.engaged_attackers.clear()
        self.engaged_targets.clear()
        return self

    def __repr__(self) -> str:
        """The counts of attackers and targets engaged."""
        return (f"CombatRegister({len(self.engaged_attackers)} attackers, "
                f"{len(self.engaged_targets)} targets)")
