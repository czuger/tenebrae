"""The movement allowance seen from the screen: the counter that has walked its points is greyed.

The server counts (`tests/application/test_movement_points.py`); what is checked here is what the
player sees of it - the counter dimmed the moment its last point is spent, the tooltip that says
why, the click that no longer offers it a square, and the greying lifted when the phase turns.

**The stream is cut**, as in the retreat tests: a scene laid out again would grey the counter from
the server's own list whatever the page did with the answer, and the test would prove nothing about
the move it followed.

The figure is built on the map rather than hard-coded - a corner of bare plain, so that each step
costs exactly one point, and one a click really reaches, the toolbar covering a corner of the
window.

These tests require Chromium (`make browser`).
"""

import pytest

from tenebrae.application import current_game
from tenebrae.engine.hexagon import MAP, Hex
from tenebrae.engine.piece import CATALOGUE

from tests.application.test_board_browser import click_the_hexagon, point_of_the_hexagon
from tests.engine.plains import surroundings

DWARF = "nains-01-5-infanteries"     # alliance, 3 movement points: three squares of plain

CORNER = 1                           # one bare ring is enough: the dwarf walks to and fro on it
CORNER_SQUARES = 7                   # 1 + 3 * CORNER * (CORNER + 1)

TOOLTIP = "Points de mouvement épuisés pour cette phase."


@pytest.fixture
def board(page, server, application, seat_the_player, deserted_map):
    """The page loaded on the set-up the server opens on, the stream cut.

    A first load before any figure is built: the map is then on screen, at the scale the clicks are
    measured against, and the square the figure goes on can be chosen among those a click reaches.
    """
    seat_the_player(application)
    page.route("**/stream*", lambda route: route.abort())
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.goto(f"{server}/game")
    wait_for_the_scene(page, len(current_game.SCENARIO))
    return page


def wait_for_the_scene(page, counters):
    """Waits for the counters to be laid out and the map to be measured."""
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % counters)
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")


def reaches_the_board(page, hexagon):
    """True if a click at this hexagon's centre lands on the board rather than on the toolbar."""
    x, y = point_of_the_hexagon(page, hexagon)
    return page.evaluate("([x, y]) => document.getElementById('board')"
                         ".contains(document.elementFromPoint(x, y))", [x, y])


def a_clickable_plain(page):
    """A square of bare plain, a bare ring around it, whose squares a click really reaches."""
    for key, elements in MAP.items():
        if elements != ("plaine",):
            continue
        hexagon = Hex.from_key(key)
        neighbourhood = surroundings(hexagon, CORNER)
        if len(neighbourhood) != CORNER_SQUARES or any(MAP.get(square.key) != ("plaine",)
                                                       for square in neighbourhood):
            continue
        if all(reaches_the_board(page, square) for square in neighbourhood):
            return hexagon
    pytest.skip("no corner of bare plain is clickable in the window")


@pytest.fixture
def one_dwarf(board, application):
    """Lays a single dwarf out on a clickable plain and loads the page on it.

    Returns the square it stands on and the neighbour it will walk to and fro over: three steps of
    one point each are all its counter is printed for.
    """
    centre = a_clickable_plain(board)
    neighbour = sorted(centre.neighbours(), key=lambda square: square.key)[0]

    current_game.BOARD.clear()
    current_game.BOARD.place(centre, CATALOGUE[DWARF])
    with application.app_context():
        current_game.save_the_game()
    board.reload()
    wait_for_the_scene(board, 1)
    return centre, neighbour


def walk(page, origin, destination):
    """Selects the counter on `origin` and clicks the square it is to walk to."""
    click_the_hexagon(page, origin)
    page.wait_for_function("document.querySelectorAll('img.ghost').length > 0")
    click_the_hexagon(page, destination)
    page.wait_for_function("document.querySelectorAll('img.ghost').length === 0")


def test_the_counter_greys_out_when_its_last_point_is_spent(board, one_dwarf):
    """Three points, three steps: nothing is dimmed until the third, and the counter says why it
    will not budge again."""
    centre, neighbour = one_dwarf

    walk(board, centre, neighbour)
    assert board.locator("img.piece.unavailable").count() == 0
    walk(board, neighbour, centre)
    assert board.locator("img.piece.unavailable").count() == 0

    walk(board, centre, neighbour)
    board.wait_for_selector("img.piece.unavailable")
    assert board.locator("img.piece.unavailable").get_attribute("title") == TOOLTIP


def test_the_greyed_counter_is_offered_no_square(board, one_dwarf):
    """The click still reaches it - the map takes every click - and the server answers with nothing:
    no ghost is laid out, and the counter stays dimmed.

    The refusal's own sentence goes to the log, which the stream carries and which is cut here; it
    is checked where it is written, in `test_movement_points.py`.
    """
    centre, neighbour = one_dwarf
    walk(board, centre, neighbour)
    walk(board, neighbour, centre)
    walk(board, centre, neighbour)
    board.wait_for_selector("img.piece.unavailable")

    click_the_hexagon(board, neighbour)
    board.wait_for_timeout(200)
    assert board.locator("img.ghost").count() == 0
    assert board.locator("img.piece.unavailable").count() == 1


def test_the_next_phase_gives_the_points_back_on_screen(board, one_dwarf):
    """The allowance is the phase's: come the Dwarves' next movement phase, the counter is bright
    again and walks."""
    centre, neighbour = one_dwarf
    walk(board, centre, neighbour)
    walk(board, neighbour, centre)
    walk(board, centre, neighbour)
    board.wait_for_selector("img.piece.unavailable")

    for _ in range(4):   # dwarves' combat, orcs' movement, orcs' combat, dwarves' movement
        board.locator("#next-phase").click()
        board.wait_for_timeout(50)
    board.wait_for_function("!document.querySelector('img.piece.unavailable')")

    walk(board, neighbour, centre)
    assert current_game.BOARD.piece_on(centre).key == DWARF
