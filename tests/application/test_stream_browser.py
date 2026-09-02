"""The stream seen from the screen: two tabs, a move played in one, the scene moving in the other.

That is what the migration promises the user, and it is here that it is checked - in Chromium, not
by opening two windows by hand. Three things are exercised here and nowhere else:

- that the page really **opens an `EventSource`** and no longer polls `/game/state`;
- that a move played outside arrives **without it having asked for anything**;
- that the fallback to polling kicks in when the stream does not get through, and that the game
  goes on.

These engine require Chromium (`make browser`).
"""

import pytest

import app

# A move played must show in less time than the old poll would have taken: that is the only way to
# tell "the stream pushed" from "something eventually asked again".
STREAM_DELAY = 1500  # milliseconds; the fallback poll was at 3000

# Playwright's ordinary patience for what is not timed.
DELAY = 10_000

# The fallback, on the other hand, is slow by construction: five failures, and Chromium spaces its
# reconnections about three seconds apart. That is deliberate - we do not give up on the stream on
# a network hiccup - and the fifteen-odd seconds it takes must therefore be allowed to pass.
FALLBACK_DELAY = 40_000

LABEL = "document.getElementById('phase-label').textContent"


@pytest.fixture(autouse=True)
def fresh_game(application, seat_the_player):
    """Every test starts from the scenario laid out, the first phase, and a seated player.

    The board and the turn are module globals shared by all the test files; without this, a
    previous test would leave the game in its combat phase and the labels expected here would not
    come out right.
    """
    seat_the_player(application)
    app.BOARD.clear()
    app.TURN.restart()
    app.REGISTER.reset()
    for square, key in app.SCENARIO.placement.items():
        app.BOARD.place(app.Hex.from_key(square), app.CATALOGUE[key])
    yield
    app.BOARD.clear()
    app.TURN.restart()
    app.REGISTER.reset()


@pytest.fixture
def opponent(playwright, server):
    """The one playing "outside": an HTTP client of its own, outside any browser.

    That is what makes these engine honest. Going through `page.request` would borrow the observed
    tab's cookies - the move would then come from the page itself, and nothing at all would be
    exercised for an anonymous visitor. Here the move really comes from elsewhere.

    Logging in unrolls the real flow, which the fake Discord client closes back onto us; the player
    obtained is the one `seat_the_player` seated at both sides.
    """
    context = playwright.request.new_context(base_url=server)
    assert context.get("/login").ok
    yield context
    context.dispose()


def open_the_board(page, server, logged_in=True):
    """Loads the board and waits for the scene to be laid out **and the stream open**.

    Waiting for the stream to be open is not a comfort measure: a move played before the
    `EventSource` is connected would be pushed to nobody, and the test would fail for a reason
    other than the one it exercises.
    """
    page.set_viewport_size({"width": 1400, "height": 900})
    if logged_in and not page.context.cookies():
        page.goto(f"{server}/login")
    page.goto(server)
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(app.SCENARIO))
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    wait_for_the_stream(page)
    return page


def wait_for_the_stream(page):
    """Waits for the page's `EventSource` to be in the "open" state (`readyState === 1`)."""
    page.wait_for_function("stream !== null && stream.readyState === 1", timeout=DELAY)


