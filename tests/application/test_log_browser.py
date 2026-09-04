"""The log column, in the browser: where it is, what it shows, and when.

These engine require Chromium (`python3 -m playwright install chromium`).
"""

import pytest

from tenebrae.application import current_game
from tenebrae.application.logs import battle_log
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import CATALOGUE

PLAIN = {"q": 1, "r": 26, "s": -27}     # two free adjacent squares of scenario no. 4
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}

# A plain square that the log column covers once the map is fitted to the test window (1400 x 900):
# the counter placed there falls at about (206, 256), where the column runs from (10, 55) to
# (362, 415). See "The map is always the one that takes the click", at the end of this file.
COVERED = {"q": 2, "r": 10, "s": -12}

DWARF = "nains-01-5-infanteries"  # alliance, strength 12
ARCHER = "yzent-03-8-archers"     # darkness, strength 2 -> ratio 6-1, die 1 -> DE


@pytest.fixture
def board(page, server, application, seat_the_player, deserted_map):
    """Opens the page **logged in**, with the log emptied.

    The server's log is a module global, and the engine' server runs in that same process: we empty
    it so the column shows only what the test writes into it. That requires emptying it **between**
    the login and the page - logging in writes its own line, and it would skew the counts.
    """
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    battle_log.LOG_MEMORY.lines.clear()
    page.goto(f"{server}/")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    yield page
    battle_log.LOG_MEMORY.lines.clear()


def read_lines(page):
    """What the column shows, from top to bottom: a (time, text) pair per line."""
    return page.evaluate("""() => [...document.querySelectorAll('#log-lines li')]
        .map((line) => [line.querySelector('time').textContent,
                        line.querySelector('.text').textContent])""")


def pass_a_phase(page, expected):
    """Steps to the next phase, and waits for the column to count `expected` lines.

    It is the **stream** that is being waited for there: the button's answer carries only the
    phase, and the log line arrives through the channel that pushes the game (see
    `resumeTheGame`).
    """
    page.locator("#next-phase").click()
    page.wait_for_function(
        "(n) => document.querySelectorAll('#log-lines li').length === n", arg=expected)


def test_the_column_is_empty_and_hidden_while_nothing_has_arrived(board):
    """Nothing to tell, nothing to frame."""
    assert board.locator("#log").is_hidden()
    assert read_lines(board) == []


def test_the_column_shows_what_the_server_logs(board):
    pass_a_phase(board, 1)
    assert board.locator("#log").is_visible()
    time, text = read_lines(board)[0]
    assert text == "Phase: Phase de combat — Nains (turn 1)"
    assert len(time.split(":")) == 3


def test_the_last_line_is_at_the_top(board):
    """The column reads the other way round from the file: what has just happened is under the
    card."""
    pass_a_phase(board, 1)
    pass_a_phase(board, 2)
    assert [text for _, text in read_lines(board)] == [
        "Phase: Phase de mouvement — Orques (turn 1)",
        "Phase: Phase de combat — Nains (turn 1)",
    ]


def test_the_column_sits_under_the_card(board):
    """The requested placement: a column just below the card's area.

    The card's area is always there, empty as long as nothing is hovered: it can be measured as it
    stands, without anything having to be shown by hand.
    """
    assert board.locator("#panel > #log").count() == 1
    pass_a_phase(board, 1)
    places = board.evaluate("""() => {
        const box = (id) => document.getElementById(id).getBoundingClientRect();
        const measurements = { card: box('card'), log: box('log') };
        return { card: [measurements.card.bottom, measurements.card.left],
                 log: [measurements.log.top, measurements.log.left] };
    }""")
    assert places["log"][0] >= places["card"][0], places   # under the card
    assert places["log"][1] == places["card"][1], places   # aligned on its left edge


def click(page, square):
    """Clicks the piece placed on this square, whatever the zoom."""
    page.locator(
        f"img.piece[data-q='{square['q']}'][data-r='{square['r']}'][data-s='{square['s']}']"
    ).click()


