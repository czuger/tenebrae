"""The game log as the server serves it: its lines, and the moment they leave.

The log used to be only a local file; it is now shown, in a column under the card. Two things are
to be exercised on this side - that the page and the stream carry it, and that a line written at
the moment of a move **leaves with that move**. The second point rests on a call order:
`mark_a_move` photographs the game, log included, and any route logging after having saved would
push the browsers an account one move behind.

The rendering of the column is in `test_log_browser.py`.
"""

import logging
from pathlib import Path

import pytest

import app
from engine import combat
from engine.hexagon import Hex
from engine.piece import CATALOGUE
from stream import Broadcaster

from test_server import read_hidden_field

PLAIN = {"q": 1, "r": 26, "s": -27}
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}

DWARF = "nains-01-5-infanteries"  # alliance, strength 12
ARCHER = "yzent-03-8-archers"     # darkness, strength 2 -> ratio 6-1, die 1 -> DE


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map, as in `test_server.py`."""


@pytest.fixture(autouse=True)
def empty_log():
    """An empty log at the start, and empty on the way out.

    The queue is a module global, and it crosses tests: without this cleanup, a test would read the
    lines written by everything that came before it - starting with the browser tests.
    """
    app.LOG_MEMORY.lines.clear()
    yield app.LOG_MEMORY.lines
    app.LOG_MEMORY.lines.clear()


@pytest.fixture(autouse=True)
def fresh_broadcaster(monkeypatch):
    """A broadcaster of one's own: the browser tests leave streams open behind them, and here we
    want to read what is published, not share it (see `test_stream.py`)."""
    monkeypatch.setattr(app, "BROADCASTER", Broadcaster())


def place(hexagon, key):
    app.BOARD.place(Hex(**hexagon), CATALOGUE[key])


def texts(lines):
    return [line["text"] for line in lines]


# --- What the log keeps --------------------------------------------------------------------------

def test_a_logged_line_carries_its_time_and_its_text():
    app.LOG.info("Phase : %s (tour %s)", "Phase de combat — Nains", 3)
    line = app.log_lines()[-1]
    assert line["text"] == "Phase : Phase de combat — Nains (tour 3)"
    assert len(line["time"].split(":")) == 3


def test_the_log_keeps_only_its_last_lines():
    """A server running for a long time must not swell by one line per refused click."""
    for number in range(app.LINES_KEPT + 10):
        app.LOG.info("line %s", number)
    lines = app.log_lines()
    assert len(lines) == app.LINES_KEPT
    assert lines[0]["text"] == "line 10"
    assert lines[-1]["text"] == f"line {app.LINES_KEPT + 9}"


def test_the_lines_served_are_a_copy():
    """The queue goes on turning while the message travels: we do not hand out the reference."""
    app.LOG.info("first")
    lines = app.log_lines()
    app.LOG.info("second")
    assert texts(lines) == ["first"]


# --- What the page and the stream carry of it -----------------------------------------------------

def test_the_page_carries_the_log(client):
    app.LOG.info("Nouvelle partie : scénario 4")
    carried = read_hidden_field(client.get("/").get_data(as_text=True), "initial-log")
    assert "Nouvelle partie : scénario 4" in texts(carried)


def test_the_game_state_carries_the_log(client):
    app.LOG.info("Combat résolu : Défenseur Éliminé — dé 1, rapport 6-1")
    state = client.get("/game/state").json
    assert state["changed"] is True
    assert texts(state["log"])[-1] == "Combat résolu : Défenseur Éliminé — dé 1, rapport 6-1"


def test_the_shared_snapshot_carries_the_log():
    """It is that snapshot which travels in the stream: the log is in it, like the pieces."""
    app.LOG.info("Phase : Phase de combat — Nains (tour 1)")
    assert texts(app.shared_snapshot()["log"]) == ["Phase : Phase de combat — Nains (tour 1)"]


# --- The breakdown of the ratio computation ------------------------------------------------------
#
# The sentence alone, on a made-up breakdown: what happens on the map is exercised in
# `engine/tests/test_combat.py`, what goes to the log further down.

def sentence(strengths, target_strength, terrain, multiplier, die_bonus, roll):
    """The line the log would write for that computation."""
    breakdown = combat.RatioBreakdown(strengths, target_strength, terrain, multiplier,
                                      die_bonus, roll)
    return app.describe_the_ratio(
        combat.CombatResult(breakdown.outcome, [], breakdown.ratio, breakdown.die, breakdown))


def test_the_terrain_is_named_even_when_it_does_nothing():
    """That is what one came for: the plain is stated, like the mountain."""
    assert sentence([12], 2, "plaine", 1, 0, 1) \
        == "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1"


def test_the_terrain_that_multiplies_shows_its_computation():
    assert sentence([12], 8, "montagne", 3, 0, 4) \
        == "Rapport 1-2 : attaque 12 contre défense 8 × 3 = 24 (montagne) — dé 4"


def test_a_group_of_attackers_shows_its_strengths_one_by_one():
    assert sentence([12, 8], 8, "montagne", 3, 0, 4) \
        == "Rapport 1-2 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4"


def test_the_terrain_that_adds_to_the_die_shows_its_computation():
    assert sentence([12], 7, "bois", 2, 2, 3) \
        == "Rapport 1-2 : attaque 12 contre défense 7 × 2 = 14 (bois) — dé 3 + 2 = 5"


def test_a_die_outside_the_table_says_it_is_brought_back():
    """Table I has only six rows: without this, the addition would look wrong."""
    assert sentence([12], 2, "colline", 1, 2, 6) \
        == "Rapport 6-1 : attaque 12 contre défense 2 (colline) — dé 6 + 2 = 8, ramené à 6"


# --- Logging before marking the move -------------------------------------------------------------
#
# What each test checks: the move's line is **in the state published by that move**, and not in the
# next one. We subscribe to the broadcaster, play, and read what was deposited.

def last_published(subscriber):
    """The last state deposited with this subscriber. The box keeps only one - the most recent."""
    state = subscriber.wait(0)
    assert state is not None, "no move was published"
    return state


@pytest.fixture
def subscriber():
    """A stream open on the game, with no browser: the box where the server deposits its states."""
    return app.BROADCASTER.subscribe()


def test_the_phase_change_leaves_with_its_line(client, subscriber):
    client.post("/phase/next")
    assert texts(last_published(subscriber)["log"])[-1] \
        == "Phase : Phase de combat — Nains (tour 1)"


def test_the_combat_leaves_with_its_computation_and_its_result(client, subscriber, monkeypatch):
    """Two lines, and in that order: the computation, then the outcome.

    The order is not indifferent - the browser's column reads the other way round from the file,
    and that is what puts the outcome at the top, its breakdown just below.
    """
    monkeypatch.setattr(app, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)       # strength 12
    place(NEIGHBOUR, ARCHER)  # strength 2, on the plain -> ratio 6-1, die 1 -> DE
    client.post("/phase/next")  # the Dwarves' combat phase
    assert client.post("/combat",
                       json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["resolved"]
    assert texts(last_published(subscriber)["log"])[-2:] == [
        "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1",
        "Combat résolu : Défenseur Éliminé",
    ]


def test_the_seat_taken_leaves_with_its_line(application, anonymous_client, subscriber,
                                             seat_the_player):
    """The table is made of seats: taking one is a move, and it is told like any other."""
    identity = seat_the_player(application, anonymous_client, sides=[])
    answer = anonymous_client.post("/game/seat", json={"side": "alliance"})
    assert answer.json["seated"] is True
    assert texts(last_published(subscriber)["log"])[-1] \
        == f"Place prise : alliance par {identity['nickname']}"


def test_the_fresh_game_leaves_with_its_line(client, subscriber):
    client.post("/game/new")
    assert "Nouvelle partie : scénario 4" in texts(last_published(subscriber)["log"])


# --- The log on disk: files of a thousand lines, three archives behind ---
#
# `RotatingLog` counts lines where `RotatingFileHandler` counts bytes. What is worth exercising
# comes down to three points: that the file really is set aside at the threshold, that no more than
# asked is kept, and that a restarted server does not start again from zero.


def log_lines_into(handler, how_many, start=0):
    """`how_many` lines into the handler, numbered, without going through the global logger."""
    for number in range(start, start + how_many):
        handler.emit(logging.LogRecord("test", logging.INFO, __file__, 0,
                                       "line %s", (number,), None))


@pytest.fixture
def log_on_disk(tmp_path):
    """A rotating log of one's own, in a throwaway directory, closed on the way out."""
    opened = []

    def open_one(lines_per_file=3, files_kept=2):
        handler = app.RotatingLog(tmp_path / "logs" / "battle_log.log",
                                  lines_per_file, files_kept)
        opened.append(handler)
        return handler

    yield open_one
    for handler in opened:
        handler.close()


