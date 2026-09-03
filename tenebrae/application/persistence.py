"""What the factory hooks onto the application for persistence, and how the routes reach it.

The three repositories - the game's, the players', the views' - are opened on the MongoDB that
`MONGODB_SETTINGS` names at start-up (`wire_persistence`) and read back from
`current_app.extensions` at every request (`game_repository`, `player_repository`,
`view_repository`). The routes never see the base: they speak to the repositories in state dicts
(see the application's README, "Game persistence").
"""

from flask import Flask, current_app

from tenebrae.application.extensions import db
from tenebrae.application.repositories.view import MongoViewRepository
from tenebrae.engine.repositories.game import MongoGameRepository
from tenebrae.engine.repositories.player import MongoPlayerRepository


def wire_persistence(application: Flask) -> None:
    """Opens the MongoDB connection and hooks the three repositories onto the application.

    Args:
        application: The application being built.
    """
    db.init_app(application)  # before the routes, and only once: the instance is shared
    application.extensions["game_repository"] = MongoGameRepository()
    application.extensions["player_repository"] = MongoPlayerRepository()
    application.extensions["view_repository"] = MongoViewRepository()


def game_repository() -> MongoGameRepository:
    """The current application's game repository.

    Returns:
        The one `wire_persistence` hooked on.
    """
    return current_app.extensions["game_repository"]


def player_repository() -> MongoPlayerRepository:
    """The current application's player repository.

    Returns:
        The one `wire_persistence` hooked on.
    """
    return current_app.extensions["player_repository"]


def view_repository() -> MongoViewRepository:
    """The current application's map view repository (see `models/view.py`).

    Returns:
        The one `wire_persistence` hooked on.
    """
    return current_app.extensions["view_repository"]
