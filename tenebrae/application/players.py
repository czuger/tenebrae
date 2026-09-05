"""The players: who is behind the request, and who holds what at the table.

The game is played by two, one player per side, identified by Discord. The routes never touch
`session` themselves: `the_connection()` designates the engine's player by their Discord identifier
(`models/connection.py`) and re-reads them from the repository at every request. The identity
comes from Discord - `discord_client.py` for the OAuth2 flow - or from the fake client the test
configuration plugs in (`wire_authentication`).

The table (`table_for`) is the one part of what the browser receives that is composed per
spectator: whether they are logged in, under what nickname, which sides they hold. The guards that
turn the anonymous, the unseated or the out-of-turn away from a route are in
`routes/authorization.py`.
"""

from typing import Optional

from flask import Flask, abort, current_app, g, session

from tenebrae.application import current_game
from tenebrae.application.current_game import SEATS
from tenebrae.application.discord_client import DiscordClient, FakeDiscordClient
from tenebrae.application.models.connection import Connection
from tenebrae.application.persistence import player_repository
from tenebrae.engine import ai
from tenebrae.engine.repositories.player import PlayerRecord

# What the factory hooks onto the application, in either branch of its configuration.
IdentityClient = DiscordClient | FakeDiscordClient


def wire_authentication(application: Flask) -> None:
    """Hooks the identity client onto the application, according to `AUTHENTICATION`.

    Args:
        application: The application being built.
    """
    if application.config["AUTHENTICATION"] == "discord":
        application.extensions["discord"] = DiscordClient(
            application.config["DISCORD_CLIENT_ID"],
            application.config["DISCORD_CLIENT_SECRET"],
            application.config["DISCORD_REDIRECT_URI"])
    else:
        application.extensions["discord"] = FakeDiscordClient()


def discord_client() -> IdentityClient:
    """The current application's identity client.

    Returns:
        Whichever `wire_authentication` hooked on.
    """
    return current_app.extensions["discord"]


def the_connection() -> Connection:
    """Builds the current request's connection: the session, and the repository to re-read from.

    Returns:
        A passing object, with no state of its own.
    """
    return Connection(session, player_repository())


def current_player() -> Optional[PlayerRecord]:
    """Reads the session's player, once per request.

    Kept on `g`: several decorators ask for it within a single request.

    Returns:
        The player, or `None` for an anonymous visitor.
    """
    if "player" not in g:
        g.player = the_connection().player()
    return g.player


def logged_in_player() -> PlayerRecord:
    """Reads the session's player where a route requires one.

    The routes behind `login_required` call this rather than `current_player`: the decorator has
    already turned the anonymous visitor away, with its own message.

    Returns:
        The player; 401 if there is none.
    """
    player = current_player()
    if player is None:
        abort(401, "no player logged in")
    return player


def is_administrator(player: Optional[PlayerRecord]) -> bool:
    """Says whether a player may use the administration pages - fix the map, compose a scenario.

    Args:
        player: The player, or `None` for an anonymous visitor.

    Returns:
        True if their identifier is in `ADMINISTRATORS` (see `config.py`).
    """
    return player is not None and player["discord_id"] in current_app.config["ADMINISTRATORS"]


def nickname_of(occupant: Optional[str]) -> Optional[str]:
    """The nickname behind a Discord identifier held at a table.

    Args:
        occupant: The identifier, or `None` for a free side.

    Returns:
        The nickname; the AI's name for the AI, which is not in base and only has one; `None` for
        a free side as for an identifier no account carries any more.
    """
    if occupant is None:
        return None
    if occupant == ai.AI_PLAYER:
        return ai.AI_NAME
    seated = player_repository().by_discord_id(occupant)
    return seated["nickname"] if seated else None


def the_visitor() -> dict[str, object]:
    """Who is looking, and nothing of what they are looking at.

    What a page that shows no game needs of the session - the landing page, which lists games
    without playing any of them, and therefore has no table of its own to speak of.

    Returns:
        `connected`, `nickname`, `avatar` and `administrator` for the session's player.
    """
    return visitor_for(current_player())


def visitor_for(player: Optional[PlayerRecord]) -> dict[str, object]:
    """Serialises one spectator: who they are, not what they hold.

    Args:
        player: The spectator, or `None` for an anonymous visitor.

    Returns:
        `connected`, `nickname`, `avatar`, `administrator`.
    """
    return {
        "connected": player is not None,
        "nickname": player["nickname"] if player else None,
        "avatar": player["avatar"] if player else None,
        "administrator": is_administrator(player),
    }


def the_table() -> dict[str, object]:
    """Serialises the table as the current request's visitor sees it.

    Returns:
        What `table_for` gives for the session's player.
    """
    return table_for(current_player())


def table_for(player: Optional[PlayerRecord]) -> dict[str, object]:
    """Serialises who is watching and who holds what, for one spectator.

    Discord identifiers are not part of it: the browser only needs nicknames and avatars. The
    player is passed rather than read from the session because the SSE stream composes this
    outside any request.

    The sides and the armies are those of **the game the process is playing** (`current_game`), not
    of any game one might be looking at: a page that shows a game is a page the process is on.

    Args:
        player: The spectator, or `None` for an anonymous visitor.

    Returns:
        `connected`, `nickname`, `avatar`, `administrator`, `sides`, `armies`, `seats`.
    """
    return visitor_for(player) | {
        # A list: ordinarily zero or one side, but the test suite seats one player on both.
        "sides": SEATS.sides_of(player["discord_id"]) if player else [],
        "armies": {army["camp"]: army["armee"] for army in current_game.SCENARIO.armies},
        "seats": {side: nickname_of(SEATS.occupant(side))
                  for side in current_game.SCENARIO.sides},
    }