def test_the_combat_shows_the_breakdown_of_its_computation(board, monkeypatch):
    """What the player sees of a combat fought: its outcome, and below it the computation that
    gave it.

    Both units are placed on the server's board before the phase change: it is the server that
    lays the scene out again, and they arrive with the rest.
    """
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    current_game.BOARD.place(Hex(**PLAIN), CATALOGUE[DWARF])
    current_game.BOARD.place(Hex(**NEIGHBOUR), CATALOGUE[ARCHER])
    pass_a_phase(board, 1)  # the Dwarves' combat phase, and the scene laid out with both

    click(board, NEIGHBOUR)  # the target
    click(board, PLAIN)      # the attacker
    board.locator("#attack").click()
    board.wait_for_function(
        "() => document.querySelectorAll('#log-lines li').length === 3")

    assert [text for _, text in read_lines(board)] == [
        "Combat résolu : Défenseur Éliminé",
        "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1",
        "Phase: Phase de combat — Nains (turn 1)",
    ]


def test_a_long_line_stays_inside_the_column(board, monkeypatch):
    """The breakdown is long: it must wrap inside the column, not make it overflow."""
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    current_game.BOARD.place(Hex(**PLAIN), CATALOGUE[DWARF])
    current_game.BOARD.place(Hex(**NEIGHBOUR), CATALOGUE[ARCHER])
    pass_a_phase(board, 1)
    click(board, NEIGHBOUR)
    click(board, PLAIN)
    board.locator("#attack").click()
    board.wait_for_function(
        "() => document.querySelectorAll('#log-lines li').length === 3")

    measurements = board.evaluate("""() => {
        const column = document.getElementById('log');
        const breakdown = [...document.querySelectorAll('#log-lines li')][1];
        return { overflow: column.scrollWidth - column.clientWidth,
                 width: column.getBoundingClientRect().width,
                 height: breakdown.getBoundingClientRect().height,
                 line: parseFloat(getComputedStyle(breakdown).fontSize) };
    }""")
    assert measurements["overflow"] <= 1, measurements          # nothing sticks out to the right
    assert measurements["height"] > measurements["line"], measurements  # the line did wrap


# ── The map is always the one that takes the click ───────────────────────────────────────────────
#
# The column is 22rem wide and up to 40vh tall, over the top-left corner of the map - where a
# scenario often has units. It was swallowing their clicks. The panel lets the pointer through now
# (map.css), and these tests hold it to that.

def fill_the_column(page, lines=30):
    """Fills the column from the page, so that it covers a good part of the map.

    The lines are laid in by the very function the stream calls (`refreshTheLog` in map.js): what
    is being measured is the column's size and its hit-testing, not where its content comes from.
    """
    page.evaluate("""(count) => refreshTheLog(Array.from({ length: count }, (_, i) => (
        { time: '12:00:00', text: `ligne ${i}` })))""", lines)
    page.wait_for_function("document.getElementById('log').getBoundingClientRect().height > 100")


def element_at(page, x, y):
    """What the browser would hand a click at that point: its id, and whether it is on the map."""
    return page.evaluate("""([x, y]) => {
        const found = document.elementFromPoint(x, y);
        return { id: found.id, tag: found.tagName, inPanel: Boolean(found.closest('#panel')),
                 onTheMap: Boolean(found.closest('#board')) };
    }""", [x, y])


def centre_of(page, identifier):
    return page.evaluate("""(id) => {
        const box = document.getElementById(id).getBoundingClientRect();
        return [box.x + box.width / 2, box.y + box.height / 2];
    }""", identifier)


def test_the_column_does_not_take_the_click(board):
    """A click in the middle of the column reaches the map underneath it."""
    fill_the_column(board)
    found = element_at(board, *centre_of(board, "log"))
    assert found["inPanel"] is False, found
    assert found["onTheMap"] is True, found


def test_the_column_follows_the_block_to_the_other_edge(board):
    """The column is the tallest box of the panel, and the one that covers most map: it moves with
    the block rather than staying behind on the left."""
    fill_the_column(board)
    on_the_left = centre_of(board, "log")

    board.locator("#panel-side").click()
    board.wait_for_function("document.getElementById('panel').classList.contains('right')")
    edges = board.evaluate("""() => {
        const box = (id) => document.getElementById(id).getBoundingClientRect();
        return { log: box('log'), panel: box('panel') };
    }""")
    assert centre_of(board, "log")[0] > on_the_left[0], edges
    assert round(edges["log"]["right"]) == round(edges["panel"]["right"]), edges


