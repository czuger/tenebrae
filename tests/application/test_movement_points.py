"""The movement allowance seen from the server: what the routes refuse, and what they tell.

The booklet allots each unit a capital of movement points for the phase. The engine holds the count
(`tests/engine/test_movement.py`); what is checked here is that the routes go through it - a second
move charged to the same unit, a click refused whatever the page shows, the greying the browser is
handed, the points given back at the phase change, and the count surviving a saved game.
"""

import pytest

from tenebrae.application import current_game
from tenebrae.application.current_game import ALLOWANCES, BOARD
from tenebrae.application.logs.battle_log import log_lines
from tenebrae.application.routes.movement import EXHAUSTED_MESSAGE
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import CATALOGUE
from tests.engine.plains import well_surrounded_plain


def a_line_of_bare_plain(length=4):
    """`length` squares in a row, each one point of movement from the last.

    Looked up on the game map rather than hard-coded, as everywhere the engine is measured: a road
    under one of them would cost a third of a point instead of one, and every count below would be
    off without saying why.
    """
    centre = well_surrounded_plain(radius=length - 1)
    step = centre.neighbours()[0]
    q, r, s = step.q - centre.q, step.r - centre.r, step.s - centre.s
    # The three coordinates alone: this is what the routes take as `origin` and `destination`, and
    # `Hex.to_dict` would add the terrain to it.
    return [{"q": centre.q + k * q, "r": centre.r + k * r, "s": centre.s + k * s}
            for k in range(length)]


# Four squares in a row: enough for a dwarf's three points, and one square more to be refused.
FIRST, SECOND, THIRD, FOURTH = a_line_of_bare_plain()

DWARF = "nains-01-5-infanteries"       # alliance, 3 movement points
ELF = "elfes-01-5-infanteries"         # alliance, 4 movement points
ORC = "orques-01-15-infanteries"       # darkness, 4 movement points


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """A deserted map before and after, allowances included (see `conftest.deserted_map`)."""


def place(hexagon, key):
    """Places a piece on the server's board, as a layout would."""
    BOARD.place(Hex(**hexagon), CATALOGUE[key])


def move(client, origin, destination):
    """Asks the server to play one move and gives back what it answered."""
    return client.post("/move", json={"origin": origin, "destination": destination}).json


def key(hexagon):
    """The "q,r,s" key of a serialised hexagon."""
    return f"{hexagon['q']},{hexagon['r']},{hexagon['s']}"


def squares(hexagons):
    """The "q,r,s" keys of a list of serialised hexagons."""
    return [key(hexagon) for hexagon in hexagons]


def test_the_plain_is_bare_where_these_tests_walk():
    """What `a_line_of_bare_plain` promises, said out loud: four squares in a row, all plain, each
    one point from the last. Every count below rests on it."""
    line = [Hex(**square) for square in (FIRST, SECOND, THIRD, FOURTH)]
    assert all(square.terrain == "plaine" for square in line)
    assert all(one.distance(next_one) == 1 for one, next_one in zip(line, line[1:]))
    assert line[0].distance(line[-1]) == 3


def test_each_move_is_charged_to_the_unit(client):
    place(FIRST, DWARF)

    first = move(client, FIRST, SECOND)
    assert first["allowed"] is True
    assert (first["movement"], first["cost"], first["remaining"]) == (3, 1.0, 2.0)
    assert first["exhausted"] is False

    second = move(client, SECOND, THIRD)
    assert (second["cost"], second["remaining"]) == (1.0, 1.0)


def test_the_unit_stops_when_its_points_are_gone(client):
    """Three points, three squares, and the fourth click finds nothing left - on the server, which
    is the only place that decides it."""
    place(FIRST, DWARF)
    move(client, FIRST, SECOND)
    move(client, SECOND, THIRD)
    third = move(client, THIRD, FOURTH)
    assert third["exhausted"] is True

    refused = move(client, FOURTH, THIRD)
    assert refused["allowed"] is False
    assert refused["message"] == EXHAUSTED_MESSAGE
    assert BOARD.piece_on(Hex(**FOURTH)).key == DWARF
    assert BOARD.piece_on(Hex(**THIRD)) is None


def test_the_refusal_is_written_where_the_player_reads_it(client):
    place(FIRST, DWARF)
    for origin, destination in ((FIRST, SECOND), (SECOND, THIRD), (THIRD, FOURTH)):
        move(client, origin, destination)
    move(client, FOURTH, THIRD)

    assert [line["text"] for line in log_lines()][-1] == EXHAUSTED_MESSAGE


def test_a_unit_with_nothing_left_is_offered_no_square(client):
    """`/moves` answers the click that lands on a greyed counter: no ghost, and the reason."""
    place(FIRST, DWARF)
    for origin, destination in ((FIRST, SECOND), (SECOND, THIRD), (THIRD, FOURTH)):
        move(client, origin, destination)

    answer = client.get("/moves", query_string=FOURTH).json
    assert answer["hexagons"] == []
    assert answer["message"] == EXHAUSTED_MESSAGE
    assert (answer["movement"], answer["remaining"], answer["exhausted"]) == (3, 0.0, True)


