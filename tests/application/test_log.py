"""The game log as the server serves it: its lines, and the moment they leave.

The log used to be only a local file; it is now shown, in a column under the card. Two things are
to be exercised on this side - that the page and the stream carry it, and that a line written at
the moment of a move **leaves with that move**. The second point rests on a call order:
`mark_a_move` photographs the game, log included, and any route logging after having saved would
push the browsers an account one move behind.

The rendering of the column is in `test_log_browser.py`.
"""

import logging
import logging.handlers
from pathlib import Path

import pytest

from tenebrae.application import current_game
from tenebrae.application.logs import battle_log, combat_sentences, movement_log, rotating_log
from tenebrae.application.config import ROOT
from tenebrae.engine import combat
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.retreat import RetreatOutcome
from tenebrae.engine.piece import CATALOGUE
from tenebrae.application.stream import Broadcaster

from tests.application.test_server import read_hidden_field, the_board

PLAIN = {"q": 1, "r": 26, "s": -27}
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}

DWARF = "nains-01-5-infanteries"  # alliance, strength 12
ARCHER = "yzent-03-8-archers"     # darkness, strength 2 -> ratio 6-1, die 1 -> DE
CROSSBOWMAN = "nains-02-4-arbaletriers"  # alliance, strength 6 -> ratio 3-1, die 4 -> DR


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map, as in `test_server.py`."""


@pytest.fixture(autouse=True)
def empty_log():
    """An empty log at the start, and empty on the way out.

    The queue is a module global, and it crosses engine: without this cleanup, a test would read the
    lines written by everything that came before it - starting with the browser engine.
    """
    battle_log.LOG_MEMORY.lines.clear()
    yield battle_log.LOG_MEMORY.lines
    battle_log.LOG_MEMORY.lines.clear()


@pytest.fixture(autouse=True)
def fresh_broadcaster(monkeypatch):
    """A broadcaster of one's own: the browser engine leave streams open behind them, and here we
    want to read what is published, not share it (see `test_stream.py`)."""
    monkeypatch.setattr(current_game, "BROADCASTER", Broadcaster())


def place(hexagon, key):
    current_game.BOARD.place(Hex(**hexagon), CATALOGUE[key])


def texts(lines):
    return [line["text"] for line in lines]


# --- What the log keeps --------------------------------------------------------------------------

def test_a_logged_line_carries_its_time_and_its_text():
    """And what is served is a copy: the queue goes on turning while the message travels, and we
    do not hand out the reference it turns in."""
    battle_log.LOG.info("Phase: %s (turn %s)", "Phase de combat — Nains", 3)
    line = battle_log.log_lines()[-1]
    assert line["text"] == "Phase: Phase de combat — Nains (turn 3)"
    assert len(line["time"].split(":")) == 3

    served = battle_log.log_lines()
    battle_log.LOG.info("one line more")
    assert texts(served)[-1] == "Phase: Phase de combat — Nains (turn 3)"


def test_the_log_keeps_only_its_last_lines():
    """A server running for a long time must not swell by one line per refused click."""
    for number in range(battle_log.LINES_KEPT + 10):
        battle_log.LOG.info("line %s", number)
    lines = battle_log.log_lines()
    assert len(lines) == battle_log.LINES_KEPT
    assert lines[0]["text"] == "line 10"
    assert lines[-1]["text"] == f"line {battle_log.LINES_KEPT + 9}"


# --- What the page and the stream carry of it -----------------------------------------------------

def test_the_page_and_the_state_both_carry_the_log(client):
    """The page carries it so a tab opens with the game already told; `/game/state` carries it so
    the fallback poll keeps up with it."""
    battle_log.LOG.info("New game: scenario 4")
    carried = read_hidden_field(the_board(client).get_data(as_text=True), "initial-log")
    assert "New game: scenario 4" in texts(carried)

    battle_log.LOG.info("Combat résolu : Défenseur Éliminé — dé 1, rapport 6-1")
    state = client.get("/game/state").json
    assert state["changed"] is True
    assert texts(state["log"])[-1] == "Combat résolu : Défenseur Éliminé — dé 1, rapport 6-1"


def test_the_shared_snapshot_carries_the_log():
    """It is that snapshot which travels in the stream: the log is in it, like the pieces."""
    battle_log.LOG.info("Phase: Phase de combat — Nains (turn 1)")
    assert texts(current_game.shared_snapshot()["log"]) == [
        "Phase: Phase de combat — Nains (turn 1)"]


# --- The breakdown of the ratio computation ------------------------------------------------------
#
# The sentence alone, on a made-up breakdown: what happens on the map is exercised in
# `tenebrae/engine/engine/test_combat.py`, what goes to the log further down.

def sentence(strengths, target_strength, terrain, multiplier, die_bonus, roll):
    """The line the log would write for that computation."""
    breakdown = combat.RatioBreakdown(strengths, target_strength, terrain, multiplier,
                                      die_bonus, roll)
    return combat_sentences.describe_the_ratio(
        combat.CombatResult(breakdown.outcome, [], breakdown.ratio, breakdown.die, breakdown))


def test_an_unresolved_combat_has_no_ratio_to_describe():
    """The routes look at `breakdown` before asking; asked all the same, the sentence refuses
    rather than describe nothing."""
    with pytest.raises(ValueError, match="not resolved"):
        combat_sentences.describe_the_ratio(combat.CombatResult(None, [], None, None))


@pytest.mark.parametrize("why, computation, written", [
    ("the terrain is named even when it changes nothing - that is what one came for",
     ([12], 2, "plaine", 1, 0, 1),
     "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1"),
    ("a terrain that multiplies shows its multiplication",
     ([12], 8, "montagne", 3, 0, 4),
     "Rapport 1-2 : attaque 12 contre défense 8 × 3 = 24 (montagne) — dé 4"),
    ("a group of attackers shows its strengths one by one",
     ([12, 8], 8, "montagne", 3, 0, 4),
     "Rapport 1-2 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4"),
    ("a terrain that helps the die shows its addition",
     ([12], 7, "bois", 2, 2, 3),
     "Rapport 1-2 : attaque 12 contre défense 7 × 2 = 14 (bois) — dé 3 + 2 = 5"),
    ("Table I has only six rows: without saying so, the addition would look wrong",
     ([12], 2, "colline", 1, 2, 6),
     "Rapport 6-1 : attaque 12 contre défense 2 (colline) — dé 6 + 2 = 8, ramené à 6"),
])
def test_the_sentence_shows_the_whole_computation(why, computation, written):
    assert sentence(*computation) == written, why


# --- The outcome's sentence ----------------------------------------------------------------------
#
# Each of the five outcomes of Table I names itself. A retreat that moved nobody says which
# exemption held: a result the table gave is never written as no result.

def outcome_sentence(outcome, retreats=()):
    """The line the log would write for that outcome and those fall-backs."""
    return combat_sentences.combat_message(
        combat.CombatResult(outcome, [], (1, 1), 1, retreats=retreats))


def fell_back():
    """One unit that found somewhere to go."""
    return RetreatOutcome(moves=[(Hex(**PLAIN), Hex(**NEIGHBOUR))])


@pytest.mark.parametrize("outcome, written", [
    ("DE", "Combat résolu : Défenseur Éliminé"),
    ("AE", "Combat résolu : Attaquant Éliminé"),
    ("EX", "Combat résolu : Échange — la cible est éliminée, "
           "avec juste assez d'attaquants"),
])
def test_each_elimination_names_itself(outcome, written):
    assert outcome_sentence(outcome) == written


@pytest.mark.parametrize("outcome, written", [
    ("DR", "Combat résolu : Défenseur Recule"),
    ("AR", "Combat résolu : Attaquant Recule"),
])
def test_a_retreat_names_itself_too(outcome, written):
    """Both retreats used to fall through to "sans effet": a unit pushed off its square read as a
    combat that had done nothing."""
    assert outcome_sentence(outcome, [fell_back()]) == written


def test_a_unit_that_fell_for_want_of_a_retreat_has_given_ground_all_the_same():
    """It left the board: the retreat did happen, and there is nothing to excuse."""
    fallen = RetreatOutcome(eliminated=Hex(**PLAIN))
    assert outcome_sentence("DR", [fallen]) == "Combat résolu : Défenseur Recule"


@pytest.mark.parametrize("outcome, written", [
    ("DR", "Combat résolu : Défenseur Recule — "
           "mais un défenseur en fort ou en château ne recule pas"),
    ("AR", "Combat résolu : Attaquant Recule — mais une unité qui tire ne recule pas"),
])
def test_a_retreat_that_moved_nobody_says_which_exemption_held(outcome, written):
    """The two exemptions of `tenebrae/engine/combat.py` leave the board as it was: without the
    note, the outcome would be followed by no fall-back line and explain nothing."""
    assert outcome_sentence(outcome) == written


def test_only_an_unresolved_combat_is_without_effect():
    """No target, or a strength that could not be read: there was no table to read."""
    assert combat_sentences.combat_message(combat.CombatResult(None, [], None, None)) \
        == "Combat résolu : sans effet"


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
    return current_game.BROADCASTER.subscribe()


def test_the_phase_change_leaves_with_its_line(client, subscriber):
    client.post("/phase/next")
    assert texts(last_published(subscriber)["log"])[-1] \
        == "Phase: Phase de combat — Nains (turn 1)"


def test_the_combat_leaves_with_its_computation_and_its_result(client, subscriber, monkeypatch):
    """Two lines, and in that order: the computation, then the outcome.

    The order is not indifferent - the browser's column reads the other way round from the file,
    and that is what puts the outcome at the top, its breakdown just below.
    """
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
    place(PLAIN, DWARF)       # strength 12
    place(NEIGHBOUR, ARCHER)  # strength 2, on the plain -> ratio 6-1, die 1 -> DE
    client.post("/phase/next")  # the Dwarves' combat phase
    assert client.post("/combat",
                       json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["resolved"]
    assert texts(last_published(subscriber)["log"])[-2:] == [
        "Rapport 6-1 : attaque 12 contre défense 2 (plaine) — dé 1",
        "Combat résolu : Défenseur Éliminé",
    ]


def test_the_combat_that_pushes_the_defender_back_tells_the_three_of_it(client, subscriber,
                                                                        monkeypatch):
    """The whole of a retreat, from the map to the log: the computation, the fall-back, the
    outcome that names it.

    The defender fires and is pushed back all the same, and the sentence says `Défenseur Recule`
    where it used to say `sans effet`.
    """
    monkeypatch.setattr(current_game, "roll_the_die", lambda: 4)
    place(PLAIN, CROSSBOWMAN)  # fires 4, its missile strength and not the 6 it closes with
    place(NEIGHBOUR, ARCHER)   # strength 2, on the plain -> ratio 2-1, die 4 -> DR
    client.post("/phase/next")  # the Dwarves' combat phase
    assert client.post("/combat",
                       json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["outcome"] == "DR"

    written = texts(last_published(subscriber)["log"])[-3:]
    assert written[0] == "Rapport 2-1 : attaque 4 contre défense 2 (plaine) — dé 4"
    assert written[1].startswith("Recul : 2,26,-28 → ")
    assert written[2] == "Combat résolu : Défenseur Recule"


def test_the_seat_taken_leaves_with_its_line(application, anonymous_client, subscriber,
                                             seat_the_player):
    """The table is made of seats: taking one is a move, and it is told like any other."""
    identity = seat_the_player(application, anonymous_client, sides=[])
    answer = anonymous_client.post("/game/seat", json={"side": "alliance"})
    assert answer.json["seated"] is True
    assert texts(last_published(subscriber)["log"])[-1] \
        == f"Seat taken: alliance by {identity['nickname']}"


def test_the_fresh_game_leaves_with_its_line(client, subscriber):
    client.post("/game/new")
    assert "New game: scenario 4" in texts(last_published(subscriber)["log"])


# --- The two logs on disk ---
#
# One `RotatingFileHandler` each - the standard one, by size - and one file each: the game the
# player reads, and the engine's movement trace, which must not land in it.


def file_handler(logger):
    """The rotating file the logger writes to."""
    return next(handler for handler in logger.handlers
                if isinstance(handler, logging.handlers.RotatingFileHandler))


def test_a_log_makes_its_directory_and_is_set_aside_at_its_size(tmp_path):
    """`logs/` is not versioned - a fresh clone has none - and the standard handler does not make
    it. Rotating itself is the handler's business, not ours: what is checked here is that it is
    opened with the size and the archives asked for, and that it does rotate."""
    path = tmp_path / "logs" / "battle_log.log"
    assert not path.parent.exists()

    handler = rotating_log.open_the_log(path, max_bytes=200, files_kept=2)
    try:
        assert path.exists()
        for number in range(60):
            handler.emit(logging.LogRecord("test", logging.INFO, __file__, 0,
                                           "line %s", (number,), None))
    finally:
        handler.close()

    files = sorted(one.name for one in (tmp_path / "logs").iterdir())
    assert files == ["battle_log.log", "battle_log.log.1", "battle_log.log.2"]
    assert path.read_text(encoding="utf-8").splitlines()[-1].endswith("line 59")


def test_fifty_kilobytes_a_file_and_three_archives_behind():
    """Both logs are opened on the same numbers: 200 KB apiece on disk, the oldest erased."""
    assert (rotating_log.MAX_BYTES, rotating_log.FILES_KEPT) == (50 * 1024, 3)
    for logger in (battle_log.LOG, movement_log.MOVEMENT_LOG):
        handler = file_handler(logger)
        assert (handler.maxBytes, handler.backupCount) == (50 * 1024, 3), logger.name


def test_both_logs_are_open_at_debug():
    """The level is not a switch to be found: the lines are written, in their file."""
    assert battle_log.LOG.level == logging.DEBUG
    assert movement_log.MOVEMENT_LOG.level == logging.DEBUG


def test_the_movement_trace_has_a_file_of_its_own():
    """Beside the game log, and not in it."""
    assert Path(file_handler(movement_log.MOVEMENT_LOG).baseFilename) \
        == movement_log.MOVEMENT_LOG_PATH
    assert movement_log.MOVEMENT_LOG_PATH.parent == battle_log.LOG_PATH.parent
    assert movement_log.MOVEMENT_LOG_PATH != battle_log.LOG_PATH


def test_the_movement_trace_says_nothing_in_the_players_column():
    """The column is the game told to the player: a movement recomputed at every click would drown
    it, which is the whole reason for the second file."""
    before = len(battle_log.log_lines())
    current_game.BOARD.moves(Hex(**PLAIN), CATALOGUE[DWARF])
    assert len(battle_log.log_lines()) == before


def test_wiring_the_movement_log_twice_does_not_double_its_lines():
    """One application per test, and `create_app` wires it each time: a second handler would write
    every line twice."""
    handlers = len(movement_log.MOVEMENT_LOG.handlers)
    movement_log.wire_the_movement_log()
    assert len(movement_log.MOVEMENT_LOG.handlers) == handlers


def test_the_applications_log_is_in_logs_at_the_root():
    """At the root of the repository, outside the `tenebrae` package: the execution traces all live
    in the same place, beside `.env`, and neither is versioned."""
    assert battle_log.LOG_PATH.parent.name == "logs"
    assert battle_log.LOG_PATH.parent.parent == ROOT
    assert ROOT == Path(__file__).resolve().parents[2]
    assert battle_log.LOG_PATH.name == "battle_log.log"
