"""The connection: the link between a Flask session and the engine's player.

This is the only model the application keeps for itself. It does not duplicate
`tenebrae.engine.models.player` - it keeps neither nickname, nor avatar, nor date: it keeps only a
**Discord identifier**, the one the session carries, and goes and re-reads the player from the
repository each time it is asked. A nickname change is thus visible from the very next request,
and there is still a single notion of identity in the project.

What the session carries: `joueur`, the identifier, and for the length of one round trip
`etat_oauth`. **Nothing else, and above all not the access token** - Flask's session cookie is
signed, not encrypted, and its contents can be read by whoever holds it. Those two keys keep their
French names: they live in cookies already in the wild, and renaming them would log everyone out.

None of this is persisted: the connection is not a document, it has no collection. Flask's signed
cookie *is* its storage, and it lives on the player's machine. The class only exists so that this
knowledge - which keys, in which order, with what precaution - sits in one place rather than
scattered across the routes.

    connection = Connection(session, player_repository())
    connection.open(identity)            # after the return from Discord
    connection.player()                  # the player's dict, or None
    connection.close()                   # log out
"""

import secrets

# What the session carries, and nothing more. The stored key names stay as they are: they are
# already in browsers' cookies.
PLAYER_KEY = "joueur"
OAUTH_STATE_KEY = "etat_oauth"

# The length of the OAuth2 anti-CSRF state, in bytes before encoding.
STATE_BYTES = 32


class Connection:
    """A visitor's session, and the engine player it designates.

    It is built at every request that needs one: it is a passing object, with no state of its own
    - everything it knows is in the session it is given and in the repository it questions.

    `session` is Flask's session (or any object offering its interface: a mapping that also
    accepts the `permanent` attribute). `players` is the engine's player repository, the one the
    factory hooks onto the application.
    """

    __slots__ = ("_session", "_players")

    def __init__(self, session, players):
        self._session = session
        self._players = players

    # --- Who is there ---

    @property
    def identifier(self):
        """The Discord identifier the session carries, or `None` if nobody is connected."""
        return self._session.get(PLAYER_KEY)

    def player(self):
        """The engine player designated by the session, or `None`.

        An identifier that no longer matches anyone - base emptied, in-memory repository of a
        restarted server - returns `None` without making a fuss: the visitor becomes anonymous
        again.
        """
        identifier = self.identifier
        return self._players.by_discord_id(identifier) if identifier else None

    # --- Opening and closing ---

    def open(self, identity):
        """Records the player from what Discord has just said about them, and opens the session.

        We start from a fresh session: nothing an anonymous visitor may have left in it survives
        the opening of an account. Returns the recorded player's dict.
        """
        player = self._players.record(identity)
        self._session.clear()
        self._session[PLAYER_KEY] = player["discord_id"]
        self._session.permanent = True
        return player

    def close(self):
        """Closes the session. The seat held is not given up: one comes back to sit in it."""
        self._session.clear()

    # --- The round trip to Discord ---

    def set_oauth_state(self):
        """Draws the single-use state that protects the flow from CSRF, stores it, returns it."""
        state = secrets.token_urlsafe(STATE_BYTES)
        self._session[OAUTH_STATE_KEY] = state
        return state

    def take_oauth_state(self):
        """Removes the state from the session and returns it - `None` if there was none.

        It is **removed**, not read: a replayed return will find nothing left to compare against.
        """
        return self._session.pop(OAUTH_STATE_KEY, None)

    def __repr__(self):
        identifier = self.identifier
        return f"Connection({identifier})" if identifier else "Connection(anonymous)"