def test_what_is_offered_shrinks_with_what_is_left(client):
    """The reach is computed on the remainder, so a unit that has walked is offered less than one
    that has not - and never a square its remaining points cannot pay for."""
    place(FIRST, ELF)
    whole = client.get("/moves", query_string=FIRST).json
    assert whole["remaining"] == 4.0

    move(client, FIRST, SECOND)
    left = client.get("/moves", query_string=SECOND).json
    assert left["remaining"] == 3.0
    assert 0 < len(left["hexagons"]) < len(whole["hexagons"])
    # And what it is offered is a subset of what four points reached: a point spent buys nothing.
    assert set(squares(left["hexagons"])) <= set(squares(whole["hexagons"])) | {key(FIRST)}


def test_the_greyed_units_are_told_to_the_browser(client):
    """The page greys out what will refuse the click, and it is the server that names it - the same
    channel the combat register uses (`unavailable`)."""
    place(FIRST, DWARF)
    place(THIRD, ORC)
    assert client.get("/phase").json["unavailable"]["movers"] == []

    move(client, FIRST, SECOND)
    move(client, SECOND, FIRST)
    move(client, FIRST, SECOND)

    unavailable = client.get("/phase").json["unavailable"]
    assert squares(unavailable["movers"]) == [key(SECOND)]
    # The other side is waiting its turn, not refusing anything: it is not greyed out.
    assert key(THIRD) not in squares(unavailable["movers"])


def test_a_combat_phase_greys_nobody_for_movement(client):
    """The list belongs to the movement phase; in combat the greying is the combat register's."""
    place(FIRST, DWARF)
    move(client, FIRST, SECOND)
    move(client, SECOND, THIRD)
    move(client, THIRD, FOURTH)

    assert client.post("/phase/next").json["unavailable"]["movers"] == []


def test_the_next_phase_gives_the_points_back(client):
    """The allowance is the phase's: stepping to the next one hands every unit its capital again,
    exactly as it empties the combat register."""
    place(FIRST, DWARF)
    for origin, destination in ((FIRST, SECOND), (SECOND, THIRD), (THIRD, FOURTH)):
        move(client, origin, destination)
    assert ALLOWANCES.has_moved(key(FOURTH))

    client.post("/phase/next")   # the Dwarves' combat phase
    client.post("/phase/next")   # the Orcs' movement phase
    client.post("/phase/next")   # the Orcs' combat phase
    client.post("/phase/next")   # the Dwarves again

    assert not ALLOWANCES.has_moved(key(FOURTH))
    assert client.get("/moves", query_string=FOURTH).json["remaining"] == 3.0
    assert move(client, FOURTH, THIRD)["allowed"] is True


def test_a_move_refused_outside_the_phase_charges_nothing(client):
    """A refusal is not a move: the unit keeps its points for the phase in which it may spend
    them."""
    place(FIRST, DWARF)
    client.post("/phase/next")   # the Dwarves' combat phase

    assert move(client, FIRST, SECOND)["allowed"] is False
    assert not ALLOWANCES.has_moved(key(FIRST))


def test_a_move_out_of_reach_charges_nothing(client):
    """Refused by the map rather than by the allowance: nothing was walked, nothing is owed."""
    place(FIRST, DWARF)
    far = {"q": 30, "r": 2, "s": -32}

    refused = move(client, FIRST, far)
    assert refused["allowed"] is False
    assert refused["remaining"] == 3.0
    assert not ALLOWANCES.has_moved(key(FIRST))


def test_the_count_survives_the_saved_game(client, application):
    """A game reopened must not hand back points already walked: the allowance is written into the
    document, as an exact fraction, and read back with the board."""
    the_game = client.get("/game", follow_redirects=True)
    assert the_game.status_code == 200
    origin = next(iter(current_game.SCENARIO.placement))
    walked = BOARD.moves(Hex.from_key(origin))[0]
    played = move(client, Hex.from_key(origin).to_dict(), walked.to_dict())
    assert played["allowed"] is True
    left = played["remaining"]

    saved = current_game.snapshot_the_game()
    assert saved["movement_left"][walked.key]

    ALLOWANCES.reset()
    current_game.restore_the_game(current_game.GAME_ID, saved)
    assert client.get("/moves", query_string=walked.to_dict()).json["remaining"] == left


def test_a_game_saved_before_the_count_existed_reopens_playable(client):
    """No migration is owed: a document with no allowance in it is a phase in which nobody has
    moved, which is what a movement phase starts as."""
    place(FIRST, DWARF)
    state = current_game.snapshot_the_game()
    del state["movement_left"]

    current_game.restore_the_game("whatever", state)

    assert client.get("/moves", query_string=FIRST).json["remaining"] == 3.0
