"""The connection: the link between a Flask session and the engine's player.

This is the only model the application keeps for itself. It does not duplicate
`tenebrae.engine.models.player` - it keeps neither nickname, nor avatar, nor date: it keeps only a
**Discord identifier**, the one the session carries, and re-reads the player from the repository
each time it is asked. A nickname change is thus visible from the very next request.

What the session carries: `joueur`, the identifier, and for the length of one round trip
`etat_oauth`. **Nothing else, and above all not the access token** - Flask's session cookie is
signed, not encrypted. Those two keys keep their French names: they live in cookies already in the
wild, and renaming them would log everyone out.

None of this is persisted: Flask's signed cookie *is* its storage. The class only exists so that
this knowledge - which keys, in which order, with what precaution - sits in one place.

    connection = Connection(session, player_repository())
    connection.open(identity)            # after the return from Discord
    connection.player()                  # the player's dict, or None
    connection.close()                   # log out
"""

import secrets
from typing import Optional

from flask.sessions import SessionMixin

from tenebrae.engine.repositories.player import MongoPlayerRepository, PlayerRecord

# What the session carries, and nothing more. Already in browsers' cookies: not renamed.
PLAYER_KEY = "joueur"
OAUTH_STATE_KEY = "etat_oauth"

# The length of the OAuth2 anti-CSRF state, in bytes before encoding.
STATE_BYTES = 32


class Connection:
    """A visitor's session, and the engine player it designates.

    A passing object, built at every request that needs one: everything it knows is in the session
    it is given and in the repository it questions.
    """

    __slots__ = ("_session", "_players")

    def __init__(self, session: SessionMixin, players: MongoPlayerRepository) -> None:
        """Binds the session to the repository the player is re-read from.

        Args:
            session: Flask's session, or any mapping that also accepts the `permanent` attribute.
            players: The engine's player repository, the one the factory hooks onto the
                application.
        """
        self._session = session
        self._players = players

    @property
    def identifier(self) -> Optional[str]:
        """The Discord identifier the session carries, or `None` if nobody is connected."""
        return self._session.get(PLAYER_KEY)

    def player(self) -> Optional[PlayerRecord]:
        """Re-reads the player the session designates.

        Returns:
            The player, or `None` for an anonymous visitor - or an identifier that no longer
            matches anyone (base emptied, in-memory repository of a restarted server).
        """
        identifier = self.identifier
        return self._players.by_discord_id(identifier) if identifier else None

    def open(self, identity: PlayerRecord) -> PlayerRecord:
        """Records the player from what Discord has just said about them, and opens the session.

        The session is cleared first: nothing an anonymous visitor may have left in it survives the
        opening of an account.

        Args:
            identity: What Discord reported.

        Returns:
            The recorded player.
        """
        player = self._players.record(identity)
        self._session.clear()
        self._session[PLAYER_KEY] = player["discord_id"]
        self._session.permanent = True
        return player

    def close(self) -> None:
        """Closes the session. The seat held is not given up: one comes back to sit in it."""
        self._session.clear()

    def set_oauth_state(self) -> str:
        """Draws the single-use state that protects the flow from CSRF, and stores it.

        Returns:
            The state, to send to Discord.
        """
        state = secrets.token_urlsafe(STATE_BYTES)
        self._session[OAUTH_STATE_KEY] = state
        return state

    def take_oauth_state(self) -> Optional[str]:
        """Removes the state from the session: a replayed return finds nothing to compare against.

        Returns:
            The state, or `None` if there was none.
        """
        return self._session.pop(OAUTH_STATE_KEY, None)

    def __repr__(self) -> str:
        """The identifier carried, or "anonymous"."""
        identifier = self.identifier
        return f"Connection({identifier})" if identifier else "Connection(anonymous)"
