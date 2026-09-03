"""The Flask application factory, and the development launch.

`create_app` reads the configuration, hooks persistence and authentication onto the application,
and registers the routes - one blueprint per subject, under `routes/`. Nothing else lives here:
the game state is in `current_game.py`, the players in `players.py`, the log in `logs/`, and the
rules in `tenebrae.engine`, which the routes merely expose. The application's README sets out how
the pieces fit together.

Launch (from the root of the repository):

    python3 -m tenebrae.application.app

then http://127.0.0.1:5000/
"""

from typing import Optional

from flask import Blueprint, Flask

from tenebrae.application.config import Config
from tenebrae.application.persistence import wire_persistence
from tenebrae.application.players import wire_authentication
from tenebrae.application.routes import (authentication, combat, game, images, map_fix, movement,
                                         phase, scenarios, seats, stream, view)

# Every blueprint of `routes/`; the order is that of the README, it changes nothing.
BLUEPRINTS: tuple[Blueprint, ...] = (
    authentication.blueprint, seats.blueprint, view.blueprint, game.blueprint, stream.blueprint,
    movement.blueprint, phase.blueprint, combat.blueprint, map_fix.blueprint,
    scenarios.blueprint, images.blueprint)


def create_app(config: Optional[type] = None) -> Flask:
    """Builds the application: the configuration, persistence, authentication, then the routes.

    Args:
        config: The configuration class; `Config` when omitted.

    Returns:
        The Flask application.

    Raises:
        RuntimeError: If `SECRET_KEY` is missing - a blunt failure at start-up rather than a Flask
            error at the first click on "se connecter".
    """
    application = Flask(__name__)
    application.config.from_object(config or Config)

    if not application.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY missing: without it no session can be signed. Set one in .env - "
            "python3 -c \"import secrets; print(secrets.token_hex(32))\"")

    wire_persistence(application)
    wire_authentication(application)
    for blueprint in BLUEPRINTS:
        application.register_blueprint(blueprint)
    return application


if __name__ == "__main__":
    create_app().run(debug=True)
