"""The SSE stream at the Flask level: headers, opening message, broadcasting, removal.

What this file exercises is the seam between the broadcaster (`test_broadcaster.py`, without
Flask) and the browser (`test_stream_browser.py`, in Chromium): the `/stream` route, the message
format, and what each subscriber receives - because the table is composed per recipient.

A stream never ends by itself: each test reads it through `read`, which takes the number of
messages it expects then **closes the generator**. Without that closing, the reading thread would
stay blocked and the subscriber would stay in the registry - which is precisely one of the things
to be checked here.
"""

import json
import threading

import pytest

import app
from discord_client import DEFAULT_IDENTITY
from stream import Broadcaster

ALLIANCE, DARKNESS = "alliance", "tenebres"

# A second player, to exercise that the table differs from one subscriber to another.
OTHER_IDENTITY = {"discord_id": "100000000000000002", "nickname": "Adversaire", "avatar": None}

# The margin left to a thread to wake up on a loaded machine.
PATIENCE = 5.0


@pytest.fixture(autouse=True)
def fresh_broadcaster(monkeypatch):
    """A broadcaster of one's own for the length of the test, and empty on the way out.

    The broadcaster is a module global, like the board and the turn. Now the browser tests run
    before these and leave streams open behind them: a closed Chromium page is only noticed at the
    next heartbeat, and its subscriber would skew every count in this file. We therefore substitute
    a fresh one - `mark_a_move` as well as the stream generator reread it from the module at every
    call, so the substitution reaches both.

    On the way out, the check that counts: this test left no subscriber behind it.
    """
    monkeypatch.setattr(app, "BROADCASTER", Broadcaster())
    yield
    assert len(app.BROADCASTER) == 0, "this test left a stream open"


@pytest.fixture(autouse=True)
def short_heartbeat(monkeypatch):
    """Twenty seconds of heartbeat would make every keepalive test interminable."""
    monkeypatch.setattr(app, "HEARTBEAT", 0.05)


def open_the_stream(client, version=None, last_event=None):
    """Opens `/stream` and returns the response. It remains to be read, chunk by chunk.

    `buffered=False` is what makes the stream readable: without it, the test client would want to
    consume the response to the end, and a stream that has no end cannot be consumed.
    """
    headers = {} if last_event is None else {"Last-Event-ID": last_event}
    request = "/stream" if version is None else f"/stream?version={version}"
    return client.get(request, headers=headers, buffered=False)


def read(answer, how_many=1):
    """The first `how_many` chunks of the stream, then we close.

    Each `yield` of the generator is a chunk: a complete message, or a comment. Reading them one by
    one rather than waiting for the end is the whole point of streaming - and the only way to read
    a stream that has no end.
    """
    chunks = []
    iterator = answer.response
    try:
        for chunk in iterator:
            chunks.append(chunk.decode("utf-8"))
            if len(chunks) >= how_many:
                break
    finally:
        answer.close()
    return chunks


def data(message):
    """The JSON carried by the `data:` line of an SSE message."""
    for line in message.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: "):])
    raise AssertionError(f"no \"data\" line in {message!r}")


def event_id(message):
    """The event number carried by the `id:` line."""
    for line in message.splitlines():
        if line.startswith("id: "):
            return int(line[len("id: "):])
    raise AssertionError(f"no \"id\" line in {message!r}")


# --- What the response announces ---


def test_the_stream_is_a_server_sent_event(client):
    answer = open_the_stream(client, version=app.VERSION)
    try:
        assert answer.status_code == 200
        assert answer.mimetype == "text/event-stream"
    finally:
        answer.close()


def test_the_headers_forbid_caching_and_buffering(client):
    """`X-Accel-Buffering` is there from now on: without it, Nginx would hold each message until
    its buffer filled, and the game would look frozen (see `DEPLOYMENT.md`)."""
    answer = open_the_stream(client, version=app.VERSION)
    try:
        assert answer.headers["Cache-Control"] == "no-cache"
        assert answer.headers["X-Accel-Buffering"] == "no"
    finally:
        answer.close()


def test_the_stream_is_public(anonymous_client):
    """A passing visitor follows the game as they see the map."""
    answer = open_the_stream(anonymous_client, version=app.VERSION)
    try:
        assert answer.status_code == 200
    finally:
        answer.close()


# --- Opening the stream ---


