"""The log column, in the browser: where it is, what it shows, and when.

These engine require Chromium (`python3 -m playwright install chromium`).
"""

import pytest

import app
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import CATALOGUE

PLAIN = {"q": 1, "r": 26, "s": -27}     # two free adjacent squares of scenario no. 4
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}

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
    app.LOG_MEMORY.lines.clear()
    page.goto(f"{server}/")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")
    yield page
    app.LOG_MEMORY.lines.clear()


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
    assert text == "Phase : Phase de combat — Nains (tour 1)"
    assert len(time.split(":")) == 3


def test_the_last_line_is_at_the_top(board):
    """The column reads the other way round from the file: what has just happened is under the
    card."""
    pass_a_phase(board, 1)
    pass_a_phase(board, 2)
    assert [text for _, text in read_lines(board)] == [
        "Phase : Phase de mouvement — Orques (tour 1)",
        "Phase : Phase de combat — Nains (tour 1)",
    ]


def test_the_column_sits_under_the_card(board):
    """The requested placement: a column just below the card's area.

    The card being hidden as long as nothing is hovered, we show it by hand for the length of the
    measurement - it is the order of the two boxes in the panel that is checked, not the hovering.
    """
    assert board.locator("#panel > #log").count() == 1
    pass_a_phase(board, 1)
    places = board.evaluate("""() => {
        const card = document.getElementById('card');
        card.hidden = false;
        const box = (id) => document.getElementById(id).getBoundingClientRect();
        const measurements = { card: box('card'), log: box('log') };
        card.hidden = true;
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
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    app.BOARD.place(Hex(**PLAIN), CATALOGUE[DWARF])
    app.BOARD.place(Hex(**NEIGHBOUR), CATALOGUE[ARCHER])
    pass_a_phase(board, 1)  # the Dwarves' combat phase, and the scene laid out with both

    click(board, NEIGHBOUR)  # the target
    click(board, PLAIN)      # the attacker
    board.locator("#attack").click()
    board.wait_for_function(
        "() => document.querySelectorAll('#log-lines li').length === 3")

    assert [text for _, text in read_lines(board)] == [
        "Combat résolu : Défenseur Éliminé",
        "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1",
        "Phase : Phase de combat — Nains (tour 1)",
    ]


def test_a_long_line_stays_inside_the_column(board, monkeypatch):
    """The breakdown is long: it must wrap inside the column, not make it overflow."""
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    app.BOARD.place(Hex(**PLAIN), CATALOGUE[DWARF])
    app.BOARD.place(Hex(**NEIGHBOUR), CATALOGUE[ARCHER])
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
