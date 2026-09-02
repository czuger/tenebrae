"""Who holds which side at the table: the seating register.

The booklet has two players play, one per side. The rest of the engine knows only sides -
`engine.piece` files each faction under "alliance" or "tenebres", `engine.phase` rotates the
phases from one to the other - and never had to know *who* was playing them. This file holds that
link: it is game, not web, and therefore lives here rather than in the application, which only
concerns itself with opening the session a player presents themselves through.

A player is designated by their Discord identifier, a string. The register knows nothing else
about them: neither nickname nor avatar - that lives in the player repository, and the register
would remain correct if Discord disappeared tomorrow. Nothing here imports Flask, and nothing here
assumes a request: a board game plays perfectly well without a Discord account, and the engine can
go on ignoring it.

    seats = Seats()
    seats.seat("alliance", "100000000000000001")
    seats.holds("100000000000000001", "alliance")   # True
    seats.is_free("tenebres")                       # True

**The register keeps a single invariant: a side has at most one occupant**, and `seat` refuses to
evict one. The social rule - a player holds only one side - is not here but in the route that
seats them, just as the legality of a move is in the server and not in the browser. The separation
is not gratuitous: the test suite seats one and the same player on both sides to play a whole game
by itself, which the route refuses and the register allows.

Like `engine.combat.CombatRegister`, it serialises to a dict and restores from a saved game: who
holds the Alliance is part of the game state, just as much as the active side, and a server
restart must not empty the table.
"""


class Seats:
    """The sides of the game and their occupant, by Discord identifier."""

    __slots__ = ("_by_side",)

    def __init__(self):
        # A free side has no key: "absent" reads better than "null", and it is also what MapField
        # stores.
        self._by_side = {}

    def occupant(self, side):
        """The Discord identifier of whoever holds this side, or `None` if it is free."""
        return self._by_side.get(side)

    def is_free(self, side):
        """Says whether nobody holds this side."""
        return side not in self._by_side

    def sides_of(self, player):
        """The sides this player holds, in the order they were taken - empty if they are watching."""
        return [side for side, occupant in self._by_side.items() if occupant == player]

    def holds(self, player, side):
        """Says whether this player really is the occupant of this side."""
        return player is not None and self._by_side.get(side) == player

    def seat(self, side, player):
        """Seats a player at a free side - or at their own, which changes nothing.

        Raises `ValueError` if the side is held by someone else: a seat is not taken from its
        occupant. That is the only invariant the register defends itself.
        """
        occupant = self._by_side.get(side)
        if occupant is not None and occupant != player:
            raise ValueError(f"side {side} is already held")
        self._by_side[side] = player
        return self

    def free(self, side):
        """Frees the side. A side that was already free makes no fuss."""
        self._by_side.pop(side, None)
        return self

    def clear(self):
        """Clears the whole table - nobody holds anything any more."""
        self._by_side.clear()
        return self

    def to_dict(self):
        """The seats in a serialisable form, ready to join the game state."""
        return {"seats": dict(self._by_side)}

    def restore(self, seats):
        """Replaces the seats with those of a saved game."""
        self._by_side = dict(seats or {})
        return self

    def __repr__(self):
        return f"Seats({self._by_side!r})"
