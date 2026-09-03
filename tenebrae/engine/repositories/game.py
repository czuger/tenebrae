"""The game repository: the access layer to the saved game.

A repository exchanges **state dicts** - `GameState`, the format of `snapshot_the_game()` in
`tenebrae/application/current_game.py` - never a MongoEngine Document. That is what keeps Mongo out
of the routes: the application imports neither `tenebrae.engine.models` nor `mongoengine`, it
calls `load`, `save` and `new_game`, and that is all.

Two repositories, as for the players: the real one, on MongoDB, and its base-less counterpart that
the test configuration plugs in. That one keeps **nothing** - the game state already lives in the
module globals of `tenebrae/application/current_game.py`, there is simply no need to double it;
that is how it differs from the in-memory player repository, which does keep (see
`tenebrae/engine/repositories/player.py`).
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, TypedDict

if TYPE_CHECKING:
    from tenebrae.engine.models.game import Game


class GameState(TypedDict):
    """The whole game state, as the repositories exchange it: the board, the turn, the combat
    register and the seats, in their serialised forms."""

    scenario: int
    placement: dict[str, str]
    tilts: dict[str, float]
    active_side: str
    phase_type: str
    turn_number: int
    engaged_attackers: list[str]
    engaged_targets: list[str]
    seats: dict[str, str]


class MongoGameRepository:
    """The current game in MongoDB: one document per game, the most recent prevails."""

    def __init__(self) -> None:
        """Binds the repository to the `Game` document.

        The import is done here and not at the top: building a null repository must not require
        mongoengine.
        """
        from tenebrae.engine.models.game import Game
        self._Game = Game

    def _most_recent(self) -> Optional["Game"]:
        """Finds the most recent game, by the model's `ordering`.

        Returns:
            The document, or `None` if the base is empty.
        """
        return self._Game.objects.first()

    def load(self) -> Optional[GameState]:
        """Reads the state of the most recent game.

        Returns:
            The state, or `None` if there is nothing in base yet.
        """
        game = self._most_recent()
        if game is None:
            return None
        return {"scenario": game.scenario,
                "placement": dict(game.placement),
                "tilts": dict(game.tilts),
                "active_side": game.active_side,
                "phase_type": game.phase_type,
                "turn_number": game.turn_number,
                "engaged_attackers": list(game.engaged_attackers),
                "engaged_targets": list(game.engaged_targets),
                "seats": dict(game.seats)}

    def save(self, state: GameState) -> None:
        """Writes the state into the most recent game, creating it if the base is empty.

        Args:
            state: The whole game state.
        """
        game = self._most_recent()
        if game is None:
            self.new_game(state)
            return
        self._fill(game, state).save()

    def new_game(self, state: GameState) -> None:
        """Opens a new game; the previous ones stay in base, as a history.

        Args:
            state: The whole game state.
        """
        game = self._Game(created_at=self._now())
        self._fill(game, state).save()

    def _fill(self, game: "Game", state: GameState) -> "Game":
        """Copies the state into the document, seats included.

        The seats travel in the state dict rather than through methods of their own because the
        whole game is rewritten at every move: seats held on the side would be erased at every save.

        Args:
            game: The document to fill.
            state: The whole game state.

        Returns:
            The same document, `updated_at` refreshed.
        """
        game.scenario = state["scenario"]
        game.placement = state["placement"]
        game.tilts = state["tilts"]
        game.active_side = state["active_side"]
        game.phase_type = state["phase_type"]
        game.turn_number = state["turn_number"]
        game.engaged_attackers = state["engaged_attackers"]
        game.engaged_targets = state["engaged_targets"]
        game.seats = state.get("seats") or {}
        game.updated_at = self._now()
        return game

    @staticmethod
    def _now() -> datetime:
        """The current time, timezone-aware.

        Returns:
            Now, in UTC.
        """
        return datetime.now(timezone.utc)


class NullGameRepository:
    """The repository that keeps nothing: `load` never finds a game, saving does nothing.

    Plugged in by the test configuration - and by `PERSISTENCE=none` -, it gives the application
    its behaviour from before persistence: every load of "/" starts from the scenario.
    """

    def load(self) -> Optional[GameState]:
        """Never finds a game.

        Returns:
            `None`.
        """
        return None

    def save(self, state: GameState) -> None:
        """Keeps nothing.

        Args:
            state: Ignored.
        """

    def new_game(self, state: GameState) -> None:
        """Keeps nothing.

        Args:
            state: Ignored.
        """
