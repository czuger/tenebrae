"""The debug log of the pages: silent by default, turned on by the address, and non-destructive.

What `static/debug.js` gives the other scripts is a console log one can follow a whole game with,
and that nobody sees unless they ask for it. These tests hold the browser's console and look at
what lands in it: nothing at all on an ordinary load, the pages' own lines once "?debug=1" has been
asked for, and the round trips with the server - with the answer still readable by the caller, the
log having read a clone of it.

These tests require Chromium (`python3 -m playwright install chromium`).
"""

import re

import pytest

from tests.application.test_board_browser import a_piece_that_can_move, show_the_ghosts
from tests.application.test_scenarios_browser import open_the_page
from tests.application.test_scenarios import scenarios_directory  # noqa: F401  (fixture reused)

# Every line of the log opens the same way: "14:02:31.145 map.js · ".
LOG_LINE = re.compile(r"^\d\d:\d\d:\d\d\.\d\d\d \S+\.js · ")

# Enough turns of the event loop for a console message to reach the test, on a loaded machine.
PATIENCE = 100


@pytest.fixture
def console(page):
    """Every line the page writes to the console, in the order it writes them."""
    lines = []
    page.on("console", lambda message: lines.append(message.text))
    return lines


def logged(console):
    """The lines that come from the debug log, the others being none of its business."""
    return [line for line in console if LOG_LINE.match(line)]


def open_the_board(page, server, query=""):
    """Opens the game page logged in - the login lands on it - and waits for the zoom mounted.

    The address is given a second time so that "?debug=1" can be asked for: the login flow returns
    to "/" by itself, without our parameters.
    """
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.goto(f"{server}/game{query}")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def wait_for_a_line(page, console, fragment):
    """Waits for a line of the log to carry `fragment`, and returns it.

    The console arrives by events, which the synchronous API delivers while it waits on the page:
    hence `wait_for_timeout` rather than a sleep.
    """
    for _ in range(PATIENCE):
        for line in logged(console):
            if fragment in line:
                return line
        page.wait_for_timeout(50)
    raise AssertionError(f"no line carrying {fragment!r} among {logged(console)}")


@pytest.fixture
def board(page, server, application, seat_the_player, console):
    """The game page, seated, with the log turned off - as an ordinary visitor gets it."""
    seat_the_player(application)
    return open_the_board(page, server)


@pytest.fixture
def talkative_board(page, server, application, seat_the_player, console):
    """The same page, opened with the log on."""
    seat_the_player(application)
    return open_the_board(page, server, "?debug=1")


# --- Silent unless it is asked for ---

def test_the_log_says_nothing_by_default(board, console):
    assert board.evaluate("() => tenebraeDebug.enabled()") is False
    assert logged(console) == []


def test_the_page_still_offers_the_log(board):
    """Turned off, the namespace and its two shorthands are there all the same."""
    assert board.evaluate("() => typeof tenebraeDebug") == "object"
    assert board.evaluate("() => typeof debugScope") == "function"
    assert board.evaluate("() => typeof debugLog") == "function"


def test_the_address_turns_the_log_on(talkative_board, console):
    assert talkative_board.evaluate("() => tenebraeDebug.enabled()") is True
    wait_for_a_line(talkative_board, console, "map.js · start")


def test_the_choice_is_kept_for_the_next_loads(talkative_board, server, console):
    """The parameter is remembered: one turns the log on once, and then plays."""
    talkative_board.goto(f"{server}/game")
    talkative_board.wait_for_function("document.getElementById('scale').textContent !== '—'")
    assert talkative_board.evaluate("() => tenebraeDebug.enabled()") is True


def test_the_address_turns_it_off_again(talkative_board, server):
    talkative_board.goto(f"{server}/game?debug=0")
    talkative_board.wait_for_function("document.getElementById('scale').textContent !== '—'")
    assert talkative_board.evaluate("() => tenebraeDebug.enabled()") is False
    assert talkative_board.evaluate("() => localStorage.getItem('tenebrae.debug')") is None


def test_turning_it_off_from_the_console_silences_it(talkative_board, console):
    talkative_board.evaluate("() => tenebraeDebug.off()")
    talkative_board.wait_for_timeout(100)  # the farewell line has time to arrive
    written = len(logged(console))
    talkative_board.evaluate("() => debugLog('test.js', 'this must not appear')")
    talkative_board.wait_for_timeout(100)
    assert len(logged(console)) == written


def test_turning_it_on_from_the_console_needs_no_reload(board, console):
    board.evaluate("() => tenebraeDebug.on()")
    board.evaluate("() => debugLog('test.js', 'spoken from the console')")
    wait_for_a_line(board, console, "spoken from the console")


