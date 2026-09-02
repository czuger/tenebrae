"""The application's models, **one file per model**.

There are two, and not one more: the application only models what is **not** the game. Everything
else - the game, the player, the seating table - lives in `engine/models/`.

- `connection.py`: the link between a Flask session and the engine's player. Nothing of it is
  persisted, Flask's signed cookie *is* its storage;
- `view.py`: where a player was on the map, and how close they had zoomed in. A Mongo document,
  written by `repositories/view.py`. It is here and not in the engine because the engine does not
  know that an image, pixels or a window exist: a game plays from an interpreter, where zoom means
  nothing.

The direction of the dependency never reverses: both designate the engine's player by their
Discord identifier, and the engine imports nothing from here.

    from models.connection import Connection
    from models.view import View
"""
