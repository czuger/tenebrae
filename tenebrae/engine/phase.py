"""How a turn of Ave Tenebrae unfolds: a state machine of the phases.

The booklet (`tenebrae/game_box/ave_tenebrae_regles_en.md`, "Game phases") fixes the order: each
player goes through movement, magic then combat, and play passes to the next player, round and
round.

`Turn` holds the active side and the current phase type, and knows how to step to the next one.
The magic phase is not implemented: `advance()` steps over it, it is never the current one.

The phase values ("mouvement", "magie", "combat") and the side values are those of the saved game
and of the French interface: they stay in French, only the code around them is English.
"""

from collections.abc import Iterable, Mapping
from typing import Optional, Self

MOVEMENT, MAGIC, COMBAT = "mouvement", "magie", "combat"

# The phases of a single player, magic included so that it can be skipped at the right moment.
ORDER = (MOVEMENT, MAGIC, COMBAT)

# What the interface displays. French, like everything the player reads.
LABELS = {MOVEMENT: "Phase de mouvement", MAGIC: "Phase de magie", COMBAT: "Phase de combat"}


class Turn:
    """The current phase of a game: which side plays, and at what.

        turn = Turn(("alliance", "tenebres"), {"alliance": "Nains", "tenebres": "Orques"})
        turn.label            # "Phase de mouvement - Nains"
        turn.advance()        # steps to combat (magic is skipped)
    """

    __slots__ = ("_sides", "_names", "_i", "number")

    _sides: tuple[str, ...]
    _names: dict[str, str]
    _i: int
    number: int

    def __init__(self, sides: Iterable[str], names: Optional[Mapping[str, str]] = None) -> None:
        """Opens the first phase of the first turn.

        Args:
            sides: The sides in player order, e.g. `("alliance", "tenebres")`.
            names: Side -> readable army name, e.g. `{"alliance": "Nains"}`.
        """
        self.set_up(sides, names)

    def set_up(self, sides: Iterable[str], names: Optional[Mapping[str, str]] = None) -> Self:
        """Puts the turn on another set of sides, back at the first phase of the first turn.

        What a game changing scenario goes through: the sides and the army names are those of the
        new set-up, and nothing of the previous game's progress is kept.

        Args:
            sides: The sides in player order.
            names: Side -> readable army name.

        Returns:
            The turn itself.
        """
        self._sides = tuple(sides)
        self._names = dict(names or {})
        return self.restart()

    @property
    def _sequence(self) -> list[tuple[str, str]]:
        """The full sequence of a turn: each side, each phase type, in order."""
        return [(side, kind) for side in self._sides for kind in ORDER]

    @property
    def active_side(self) -> str:
        """The side whose phase it is - "alliance" or "tenebres"."""
        return self._sequence[self._i][0]

    @property
    def phase_type(self) -> str:
        """The type of the current phase: "mouvement" or "combat" (never "magie")."""
        return self._sequence[self._i][1]

    @property
    def active_army(self) -> str:
        """The readable name of the army that plays - "Nains", "Orques" -, failing that its side."""
        return self._names.get(self.active_side, self.active_side)

    @property
    def label(self) -> str:
        """What the interface displays: "Phase de mouvement — Nains"."""
        return f"{LABELS[self.phase_type]} — {self.active_army}"

    def restart(self) -> Self:
        """Brings the game back to the first phase of the first turn.

        Returns:
            The turn itself.
        """
        self._i = 0
        self.number = 1
        return self

    def restore(self, side: str, phase_type: str, number: int) -> Self:
        """Brings the turn back to a phase kept by a saved game.

        Args:
            side: The active side.
            phase_type: `MOVEMENT` or `COMBAT`.
            number: The turn number.

        Returns:
            The turn itself.

        Raises:
            ValueError: If `phase_type` is `MAGIC`, which is never the current phase.
        """
        if phase_type == MAGIC:
            raise ValueError("the magic phase is never the current one")
        self._i = self._sequence.index((side, phase_type))
        self.number = number
        return self

    def advance(self) -> Self:
        """Steps to the next phase, stepping over magic and counting the turns.

        Returns:
            The turn itself.
        """
        sequence = self._sequence
        self._i += 1
        if self._i >= len(sequence):
            self._i = 0
            self.number += 1
        if sequence[self._i][1] == MAGIC:
            self.advance()
        return self

    def allows_movement(self, side: str) -> bool:
        """Says whether a side may move its units right now.

        Args:
            side: The side asking.

        Returns:
            True during that side's movement phase only.
        """
        return self.phase_type == MOVEMENT and side == self.active_side

    def allows_combat(self, side: str) -> bool:
        """Says whether a side may declare a combat right now.

        Args:
            side: The side asking.

        Returns:
            True during that side's combat phase only.
        """
        return self.phase_type == COMBAT and side == self.active_side

    def to_dict(self) -> dict[str, str | int]:
        """Serialises the current phase for the browser's JSON.

        Returns:
            The side, type, army, label and turn number.
        """
        return {"side": self.active_side, "type": self.phase_type,
                "army": self.active_army, "label": self.label, "number": self.number}

    def __repr__(self) -> str:
        """The turn number and the phase label."""
        return f"Turn({self.number}, {self.label!r})"
