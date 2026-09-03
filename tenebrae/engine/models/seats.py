"""Who holds which side at the table: the seating register.

The booklet has two players play, one per side. The rest of the engine knows only sides -
`tenebrae.engine.piece` files each faction under "alliance" or "tenebres", `tenebrae.engine.phase`
rotates the phases from one to the other - and never had to know *who* was playing them. This file
holds that link: it is game, not web, and therefore lives here rather than in the application.

A player is designated by their Discord identifier, a string. The register knows nothing else
about them - nickname and avatar live in the player repository. Nothing here imports Flask, and
nothing here assumes a request.

    seats = Seats()
    seats.seat("alliance", "100000000000000001")
    seats.holds("100000000000000001", "alliance")   # True
    seats.is_free("tenebres")                       # True

**The register keeps a single invariant: a side has at most one occupant**, and `seat` refuses to
evict one. The social rule - a player holds only one side - is in the route that seats them, not
here: the test suite seats one and the same player on both sides to play a whole game by itself.

Like `tenebrae.engine.combat_register.CombatRegister`, it serialises to a dict and restores from a
saved game: who holds the Alliance is part of the game state.
"""

from collections.abc import Mapping
from typing import Optional, Self


class Seats:
    """The sides of the game and their occupant, by Discord identifier."""

    __slots__ = ("_by_side",)

    _by_side: dict[str, str]

    def __init__(self) -> None:
        """Opens an empty table: every side free."""
        # A free side has no key, which is also what `MapField` stores.
        self._by_side = {}

    def occupant(self, side: str) -> Optional[str]:
        """Reads who holds a side.

        Args:
            side: `"alliance"` or `"tenebres"`.

        Returns:
            The occupant's Discord identifier, or `None` if the side is free.
        """
        return self._by_side.get(side)

    def is_free(self, side: str) -> bool:
        """Says whether nobody holds a side.

        Args:
            side: `"alliance"` or `"tenebres"`.

        Returns:
            True if the side has no occupant.
        """
        return side not in self._by_side

    def sides_of(self, player: str) -> list[str]:
        """Lists the sides a player holds.

        Args:
            player: The Discord identifier.

        Returns:
            The sides, in the order they were taken; empty if the player is watching.
        """
        return [side for side, occupant in self._by_side.items() if occupant == player]

    def holds(self, player: Optional[str], side: str) -> bool:
        """Says whether a player is the occupant of a side.

        Args:
            player: The Discord identifier; `None` holds nothing.
            side: `"alliance"` or `"tenebres"`.

        Returns:
            True if that player sits there.
        """
        return player is not None and self._by_side.get(side) == player

    def seat(self, side: str, player: str) -> Self:
        """Seats a player at a free side - or at their own, which changes nothing.

        Args:
            side: `"alliance"` or `"tenebres"`.
            player: The Discord identifier.

        Returns:
            The table itself.

        Raises:
            ValueError: If the side is held by someone else: a seat is not taken from its
                occupant. That is the only invariant the register defends itself.
        """
        occupant = self._by_side.get(side)
        if occupant is not None and occupant != player:
            raise ValueError(f"side {side} is already held")
        self._by_side[side] = player
        return self

    def free(self, side: str) -> Self:
        """Frees a side; a side that was already free makes no fuss.

        Args:
            side: `"alliance"` or `"tenebres"`.

        Returns:
            The table itself.
        """
        self._by_side.pop(side, None)
        return self

    def clear(self) -> Self:
        """Clears the whole table: nobody holds anything any more.

        Returns:
            The table itself.
        """
        self._by_side.clear()
        return self

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Serialises the seats, ready to join the game state.

        Returns:
            `{"seats": {side: discord_id}}`.
        """
        return {"seats": dict(self._by_side)}

    def restore(self, seats: Optional[Mapping[str, str]]) -> Self:
        """Replaces the seats with those of a saved game.

        Args:
            seats: Side -> Discord identifier; `None` for a game saved before players existed.

        Returns:
            The table itself.
        """
        self._by_side = dict(seats or {})
        return self

    def __repr__(self) -> str:
        """The side -> occupant mapping."""
        return f"Seats({self._by_side!r})"
