"""How a turn of Ave Tenebrae unfolds: a state machine of the phases.

The booklet (`tenebrae/game_box/ave_tenebrae_regles_en.md`, "Game phases") fixes the order: each
player goes through movement, magic then combat, and play passes to the next player, round and
round. The engine knew nothing of this until now - a scenario was only a starting position.

`Turn` holds the active side and the current phase type, and knows how to step to the next one.
The magic phase is not implemented: `advance()` steps over it, it is never the current one.

The phase values ("mouvement", "magie", "combat") and the side values are those of the saved game
and of the French interface: they stay in French, only the code around them is English.
"""

MOVEMENT, MAGIC, COMBAT = "mouvement", "magie", "combat"

# The order of the phases of a single player. Magic appears there so it can be skipped at the
# right moment.
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

    def __init__(self, sides, names=None):
        self._sides = tuple(sides)
        self._names = dict(names or {})
        # The full sequence of a turn: each side, each phase type, in order.
        self._i = 0
        self.number = 1

    @property
    def _sequence(self):
        return [(side, kind) for side in self._sides for kind in ORDER]

    @property
    def active_side(self):
        """The side whose phase it is - "alliance" or "tenebres"."""
        return self._sequence[self._i][0]

    @property
    def phase_type(self):
        """The type of the current phase: "mouvement" or "combat" (never "magie")."""
        return self._sequence[self._i][1]

    @property
    def active_army(self):
        """The readable name of the army that plays - "Nains", "Orques" -, failing that its side."""
        return self._names.get(self.active_side, self.active_side)

    @property
    def label(self):
        """What the interface displays: "Phase de mouvement - Nains"."""
        return f"{LABELS[self.phase_type]} — {self.active_army}"

    def restart(self):
        """Brings the game back to the first phase of the first turn."""
        self._i = 0
        self.number = 1
        return self

    def restore(self, side, phase_type, number):
        """Brings the turn back to that phase, as a saved game kept it.

        The `(side, type)` pair is enough to find the position in the sequence - that is what
        `to_dict` delivers. Magic is refused: `advance()` always steps over it, it is never the
        current phase, and a saved game citing it does not come from here.
        """
        if phase_type == MAGIC:
            raise ValueError("the magic phase is never the current one")
        self._i = self._sequence.index((side, phase_type))
        self.number = number
        return self

    def advance(self):
        """Steps to the next phase, stepping over magic and counting the turns."""
        sequence = self._sequence
        self._i += 1
        if self._i >= len(sequence):
            self._i = 0
            self.number += 1
        if sequence[self._i][1] == MAGIC:
            self.advance()
        return self

    def allows_movement(self, side):
        """Says whether `side` may move its units right now."""
        return self.phase_type == MOVEMENT and side == self.active_side

    def allows_combat(self, side):
        """Says whether `side` may declare a combat right now."""
        return self.phase_type == COMBAT and side == self.active_side

    def to_dict(self):
        """The current phase in a form ready for the browser's JSON."""
        return {"side": self.active_side, "type": self.phase_type,
                "army": self.active_army, "label": self.label, "number": self.number}

    def __repr__(self):
        return f"Turn({self.number}, {self.label!r})"
