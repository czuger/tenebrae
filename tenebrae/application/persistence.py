"""What the factory hooks onto the application for persistence, and how the routes reach it.

The three repositories - the game's, the players', the views' - are chosen by `PERSISTENCE` at
start-up (`wire_persistence`) and read back from `current_app.extensions` at every request
(`game_repository`, `player_repository`, `view_repository`). The routes never see the base: they
speak to the repositories in state dicts, and `PERSISTENCE=none` - the test configuration - plugs
in counterparts that keep nothing, or keep in memory (see the application's README, "Game
persistence").
"""

from flask import Flask, current_app

from tenebrae.application.models.connection import PlayerRepository
from tenebrae.application.repositories.view import InMemoryViewRepository, MongoViewRepository
from tenebrae.engine.repositories.game import MongoGameRepository, NullGameRepository
from tenebrae.engine.repositories.player import InMemoryPlayerRepository, MongoPlayerRepository

# What the factory hooks onto the application, in either branch of its configuration.
GameRepository = MongoGameRepository | NullGameRepository
ViewRepository = MongoViewRepository | InMemoryViewRepository


def wire_persistence(application: Flask) -> None:
    """Hooks the three repositories onto the application, according to `PERSISTENCE`.

    The extension is imported here, and not at the top of the file: it is the only module that
    imports mongoengine at load, and an application without persistence builds without it.

    Args:
        application: The application being built.
    """
    games: GameRepository
    players: PlayerRepository
    views: ViewRepository
    if application.config["PERSISTENCE"] == "mongo":
        from tenebrae.application.extensions import db
        db.init_app(application)  # before the routes, and only once: the instance is shared
        games, players, views = (MongoGameRepository(), MongoPlayerRepository(),
                                 MongoViewRepository())
    else:
        games, players, views = (NullGameRepository(), InMemoryPlayerRepository(),
                                 InMemoryViewRepository())
    application.extensions["game_repository"] = games
    application.extensions["player_repository"] = players
    application.extensions["view_repository"] = views


def game_repository() -> GameRepository:
    """The current application's game repository.

    Returns:
        Whichever `wire_persistence` hooked on.
    """
    return current_app.extensions["game_repository"]


def player_repository() -> PlayerRepository:
    """The current application's player repository.

    Returns:
        Whichever `wire_persistence` hooked on.
    """
    return current_app.extensions["player_repository"]


def view_repository() -> ViewRepository:
    """The current application's map view repository (see `models/view.py`).

    Returns:
        Whichever `wire_persistence` hooked on.
    """
    return current_app.extensions["view_repository"]