def test_the_toolbar_still_takes_the_click(board):
    """The one box of the panel that keeps the pointer: it carries the buttons."""
    found = element_at(board, *centre_of(board, "zoom-in"))
    assert found["id"] == "zoom-in", found


def test_a_counter_under_the_column_is_still_clicked(board):
    """The bug itself: a piece the column covers takes the click all the same.

    The piece is placed on a square the column covers - the map opens fitted to the test window, so
    that square is always at the same place - and the click is aimed at the counter. It is
    `localiser`, which any click on a piece enables, that says the board received it.
    """
    current_game.BOARD.place(Hex(**COVERED), CATALOGUE[DWARF])
    pass_a_phase(board, 1)  # the server lays the scene out again, with it
    fill_the_column(board)

    places = board.evaluate("""() => {
        const piece = document.querySelector("img.piece[data-q='2'][data-r='10'][data-s='-12']");
        const box = piece.getBoundingClientRect();
        const column = document.getElementById('log').getBoundingClientRect();
        const point = [box.x + box.width / 2, box.y + box.height / 2];
        return { point,
                 covered: point[0] > column.x && point[0] < column.right
                          && point[1] > column.y && point[1] < column.bottom,
                 found: document.elementFromPoint(...point) === piece };
    }""")
    assert places["covered"] is True, places   # the counter really is under the column
    assert places["found"] is True, places     # and it is the counter the click would reach
    assert board.locator("#locate").is_disabled()

    board.mouse.click(*places["point"])
    board.wait_for_selector("#locate:not([disabled])")
# ── Reducing the column ──────────────────────────────────────────────────────────────────────────
#
# The column is tall and it lies over the map: its "−" button brings it down to itself, and back.


def log_height(page):
    return page.evaluate("() => document.getElementById('log').getBoundingClientRect().height")


def test_the_button_reduces_the_column_to_itself(board):
    fill_the_column(board)
    opened = log_height(board)

    board.locator("#log-toggle").click()
    board.wait_for_selector("#log-lines", state="hidden")
    assert log_height(board) < opened / 2
    assert board.locator("#log-toggle").text_content() == "+"
    assert board.locator("#log-toggle").get_attribute("title") == "Afficher le journal"


def test_the_button_brings_the_column_back(board):
    fill_the_column(board)
    opened = log_height(board)

    board.locator("#log-toggle").click()
    board.wait_for_selector("#log-lines", state="hidden")
    board.locator("#log-toggle").click()
    board.wait_for_selector("#log-lines", state="visible")
    assert log_height(board) == opened
    assert board.locator("#log-toggle").text_content() == "−"


def test_a_reduced_column_stays_reduced_while_the_game_goes_on(board):
    """The state is the box's, and the lines alone are rewritten at every move played."""
    pass_a_phase(board, 1)
    board.locator("#log-toggle").click()
    board.wait_for_selector("#log-lines", state="hidden")

    pass_a_phase(board, 2)
    assert board.locator("#log-lines").is_hidden()
    assert board.locator("#log").is_visible()


def test_a_reduced_column_keeps_its_button_when_the_log_empties(board):
    """A server restarted has an empty memory, and the stream hands it over: the box must stay,
    or nothing could bring the column back. Untouched, an empty column still does not appear."""
    fill_the_column(board)
    board.locator("#log-toggle").click()
    board.wait_for_selector("#log-lines", state="hidden")

    board.evaluate("() => refreshTheLog([])")
    assert board.locator("#log").is_visible()
    assert board.locator("#log-toggle").is_visible()

    # Opened again with nothing in it: an empty list has no height, hence the class and not the
    # lines' visibility.
    board.locator("#log-toggle").click()
    board.wait_for_function("!document.getElementById('log').classList.contains('reduced')")
    assert board.locator("#log").is_visible()
    assert board.locator("#log-toggle").text_content() == "−"


def test_the_button_takes_its_own_click(board):
    """The panel lets the pointer through; the button, which carries one, takes it back."""
    fill_the_column(board)
    found = element_at(board, *centre_of(board, "log-toggle"))
    assert found["id"] == "log-toggle", found
