"""Shared fixtures: a logged-in Flask client, a test player, and a real server for the browser."""

import threading

import pytest
from werkzeug.serving import make_server

from tenebrae.application.app import create_app
from tenebrae.application.current_game import BOARD, REGISTER, SCENARIO, SEATS, TURN
from tenebrae.application.config import TestingConfig
from tenebrae.application.discord_client import DEFAULT_IDENTITY


@pytest.fixture(scope="session")
def application():
    """The test application, built once by the factory.

    A single instance for the whole session: the Flask client and the browser engine' server must
    speak to the same object. The test configuration unplugs persistence (null repository) - the
    game state stays in `current_game`'s module globals, which the fixtures and the engine
    manipulate directly - and plugs in the fake Discord client.
    """
    return create_app(TestingConfig)


@pytest.fixture
def seat_the_player():
    """Returns the means to seat a player at the table, and lifts the table on the way out.

    The suite plays **both sides at once**: a single test player holds the Alliance and the
    Darkness. That is not what the "take a seat" route allows - it refuses a second side, and a
    test checks that - but the register knows nothing of it: it defends only the "one side, one
    occupant" invariant. It is that separation which lets the engine written before players existed
    play both sides, without rewriting a single one.
    """
    SEATS.clear()

    def seat(application, client=None, identity=DEFAULT_IDENTITY, sides=None):
        application.extensions["player_repository"].record(identity)
        for side in (SCENARIO.sides if sides is None else sides):
            SEATS.seat(side, identity["discord_id"])
        if client is not None:
            with client.session_transaction() as session:
                session["joueur"] = identity["discord_id"]
        return identity

    yield seat
    SEATS.clear()


@pytest.fixture
def client(application, seat_the_player):
    """A Flask test client, **logged in and seated at both sides** (see `seat_the_player`).

    It is no longer the passing visitor it was before players existed: the routes that change the
    state now require a session and a seat. To exercise an anonymous visitor, take
    `anonymous_client`.
    """
    client = application.test_client()
    seat_the_player(application, client)
    return client


@pytest.fixture
def anonymous_client(application):
    """The same client, with no session: what a passing visitor sees."""
    return application.test_client()


@pytest.fixture
def deserted_map():
    """Clears the server's board and brings the turn back to its first phase, before and after the
    test.

    The layout is grouped: without that, a sector falling near a movement test's reference hexagon
    would place opponents there, and the result would depend on chance. The turn is shared too - a
    test that advanced it would leave it advanced for the next one, and the phase's combat register
    with it.
    """
    BOARD.clear()
    TURN.restart()
    REGISTER.reset()
    yield BOARD
    BOARD.clear()
    TURN.restart()
    REGISTER.reset()


@pytest.fixture(scope="session")
def server(application):
    """Serves the application on a free port, for the length of the test session.

    `threaded=True` is not a convenience: since the page holds an open **SSE stream** (`/stream`,
    see `tenebrae/application/stream.py`), a request stays in progress for as long as the tab lives.
    A single-threaded server - which is what `make_server` gives by default - would serve that
    stream and nothing else ever again, and the whole Playwright suite would stop there. Werkzeug's
    threads are daemons: shutting down does not wait for the streams still open.
    """
    server = make_server("127.0.0.1", 0, application, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    thread.join()