def placed_squares(page):
    return set(page.evaluate(
        "() => [...document.querySelectorAll('img.piece:not(.ghost)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))


# --- The page really holds a stream, and no longer polls ---


def test_the_page_opens_a_stream(page, server):
    open_the_board(page, server)
    assert page.evaluate("stream instanceof EventSource") is True


def test_the_page_no_longer_polls_the_state(page, server, opponent):
    """Polling is dead: not a single `/game/state`, even after a move played.

    The old `setInterval` fired every three seconds; we let four pass.
    """
    polls = []
    page.on("request", lambda request: polls.append(request.url)
            if "/game/state" in request.url else None)

    open_the_board(page, server)
    assert opponent.post("/phase/next").ok
    page.wait_for_function(f"{LABEL} === 'Phase de combat — Nains'", timeout=STREAM_DELAY)
    page.wait_for_timeout(4000)

    assert polls == [], f"the page is still polling: {polls}"


def test_the_stream_is_the_only_call_to_the_server_when_nothing_happens(page, server):
    """A page opened and left alone must no longer ask for anything at all."""
    open_the_board(page, server)
    calls = []
    page.on("request", lambda request: calls.append(request.url))
    page.wait_for_timeout(4000)
    assert calls == [], f"the page still calls the server at rest: {calls}"


# --- A move played outside arrives by itself ---


def test_a_move_played_outside_arrives_without_asking_for_anything(page, server, opponent):
    """The heart of the matter, and in less than a second and a half - the old poll took three
    seconds in the best case."""
    open_the_board(page, server)
    assert page.locator("#phase-label").inner_text() == "Phase de mouvement — Nains"

    assert opponent.post("/phase/next").ok

    page.wait_for_function(f"{LABEL} === 'Phase de combat — Nains'", timeout=STREAM_DELAY)


def test_a_piece_moved_outside_is_laid_out_again_in_the_page(page, server, opponent):
    """Not only the phase: the whole board travels through the stream."""
    open_the_board(page, server)

    origin, destination, key = a_possible_move()
    answer = opponent.post("/move", data={
        "origin": origin.to_dict(), "destination": destination.to_dict(), "piece": key})
    assert answer.json()["allowed"] is True

    page.wait_for_function(
        "(squares) => [...document.querySelectorAll('img.piece:not(.ghost)')]"
        ".some((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}` === squares)",
        arg=f"{destination.q},{destination.r},{destination.s}", timeout=STREAM_DELAY)
    assert f"{origin.q},{origin.r},{origin.s}" not in placed_squares(page)


def a_possible_move():
    """A unit of the active side, its square, and a square it can go to."""
    for square, piece in app.BOARD.pieces.items():
        if piece.side != app.TURN.active_side:
            continue
        origin = app.Hex.from_key(square)
        destinations = app.BOARD.moves(origin, piece)
        if destinations:
            return origin, next(iter(destinations)), piece.key
    raise AssertionError("no unit of the active side can move")


def test_two_tabs_see_the_same_move(page, context, server, opponent):
    """Two players, two browsers: that is what all of this exists for."""
    open_the_board(page, server)
    second = context.new_page()
    try:
        open_the_board(second, server)

        assert opponent.post("/phase/next").ok

        for tab in (page, second):
            tab.wait_for_function(f"{LABEL} === 'Phase de combat — Nains'", timeout=STREAM_DELAY)
    finally:
        second.close()


def test_a_visitor_without_an_account_also_follows_the_game(page, server, opponent):
    """The stream is public, like the map: one can watch a game without an account."""
    open_the_board(page, server, logged_in=False)
    assert page.evaluate("table.connected") is False

    assert opponent.post("/phase/next").ok

    page.wait_for_function(f"{LABEL} === 'Phase de combat — Nains'", timeout=STREAM_DELAY)


# --- What laying the scene out again must not undo ---


def test_the_locate_marker_survives_the_scene_being_laid_out_again(page, server, opponent):
    """"Localiser" aims at the last clicked piece, and must find it again after an opponent's move.

    Laying the scene out again destroys every image and recreates them: without care, the marker
    would point at an element no longer on the board and the button would go off. That was already
    true of polling, but one had to wait three seconds to see it; the stream shows it at once.
    """
    open_the_board(page, server)
    piece = page.locator("img.piece:not(.ghost)").first
    square = piece.evaluate("p => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`")
    piece.click()
    page.wait_for_function("!document.getElementById('locate').disabled")

    assert opponent.post("/phase/next").ok
    page.wait_for_function(f"{LABEL} === 'Phase de combat — Nains'", timeout=STREAM_DELAY)

    assert page.locator("#locate").is_enabled(), \
        "the \"localiser\" marker was lost when laying the scene out again"
    assert page.evaluate("`${lastClickedPiece.dataset.q},${lastClickedPiece.dataset.r},`"
                         "+ `${lastClickedPiece.dataset.s}`") == square


# --- The fallback, and reconnecting ---


def test_the_fallback_to_polling_when_the_stream_does_not_get_through(page, server, opponent):
    """An intermediary that cuts SSE must not break the game: it must slow it down.

    We refuse every connection to `/stream`: the browser retries by itself, the page counts the
    failures, and on the fifth it reopens the old poll. The move played outside therefore does end
    up arriving - in three seconds instead of a millisecond.
    """
    page.route("**/stream*", lambda route: route.abort())
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.goto(server)
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(app.SCENARIO))

    # The fallback settles in once the five failures have been counted.
    page.wait_for_function("pollTimer !== null", timeout=FALLBACK_DELAY)
    assert page.evaluate("stream === null"), "the stream should have been closed before the fallback"

    assert opponent.post("/phase/next").ok
    page.wait_for_function(f"{LABEL} === 'Phase de combat — Nains'", timeout=DELAY)


def test_the_page_reconnects_after_an_outage(page, server, opponent):
    """The server restarts, or the network drops: `EventSource` reopens by itself, and catches up.

    The outage is played by refusing `/stream` for the length of one reconnection, then letting it
    through again. What is checked afterwards is what counts: the stream is open again, and a move
    played during the outage really was caught up on - that is what the `Last-Event-ID` allows.
    """
    open_the_board(page, server)

    cut = {"active": True}
    page.route("**/stream*",
               lambda route: route.abort() if cut["active"] else route.continue_())
    page.evaluate("stream.close(); stream = null; openTheStream();")  # the connection drops

    # The move is played while the page is listening to nobody: it cannot receive it.
    assert opponent.post("/phase/next").ok
    page.wait_for_timeout(300)
    assert page.locator("#phase-label").inner_text() == "Phase de mouvement — Nains"

    cut["active"] = False
    wait_for_the_stream(page)

    # Reconnected, the page catches up on what it missed without anything having to be asked again.
    page.wait_for_function(f"{LABEL} === 'Phase de combat — Nains'", timeout=DELAY)


# --- Cleaning up ---


def test_a_closed_tab_frees_its_subscription(page, context, server, opponent):
    """The leak we want to catch: the server must not keep a box for a tab that has gone."""
    open_the_board(page, server)
    subscribers = len(app.BROADCASTER)

    second = context.new_page()
    open_the_board(second, server)
    assert len(app.BROADCASTER) == subscribers + 1

    second.close()
    # The removal is noticed as soon as the server tries to write: the heartbeat is enough to
    # trigger it, and it is shortened here by the first move played.
    assert opponent.post("/phase/next").ok
    wait_until(lambda: len(app.BROADCASTER) == subscribers)


def wait_until(condition, seconds=10.0):
    """Waits for a Python condition to become true - the removal happens in another thread."""
    import time
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        if condition():
            return
        time.sleep(0.05)
    raise AssertionError("condition never met")
