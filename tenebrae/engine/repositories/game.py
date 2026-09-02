"""The game repository: the access layer to the saved game.

A repository exchanges **state dicts** - the format of `snapshot_the_game()` in
`application/app.py`: `{scenario, placement, tilts, active_side, phase_type, turn_number,
engaged_attackers, engaged_targets, seats}` - never a MongoEngine Document. That is what keeps
Mongo out of the routes: `app.py` imports neither `engine.models` nor `mongoengine`, it calls
`load`, `save` and `new_game`, and that is all.

Two repositories, as for the players: the real one, on MongoDB, and its base-less counterpart that
the test configuration plugs in. That one keeps **nothing** - the game state already lives in the
module globals of `app.py`, there is simply no need to double it; that is how it differs from the
in-memory player repository, which does keep (see `engine/repositories/player.py`).
"""

from datetime import datetime, timezone


class MongoGameRepository:
    """The current game in MongoDB: one document per game, the most recent prevails."""

    def __init__(self):
        # The import is done here and not at the top: building a null repository must not require
        # mongoengine - the Mongo-less engine import this module too.
        from tenebrae.engine.models.game import Game
        self._Game = Game

    def _most_recent(self):
        return self._Game.objects.first()  # the model's `ordering`: most recent first

    def load(self):
        """The state of the most recent game, or `None` if there is nothing in base yet."""
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

    def save(self, state):
        """Writes the state into the most recent game - creates it if the base is empty."""
        game = self._most_recent()
        if game is None:
            return self.new_game(state)
        self._fill(game, state).save()

    def new_game(self, state):
        """Opens a new game; the previous ones stay in base, as a history."""
        game = self._Game(created_at=self._now())
        self._fill(game, state).save()

    def _fill(self, game, state):
        game.scenario = state["scenario"]
        game.placement = state["placement"]
        game.tilts = state["tilts"]
        game.active_side = state["active_side"]
        game.phase_type = state["phase_type"]
        game.turn_number = state["turn_number"]
        game.engaged_attackers = state["engaged_attackers"]
        game.engaged_targets = state["engaged_targets"]
        # The seats are rewritten like the rest. That is why they travel in the state dict rather
        # than through methods of their own: `_fill` rewrites the whole game at every move, and
        # seats held on the side would be erased at every save.
        game.seats = state.get("seats") or {}
        game.updated_at = self._now()
        return game

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)


class NullGameRepository:
    """The repository that keeps nothing: `load` never finds a game, saving does nothing. Plugged
    in by the test configuration - and by `PERSISTENCE=none` -, it gives the application back its
    behaviour from before persistence: every load of "/" starts from the scenario."""

    def load(self):
        return None

    def save(self, state):
        pass

    def new_game(self, state):
        pass