def test_the_logs_directory_is_created_as_needed(log_on_disk, tmp_path):
    """`logs/` is not versioned: a fresh clone has none, and the log must open it."""
    assert not (tmp_path / "logs").exists()
    log_on_disk()
    assert (tmp_path / "logs" / "battle_log.log").exists()


def test_the_file_is_set_aside_at_the_threshold(log_on_disk, tmp_path):
    handler = log_on_disk(lines_per_file=3)
    log = tmp_path / "logs" / "battle_log.log"
    log_lines_into(handler, 3)
    assert log.read_text(encoding="utf-8").splitlines() == ["line 0", "line 1", "line 2"]
    assert not log.with_suffix(".log.1").exists()

    log_lines_into(handler, 1, start=3)
    assert log.with_suffix(".log.1").read_text(encoding="utf-8").splitlines() \
        == ["line 0", "line 1", "line 2"]
    assert log.read_text(encoding="utf-8").splitlines() == ["line 3"]


def test_only_the_requested_archives_are_kept(log_on_disk, tmp_path):
    """Beyond that, the oldest is erased: the log does not fill the disk."""
    handler = log_on_disk(lines_per_file=2, files_kept=2)
    log_lines_into(handler, 20)
    files = sorted(path.name for path in (tmp_path / "logs").iterdir())
    assert files == ["battle_log.log", "battle_log.log.1", "battle_log.log.2"]
    # The last lines written, and nothing older than the two archives.
    assert (tmp_path / "logs" / "battle_log.log").read_text(
        encoding="utf-8").splitlines() == ["line 18", "line 19"]
    assert (tmp_path / "logs" / "battle_log.log.2").read_text(
        encoding="utf-8").splitlines() == ["line 14", "line 15"]


def test_a_restart_does_not_start_again_from_zero(log_on_disk, tmp_path):
    """The counter picks up what the file already carries: ten restarts do not make ten thousand
    lines in the same file."""
    log_lines_into(log_on_disk(lines_per_file=3), 2)
    log = tmp_path / "logs" / "battle_log.log"

    handler = log_on_disk(lines_per_file=3)
    assert handler.lines_written == 2
    log_lines_into(handler, 1, start=2)
    assert log.read_text(encoding="utf-8").splitlines() == ["line 0", "line 1", "line 2"]

    log_lines_into(handler, 1, start=3)
    assert log.read_text(encoding="utf-8").splitlines() == ["line 3"]


def test_the_applications_log_is_in_logs_at_the_root():
    """No longer in `application/`: the execution traces all live in the same place."""
    assert app.LOG_PATH.parent.name == "logs"
    assert app.LOG_PATH.parent.parent == Path(app.__file__).resolve().parent.parent
    assert (app.LINES_PER_FILE, app.LOGS_KEPT) == (1000, 3)
