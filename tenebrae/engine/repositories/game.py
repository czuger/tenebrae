"""The game repository: the access layer to the saved games.

A repository exchanges **state dicts** - `GameState`, the format of `snapshot_the_game()` in
`tenebrae/application/current_game.py` - never a MongoEngine Document. That is what keeps Mongo out
of the routes: the application imports neither `tenebrae.engine.models` nor `mongoengine`, it
calls `games`, `load`, `save` and `new_game`, and that is all.

**A game is designated by its identifier**, the string form of its document's `_id`. `GameState`
does not carry it: a state dict is what a game *is*, not which row holds it. The identifier
therefore travels beside the state - `load(identifier)`, `save(identifier, state)` - and
`GameSummary` carries it for the landing page, which lists games without playing any of them.

`save` writes into the document it is given and nowhere else. It used to write into the most recent
one, which was true while the server only ever played that one; as soon as an older game can be
opened, writing into the most recent would land one game's moves in another.
"""

from datetime import datetime, timezone
from typing import Optional, TypedDict

from bson.errors import InvalidId
from mongoengine.errors import ValidationError

from tenebrae.engine.casualties import Casualty as CasualtyEntry
from tenebrae.engine.models.game import Casualty, Game


class GameState(TypedDict):
    """The whole game state, as the repositories exchange it: the board, the turn, the combat
    register, the units removed from play and the seats, in their serialised forms."""

    scenario: int
    placement: dict[str, str]
    tilts: dict[str, float]
    active_side: str
    phase_type: str
    turn_number: int
    engaged_attackers: list[str]
    engaged_targets: list[str]
    casualties: list[CasualtyEntry]
    seats: dict[str, str]
    over: bool
    winner: Optional[str]


class GameSummary(TypedDict):
    """One saved game as a list shows it: enough to recognise it, not enough to play it.

    The placement is not here - a list of games has no board to draw -, only how many units are
    still standing on it.
    """

    identifier: str
    scenario: int
    turn_number: int
    active_side: str
    phase_type: str
    seats: dict[str, str]
    over: bool
    winner: Optional[str]
    units: int
    created_at: datetime
    updated_at: datetime


class MongoGameRepository:
    """The saved games in MongoDB: one document per game, each played by its identifier."""

    def _most_recent(self) -> Optional[Game]:
        """Finds the most recent game, by the model's `ordering`.

        Returns:
            The document, or `None` if the base is empty.
        """
        return Game.objects.first()

    def _by_identifier(self, identifier: str) -> Optional[Game]:
        """Finds one game by the string form of its `_id`.

        Args:
            identifier: What `games()` and `new_game()` give out.

        Returns:
            The document, or `None` - a game that has gone, and an identifier that was never one:
            an address typed by hand is a miss, not a 500.
        """
        try:
            return Game.objects(pk=identifier).first()
        except (ValidationError, InvalidId):
            return None

    def games(self) -> list[GameSummary]:
        """Summarises every saved game, most recently played first.

        Returns:
            One entry per document, in the model's `ordering`; empty on an empty base.
        """
        return [self._summary_of(game) for game in Game.objects]

    def most_recent(self) -> Optional[tuple[str, GameState]]:
        """Reads the game played most recently, and says which one it is.

        The identifier comes back with the state because the caller needs both and one query
        holds them: what to play, and which document to save into.

        Returns:
            The identifier and the state, or `None` on an empty base.
        """
        game = self._most_recent()
        return None if game is None else (str(game.id), self._state_of(game))

    def load(self, identifier: Optional[str] = None) -> Optional[GameState]:
        """Reads the state of one saved game, the most recent one by default.

        Args:
            identifier: The game to read; omitted, the most recently played.

        Returns:
            The state, or `None` if there is no such game - an empty base, or an identifier that
            names nothing.
        """
        game = self._by_identifier(identifier) if identifier is not None else self._most_recent()
        return None if game is None else self._state_of(game)

    def _state_of(self, game: Game) -> GameState:
        """Reads a document into the state dict the engine and the routes exchange.

        Args:
            game: The document.

        Returns:
            The whole game state.
        """
        return {"scenario": game.scenario,
                "placement": dict(game.placement),
                "tilts": dict(game.tilts),
                "active_side": game.active_side,
                "phase_type": game.phase_type,
                "turn_number": game.turn_number,
                "engaged_attackers": list(game.engaged_attackers),
                "engaged_targets": list(game.engaged_targets),
                "casualties": [_entry_of(loss) for loss in game.casualties],
                "seats": dict(game.seats),
                "over": bool(game.over),
                "winner": game.winner}

    def _summary_of(self, game: Game) -> GameSummary:
        """Reads a document into the summary a list of games shows.

        Args:
            game: The document.

        Returns:
            Its identity, where it stands, and how many units are left on its board.
        """
        return {"identifier": str(game.id),
                "scenario": game.scenario,
                "turn_number": game.turn_number,
                "active_side": game.active_side,
                "phase_type": game.phase_type,
                "seats": dict(game.seats),
                "over": bool(game.over),
                "winner": game.winner,
                "units": len(game.placement),
                "created_at": _in_utc(game.created_at),
                "updated_at": _in_utc(game.updated_at)}

    def save(self, identifier: Optional[str], state: GameState) -> str:
        """Writes the state into the game it names, and into no other.

        A board played on with no game behind it - no identifier, or one whose document has gone -
        opens one at its first move, which is what an empty base did before.

        Args:
            identifier: The game to write into, or `None`.
            state: The whole game state.

        Returns:
            The identifier written into: the one given, or the new game's.
        """
        game = self._by_identifier(identifier) if identifier is not None else None
        if game is None:
            return self.new_game(state)
        return str(self._fill(game, state).save().id)

    def new_game(self, state: GameState) -> str:
        """Opens a new game; the previous ones stay in base, as a history.

        Args:
            state: The whole game state.

        Returns:
            The new game's identifier.
        """
        game = Game(created_at=self._now())
        return str(self._fill(game, state).save().id)

    def _fill(self, game: Game, state: GameState) -> Game:
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
        game.casualties = [Casualty(**loss) for loss in state.get("casualties") or []]
        game.seats = state.get("seats") or {}
        game.over = bool(state.get("over"))
        game.winner = state.get("winner")
        game.updated_at = self._now()
        return game

    @staticmethod
    def _now() -> datetime:
        """The current time, timezone-aware.

        Returns:
            Now, in UTC.
        """
        return datetime.now(timezone.utc)


def _in_utc(moment: datetime) -> datetime:
    """Puts a time read back from MongoDB in the timezone it was written in.

    `_now()` writes an aware time; the driver gives it back **naive**, and a naive time serialised
    for a browser reads as that browser's local time - a game played at 18:06 UTC shown as 18:06 in
    Paris, two hours out. The offset is put back here, where the fact that it is UTC is known,
    rather than guessed at the far end.

    Args:
        moment: The time as the base gave it.

    Returns:
        The same instant, marked UTC.
    """
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def _entry_of(loss: Casualty) -> CasualtyEntry:
    """Reads one casualty back into the plain dict the engine's register holds.

    Args:
        loss: The embedded document.

    Returns:
        Its four fields, an absent `taken_by` read as an empty side.
    """
    return {"square": loss.square, "piece": loss.piece,
            "side": loss.side, "taken_by": loss.taken_by or ""}
