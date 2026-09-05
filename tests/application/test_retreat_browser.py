"""A retreat seen from the screen: the counters that give ground move on the tab that ordered it.

`/combat` answers with the fall-backs it has played (`retreats`), and the tab that asked for the
combat lays them out itself, as it clears the squares of the eliminated; the other tabs get the
whole scene again through the stream (`tenebrae/application/stream.py`). **The stream is cut here**,
on purpose: a scene laid out again would put every counter right whatever the answer carried, and
these tests would check nothing.

The figures are built on the map rather than hard-coded - a corner of bare plain, so that no
terrain refuses a fall-back, and one a click really reaches, the toolbar covering a corner of the
window.

These tests require Chromium (`make browser`).
"""

import pytest

from tenebrae.application import current_game
from tenebrae.engine.hexagon import MAP, Hex
from tenebrae.engine.piece import CATALOGUE

from tests.application.test_board_browser import (angles_by_square, click_the_hexagon,
                                                  point_of_the_hexagon)
from tests.engine.plains import surroundings

DWARF = "nains-01-5-infanteries"     # alliance, strength 12
ORC = "orques-01-15-infanteries"     # darkness, strength 8 - against the dwarf, the 1-1 column
A_RETREAT = 1                        # the die that reads `DR` there

CORNER = 2                           # the rings of plain the figures need around their centre
CORNER_SQUARES = 19                  # 1 + 3 * CORNER * (CORNER + 1)


@pytest.fixture
def board(page, server, application, seat_the_player, deserted_map, monkeypatch):
    """The page loaded on the set-up the server opens on, the stream cut and the die fixed.

    A first load, before any figure is built: the map is then on screen, at the scale the clicks
    are measured against, and the square a figure will be laid out on can be chosen among those a
    click really reaches. `lay_the_figure_out` loads the page again on the figure itself.
    """
    seat_the_player(application)
    monkeypatch.setattr(current_game, "roll_the_die", lambda: A_RETREAT)
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
    """A square of bare plain, two bare rings around it, whose corner a click really reaches."""
    for key, elements in MAP.items():
        if elements != ("plaine",):
            continue
        hexagon = Hex.from_key(key)
        neighbourhood = surroundings(hexagon, CORNER)
        if len(neighbourhood) != CORNER_SQUARES or any(MAP.get(square.key) != ("plaine",)
                                                       for square in neighbourhood):
            continue
        if all(reaches_the_board(page, square) for square in [hexagon] + ring(hexagon)):
            return hexagon
    pytest.skip("no corner of bare plain wide enough is clickable in the window")


def ring(centre):
    """The six squares around `centre`, sorted by key - the order the engine reads them in."""
    return sorted(centre.neighbours(), key=lambda square: square.key)


@pytest.fixture
def lay_the_figure_out(board, application):
    """Returns the means to lay a figure out and load the page on it.

    The figure is saved, then the page loaded again on it rather than told about it: the stream is
    cut, and nothing else would bring the tab a scene composed behind its back. Saving goes through
    the repository, which reads the application's - hence the context, which no route is opening
    here.
    """
    def lay_out(placement):
        current_game.BOARD.clear()
        for hexagon, key in placement.items():
            current_game.BOARD.place(hexagon, CATALOGUE[key])
        current_game.TURN.advance()  # the Dwarves' movement phase -> their combat phase
        with application.app_context():
            current_game.save_the_game()
        board.reload()
        wait_for_the_scene(board, len(placement))

    return lay_out


def attack(page, target, attackers):
    """Composes the combat on the map - the target, then the attackers - and clicks "Attaquer"."""
    click_the_hexagon(page, target)
    page.wait_for_selector("img.piece.target")
    for attacker in attackers:
        click_the_hexagon(page, attacker)
    page.wait_for_function("(n) => document.querySelectorAll('img.piece.attacker').length === n",
                           arg=len(attackers))
    page.locator("#attack").click()
    page.wait_for_selector("#attack", state="hidden")


def squares_on_screen(page):
    """The squares the counters occupy on the page, read off the board itself."""
    return set(page.evaluate(
        "() => [...document.querySelectorAll('img.piece:not(.ghost)')]"
        ".map((piece) => `${piece.dataset.q},${piece.dataset.r},${piece.dataset.s}`)"))


def test_the_defender_that_gives_ground_moves_on_the_screen(board, lay_the_figure_out):
    """`DR`: the orc leaves its square, and the tab that asked for the combat shows it."""
    plain = a_clickable_plain(board)
    dwarf, *_ = ring(plain)
    lay_the_figure_out({plain: ORC, dwarf: DWARF})

    attack(board, plain, [dwarf])

    assert current_game.BOARD.piece_on(plain) is None
    assert squares_on_screen(board) == set(current_game.BOARD.pieces)
    assert plain.key not in squares_on_screen(board)


def test_the_counter_that_falls_back_lies_down_at_the_servers_angle(board, lay_the_figure_out):
    """The unit has been picked up: it lies down at a fresh angle, and that angle is the server's.

    It is the server that draws it and that keeps it (`tenebrae/engine/board.py`), as for a move: a
    page drawing one of its own would see the counter spin at the next scene laid out.
    """
    plain = a_clickable_plain(board)
    dwarf, *_ = ring(plain)
    lay_the_figure_out({plain: ORC, dwarf: DWARF})

    attack(board, plain, [dwarf])

    fallen = next(key for key, piece in current_game.BOARD.pieces.items() if piece.key == ORC)
    assert angles_by_square(board)[fallen] == round(current_game.BOARD.tilts[fallen], 2)


def test_the_friends_pushed_move_with_it(board, lay_the_figure_out):
    """Ringed by its own, the orc pushes a friend: two counters move, and both move on screen.

    The order is what is exercised here: the orc takes the square of the friend it pushes, and a
    tab laying the fall-backs out in the order the answer gives them must move the friend all the
    same - it looks its counters up before any of them has moved (`fallThePiecesBack`).
    """
    plain = a_clickable_plain(board)
    dwarf, *friends = ring(plain)
    placement = {plain: ORC, dwarf: DWARF}
    placement.update({square: ORC for square in friends})
    lay_the_figure_out(placement)

    attack(board, plain, [dwarf])

    # The orc has given ground, and the friend it pushed has left the ring for the one beyond.
    assert current_game.BOARD.piece_on(plain) is None
    assert len(set(current_game.BOARD.pieces) - {square.key for square in placement}) == 1
    assert squares_on_screen(board) == set(current_game.BOARD.pieces)


def test_a_unit_that_cannot_fall_back_leaves_the_screen(board, lay_the_figure_out):
    """Ringed by the enemy, the orc has nowhere to go: its counter goes, like any elimination."""
    plain = a_clickable_plain(board)
    attacker, *_ = ring(plain)
    placement = {plain: ORC}
    placement.update({square: DWARF for square in ring(plain)})
    lay_the_figure_out(placement)

    attack(board, plain, [attacker])

    assert current_game.BOARD.piece_on(plain) is None
    assert squares_on_screen(board) == set(current_game.BOARD.pieces)