def test_an_up_to_date_browser_receives_only_a_comment(client):
    """Nothing has moved since it loaded the page: sending it the 48 pieces would be for nothing.

    An SSE comment - a line beginning with ":" - opens the connection all the same, which moves
    the browser's `EventSource` to the "open" state.
    """
    answer = open_the_stream(client, version=app.VERSION)
    assert read(answer) == [": partie suivie\n\n"]


def test_a_browser_behind_receives_the_whole_game(client):
    """It reopens its tab after an outage: the opponent may have played meanwhile."""
    client.get("/")  # the board is a module global: we populate it before counting its pieces
    answer = open_the_stream(client, version=app.VERSION - 1)
    state = data(read(answer)[0])

    assert state["version"] == app.VERSION
    assert len(state["pieces"]) == len(app.SCENARIO)
    assert state["phase"]["label"] == app.TURN.label
    assert state["table"]["connected"] is True


def test_a_browser_without_a_version_receives_the_whole_game(client):
    """No `?version` and no `Last-Event-ID`: we do not know what it knows, so we say everything."""
    answer = open_the_stream(client)
    assert data(read(answer)[0])["version"] == app.VERSION


def test_the_last_event_prevails_over_the_parameter(client):
    """The URL dates from when the page opened; the `Last-Event-ID`, from the last reconnection.

    An `EventSource` cannot set a header on the first connection - hence `?version=` - but it sends
    the `Last-Event-ID` by itself at every reconnection, and that one is more recent. So it
    decides.
    """
    answer = open_the_stream(client, version=app.VERSION - 1, last_event=str(app.VERSION))
    assert read(answer) == [": partie suivie\n\n"]


def test_an_unreadable_last_event_makes_everything_be_sent_back(client):
    """The header comes from the browser: empty, or anything at all. We do not crash for so little."""
    answer = open_the_stream(client, last_event="")
    assert data(read(answer)[0])["version"] == app.VERSION


def test_a_restarted_server_is_caught_up_with(client, deserted_map):
    """The browser knows version 12, the server starts again from zero: the numbers no longer
    match, and that is precisely what must make it take everything again."""
    answer = open_the_stream(client, last_event="12")
    assert data(read(answer)[0])["version"] == app.VERSION


# --- What happens when a move is played ---


def test_a_move_played_is_pushed_to_the_stream(client):
    """The heart of the matter: nobody asks for anything again, the server writes."""
    answer = open_the_stream(client, version=app.VERSION)
    iterator = answer.response
    try:
        assert next(iterator).decode() == ": partie suivie\n\n"

        # The subscription only exists once the generator has started: the move is played after.
        assert client.post("/phase/next").status_code == 200

        message = next(iterator).decode()
        state = data(message)
        assert state["phase"]["label"] == app.TURN.label
        assert event_id(message) == state["version"] == app.VERSION
    finally:
        answer.close()


def test_the_stream_beats_when_nothing_happens(client):
    """The keepalive: without it, an intermediary would close a connection it believes dead."""
    answer = open_the_stream(client, version=app.VERSION)
    assert read(answer, how_many=3) == [": partie suivie\n\n", ": battement\n\n",
                                        ": battement\n\n"]


def test_a_move_pushes_the_board(client, deserted_map):
    """It is not only the phase: every move played goes through `mark_a_move`."""
    origin = app.Hex(0, 0, 0)
    piece = app.CATALOGUE[next(iter(app.SCENARIO.placement.values()))]
    deserted_map.place(origin, piece)
    destination = next(iter(deserted_map.moves(origin, piece)))

    answer = open_the_stream(client, version=app.VERSION)
    iterator = answer.response
    try:
        next(iterator)
        assert client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": piece.key,
        }).json["allowed"] is True

        squares = {(p["q"], p["r"], p["s"]) for p in data(next(iterator).decode())["pieces"]}
        assert (destination.q, destination.r, destination.s) in squares
    finally:
        answer.close()


def test_a_fresh_game_pushes_the_laid_out_scenario_and_not_an_empty_board(client):
    """`lay_out_the_scenario` clears the board before filling it.

    Marking the move in between - which is what the code did before the stream - pushed the
    photograph of a deserted board, and the opponent's browser erased all its pieces.
    """
    answer = open_the_stream(client, version=app.VERSION)
    iterator = answer.response
    try:
        next(iterator)
        assert client.post("/game/new").status_code == 200
        assert len(data(next(iterator).decode())["pieces"]) == len(app.SCENARIO)
    finally:
        answer.close()


