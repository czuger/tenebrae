"""Resuming a game, seen from the browser: move a piece, reload, find it there.

That is what persistence promises the user, and that is what is checked here - by playing in
Chromium, not by launching the application by hand. The server is the shared one of `conftest.py`,
plugged into the test MongoDB like the rest of the suite, and the base is emptied before each test.

These tests require Chromium (`make browser`).
"""

import pytest

from tenebrae.application import current_game


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map and the first phase, and leaves them so: the board
    and the turn are shared by the whole session."""


@pytest.fixture
def persistent_server(server, application, seat_the_player):
    """The shared server, the test player seated at both sides."""
    seat_the_player(application)
    return server


@pytest.fixture
def persistent_board(page, persistent_server):
    """Opens the board and waits for the map and the units to be loaded."""
    page.set_viewport_size({"width": 1400, "height": 900})
    open_the_board(page, persistent_server)
    return page


def open_the_board(page, address):
    """Loads the board and waits for everything to be laid out - as at the first load.

    The first load goes through logging in: playing requires a seat, and the browser's session is
    set by unrolling the flow, which the fake Discord client closes back onto us.
    """
    if not page.context.cookies():
        page.goto(f"{address}/login")
    page.goto(address)
    page.wait_for_function(
        "document.querySelectorAll('img.piece').length === %d" % len(current_game.SCENARIO))
    page.wait_for_function(
        "[...document.querySelectorAll('img.piece'), document.getElementById('map')]"
        ".every((i) => i.complete && i.naturalWidth > 0)")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    return page


def placed_squares(page):
    """The squares of the placed pieces, as the page carries them."""
    return set(page.evaluate(
        "() => [...document.querySelectorAll('img.piece:not(.ghost)')]"
        ".map((p) => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`)"))


def placed_angles(page):
    """Each placed piece's angle, by square - read off the rotation the browser applied."""
    return page.evaluate("""() => Object.fromEntries(
        [...document.querySelectorAll('img.piece:not(.ghost)')].map((piece) => {
            const matrix = new DOMMatrix(getComputedStyle(piece).transform);
            const angle = Math.atan2(matrix.b, matrix.a) * 180 / Math.PI;
            return [`${piece.dataset.q},${piece.dataset.r},${piece.dataset.s}`,
                    Math.round(angle * 100) / 100];
        }))""")


def move_a_piece(page):
    """Moves the first unit that has squares to go to, and returns its origin and destination."""
    for index in range(len(current_game.SCENARIO)):
        piece = page.locator("img.piece:not(.ghost)").nth(index)
        origin = piece.evaluate("p => `${p.dataset.q},${p.dataset.r},${p.dataset.s}`")
        piece.click()
        try:
            page.wait_for_function("document.querySelectorAll('img.ghost').length > 0",
                                   timeout=2000)
        except Exception:
            continue  # this unit has nowhere to go: on to the next one
        ghost = page.locator("img.ghost").last
        destination = ghost.evaluate("g => `${g.dataset.q},${g.dataset.r},${g.dataset.s}`")
        ghost.click()
        page.wait_for_function("document.querySelectorAll('img.ghost').length === 0")
        return origin, destination
    raise AssertionError("no unit of the scenario can move")


def test_a_moved_piece_stays_at_its_new_square_after_a_reload(persistent_board,
                                                              persistent_server):
    """The heart of persistence, seen from the screen: reloading no longer resets the scenario."""
    origin, destination = move_a_piece(persistent_board)
    assert origin not in placed_squares(persistent_board)
    assert destination in placed_squares(persistent_board)

    open_the_board(persistent_board, persistent_server)

    placed = placed_squares(persistent_board)
    assert destination in placed, "the moved piece was not found at its destination"
    assert origin not in placed, "the piece is back at its origin: nothing was resumed"


def test_the_phase_is_resumed_after_a_reload(persistent_board, persistent_server):
    persistent_board.locator("#next-phase").click()
    persistent_board.wait_for_function(
        "document.getElementById('phase-label').textContent === 'Phase de combat — Nains'")

    open_the_board(persistent_board, persistent_server)
    assert persistent_board.locator("#phase-label").inner_text() == "Phase de combat — Nains"


def test_starting_again_lays_the_scenario_out_again(persistent_board, persistent_server):
    """`POST /game/new` brings the 48 units back to their squares, and the reload confirms it."""
    origin, destination = move_a_piece(persistent_board)

    answer = persistent_board.request.post(f"{persistent_server}/game/new")
    assert answer.ok

    open_the_board(persistent_board, persistent_server)
    placed = placed_squares(persistent_board)
    assert placed == set(current_game.SCENARIO.placement)
    assert origin in placed and destination not in placed


def test_the_pieces_keep_their_tilt_after_a_reload(persistent_board, persistent_server):
    """The counters' angle is saved with the positions: reloading does not lay them down again."""
    before = placed_angles(persistent_board)
    open_the_board(persistent_board, persistent_server)
    assert placed_angles(persistent_board) == before


def test_the_moved_piece_keeps_its_new_angle_after_a_reload(persistent_board, persistent_server):
    """Picked up, it lies down again once - and the base keeps that new angle."""
    _, destination = move_a_piece(persistent_board)
    angle = placed_angles(persistent_board)[destination]

    open_the_board(persistent_board, persistent_server)

    assert placed_angles(persistent_board)[destination] == angle