# --- The levels ---

def test_a_level_drops_what_is_below_it(talkative_board, console):
    """`level("info")` leaves the moves played and drops the noise of the pointer."""
    assert talkative_board.evaluate("() => tenebraeDebug.level('info')") == "info"
    talkative_board.evaluate("""() => {
        const logger = tenebraeDebug.scope('test.js');
        logger.trace('this stays below the level');
        logger.info('this passes');
    }""")
    wait_for_a_line(talkative_board, console, "this passes")
    assert not any("below the level" in line for line in logged(console))


def test_an_unknown_level_changes_nothing(talkative_board):
    kept = talkative_board.evaluate("() => tenebraeDebug.level()")
    assert talkative_board.evaluate("() => tenebraeDebug.level('shout')") == kept


def test_a_warning_is_marked_and_kept_at_the_consoles_own_level(talkative_board, page, console):
    kinds = []
    page.on("console", lambda message: kinds.append((message.type, message.text)))
    talkative_board.evaluate("() => tenebraeDebug.scope('test.js').warn('something odd')")
    wait_for_a_line(talkative_board, console, "[WARN] something odd")
    assert [kind for kind, text in kinds if "something odd" in text] == ["warning"]


# --- The round trips with the server ---

def test_a_round_trip_is_written_down(talkative_board, console):
    """A click on a unit asks the server for its squares: the log carries both ends of it."""
    piece, _, _ = a_piece_that_can_move(talkative_board)
    show_the_ghosts(talkative_board, piece)
    wait_for_a_line(talkative_board, console, "→ GET /moves")
    wait_for_a_line(talkative_board, console, "← 200 GET /moves")


def test_a_refused_request_is_written_down_as_a_warning(talkative_board, console):
    talkative_board.evaluate("() => tenebraeDebug.fetch('test.js', '/there-is-no-such-route')")
    wait_for_a_line(talkative_board, console, "[WARN] ← 404 GET /there-is-no-such-route")


def test_the_answer_stays_readable_by_the_caller(talkative_board):
    """The log reads a **clone**: the body the caller waits for has not been consumed."""
    scenarios = talkative_board.evaluate("""async () => {
        const answer = await tenebraeDebug.fetch('test.js', '/game/scenarios');
        const read = await answer.json();
        return read.scenarios.length;
    }""")
    assert scenarios > 0


def test_a_request_that_does_not_answer_still_throws(talkative_board, console):
    """`fetch`'s failure is written down and passed on: the caller's `catch` decides, as before."""
    thrown = talkative_board.evaluate("""async () => {
        try {
            await tenebraeDebug.fetch('test.js', 'http://127.0.0.1:1/nowhere');
            return false;
        } catch (error) {
            return true;
        }
    }""")
    assert thrown
    wait_for_a_line(talkative_board, console, "did not answer")


# --- Non-destructive ---

def test_the_board_is_played_the_same_with_the_log_on(talkative_board):
    """The ghosts appear and the move goes through: the log has changed nothing of the game.

    The squares are read, not the images: the move comes back through the stream, which lays the
    whole scene out again - the image clicked is no longer the one on the board.
    """
    piece, origin, _ = a_piece_that_can_move(talkative_board)
    show_the_ghosts(talkative_board, piece)
    ghost = talkative_board.locator("img.ghost").last
    destination = ghost.evaluate("g => `${g.dataset.q},${g.dataset.r},${g.dataset.s}`")
    ghost.click()
    talkative_board.wait_for_function("document.querySelectorAll('img.ghost').length === 0")

    squares = talkative_board.evaluate(
        "() => [...document.querySelectorAll('img.piece:not(.ghost)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)")
    assert destination in squares
    assert origin.key not in squares


def test_the_view_is_still_stored_with_the_log_on(talkative_board, console):
    """The zoom still reaches the server: `trace.fetch` is `fetch` for everything but the log."""
    talkative_board.locator("#zoom-in").click()
    wait_for_a_line(talkative_board, console, "→ POST /view")


# --- The other two pages ---

def test_the_fixing_page_speaks_too(page, server, application, seat_the_player, console):
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.goto(f"{server}/admin/map_fix?debug=1")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    wait_for_a_line(page, console, "map_fix.js · the fixing page is ready")


def test_the_scenario_page_speaks_too(page, server, application, seat_the_player,
                                      scenarios_directory, console):  # noqa: F811
    open_the_page(page, server, application, seat_the_player, "/admin/scenarios?debug=1")
    wait_for_a_line(page, console, "scenarios.js · the scenario page is ready")