# --- Several clients at once ---


def test_two_streams_receive_the_same_move(client, anonymous_client):
    """Two players, two browsers: a single move, and both see it."""
    player = open_the_stream(client, version=app.VERSION)
    visitor = open_the_stream(anonymous_client, version=app.VERSION)
    player_thread, visitor_thread = player.response, visitor.response
    try:
        next(player_thread)
        next(visitor_thread)
        assert len(app.BROADCASTER) == 2

        assert client.post("/phase/next").status_code == 200

        for iterator in (player_thread, visitor_thread):
            assert data(next(iterator).decode())["phase"]["label"] == app.TURN.label
    finally:
        player.close()
        visitor.close()


def test_each_stream_receives_its_own_players_table(application, client, anonymous_client):
    """The only part of the message that is not shared.

    The seated player receives their sides; the passing visitor receives an anonymous table - but
    the **same game**. That is why the table is composed per recipient and not once and for all.
    """
    player = open_the_stream(client, version=app.VERSION)
    visitor = open_the_stream(anonymous_client, version=app.VERSION)
    player_thread, visitor_thread = player.response, visitor.response
    try:
        next(player_thread)
        next(visitor_thread)
        assert client.post("/phase/next").status_code == 200

        players_table = data(next(player_thread).decode())["table"]
        visitors_table = data(next(visitor_thread).decode())["table"]

        assert players_table["connected"] is True
        assert players_table["nickname"] == DEFAULT_IDENTITY["nickname"]
        assert players_table["sides"] == [ALLIANCE, DARKNESS]

        assert visitors_table["connected"] is False
        assert visitors_table["nickname"] is None
        assert visitors_table["sides"] == []

        # And yet the same game: the occupied seats are seen from both sides.
        assert players_table["seats"] == visitors_table["seats"]
    finally:
        player.close()
        visitor.close()


def test_the_player_is_re_read_at_every_message(application, client):
    """The stream does not cache the player: leaving one's seat shows at the next message.

    That is what forbids `stream_with_context`, which would keep `g.player` for the whole duration
    of the connection - that is, as long as the tab stays open.
    """
    answer = open_the_stream(client, version=app.VERSION)
    iterator = answer.response
    try:
        next(iterator)
        assert client.post("/phase/next").status_code == 200
        assert data(next(iterator).decode())["table"]["sides"] == [ALLIANCE, DARKNESS]

        assert client.post("/game/seat/leave").status_code == 200
        assert data(next(iterator).decode())["table"]["sides"] == []
    finally:
        answer.close()


# --- Cleaning up ---


def test_a_closed_stream_frees_its_subscription(client):
    """The leak we want to catch: a closed tab leaving its box behind it.

    The server would go on depositing the state of every move played into it, forever.
    """
    answer = open_the_stream(client, version=app.VERSION)
    iterator = answer.response
    next(iterator)
    assert len(app.BROADCASTER) == 1

    answer.close()
    assert len(app.BROADCASTER) == 0


def test_ten_streams_opened_then_closed_leave_nothing(client):
    """A tab opened and closed ten times in a row must accumulate nothing."""
    for _ in range(10):
        answer = open_the_stream(client, version=app.VERSION)
        next(answer.response)
        answer.close()
    assert len(app.BROADCASTER) == 0


def test_a_stream_read_in_another_thread_also_receives(client, application):
    """The real case: the stream is served by one thread, the move played by another.

    Both the development server and gunicorn serve each request in its own thread; this test is
    the closest to what really happens.
    """
    received = []
    subscribed = threading.Event()

    def listen():
        with application.test_client() as other:
            answer = open_the_stream(other, version=app.VERSION)
            iterator = answer.response
            try:
                next(iterator)
                subscribed.set()
                received.append(data(next(iterator).decode()))
            finally:
                answer.close()

    thread = threading.Thread(target=listen, daemon=True)
    thread.start()
    assert subscribed.wait(PATIENCE), "the second thread's stream did not open"

    assert client.post("/phase/next").status_code == 200
    thread.join(PATIENCE)

    assert len(received) == 1 and received[0]["phase"]["label"] == app.TURN.label
    assert len(app.BROADCASTER) == 0
