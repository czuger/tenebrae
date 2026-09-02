"""The connection model: what the session carries, and the engine player it designates.

These engine bear on the class alone, with no request and no route - as
`tenebrae/engine/engine/test_seats.py` does for the seating register. `Connection` only asks for a
session (any mapping that also accepts the `permanent` attribute: Flask's real session is one) and a
player repository; we give it here the engine's in-memory repository, which is the engine' real
repository.

What is checked comes down to three points, and they are the class's three reasons for existing:
the session carries **only** the identifier, the player is **re-read** from the repository at every
request, and the OAuth2 state is **removed** from the session as soon as it is taken back.
"""

import pytest

from tenebrae.application.discord_client import DEFAULT_IDENTITY
from tenebrae.engine.repositories.player import InMemoryPlayerRepository
from tenebrae.application.models.connection import OAUTH_STATE_KEY, PLAYER_KEY, Connection


class FakeSession(dict):
    """A mapping that accepts `permanent`, like Flask's session."""

    permanent = False


@pytest.fixture
def players():
    return InMemoryPlayerRepository()


@pytest.fixture
def session():
    return FakeSession()


@pytest.fixture
def connection(session, players):
    return Connection(session, players)


class TestOpening:

    def test_opening_records_the_player_and_returns_their_dict(self, connection, players):
        player = connection.open(DEFAULT_IDENTITY)
        assert player["nickname"] == DEFAULT_IDENTITY["nickname"]
        assert players.by_discord_id(DEFAULT_IDENTITY["discord_id"]) == player

    def test_the_session_carries_only_the_identifier(self, connection, session):
        """No nickname, no avatar, no token: Flask's cookie is signed, not encrypted. And the
        session is permanent, so the account outlives the tab."""
        connection.open(DEFAULT_IDENTITY)
        assert dict(session) == {PLAYER_KEY: DEFAULT_IDENTITY["discord_id"]}
        assert session.permanent is True

    def test_opening_starts_from_a_fresh_session(self, connection, session):
        """Nothing an anonymous visitor may have left in it survives the opening of an account."""
        session["anonymous-trace"] = "to be thrown away"
        connection.open(DEFAULT_IDENTITY)
        assert "anonymous-trace" not in session


class TestTheDesignatedPlayer:

    def test_an_empty_session_designates_nobody(self, connection):
        assert connection.identifier is None
        assert connection.player() is None

    def test_the_player_is_re_read_from_the_repository_every_time(self, connection, players):
        """The nickname is not copied into the session: a change shows from the next request on."""
        connection.open(DEFAULT_IDENTITY)
        players.record(DEFAULT_IDENTITY | {"nickname": "Renamed"})
        assert connection.player()["nickname"] == "Renamed"

    def test_an_unknown_identifier_becomes_anonymous_again(self, session, players):
        """Base emptied, in-memory repository of a restarted server: the visitor becomes anonymous
        again."""
        session[PLAYER_KEY] = "100000000000000009"
        connection = Connection(session, players)
        assert connection.identifier == "100000000000000009"
        assert connection.player() is None

    def test_closing_leaves_nothing_in_the_session(self, connection, session):
        connection.open(DEFAULT_IDENTITY)
        connection.close()
        assert dict(session) == {}
        assert connection.player() is None


class TestOAuthState:

    def test_setting_stores_the_state_in_the_session_and_returns_it(self, connection, session):
        state = connection.set_oauth_state()
        assert session[OAUTH_STATE_KEY] == state
        assert len(state) >= 32

    def test_two_states_do_not_look_alike(self, connection):
        assert connection.set_oauth_state() != connection.set_oauth_state()

    def test_taking_removes_the_state_from_the_session(self, connection, session):
        """A replayed return finds nothing left to compare against - the second take, like a take
        on a session that never carried a state, gives None."""
        state = connection.set_oauth_state()
        assert connection.take_oauth_state() == state
        assert OAUTH_STATE_KEY not in session
        assert connection.take_oauth_state() is None
