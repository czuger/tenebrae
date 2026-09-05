"""The first victory condition: a side whose troops have all been annihilated has lost.

`tenebrae/engine/victory.py` counts, and nothing more - it is the application that knows whether a
game is being played at all. What is exercised here is what counts as a troop: a marker is not one,
and a counter with nothing printed on it is not one either.
"""

from tenebrae.engine import victory
from tenebrae.engine.board import Board
from tenebrae.engine.piece import ALLIANCE, DARKNESS, piece

from tests.engine.plains import ring_of, well_surrounded_plain

DWARF = "nains-01-5-infanteries"       # alliance
ORC = "orques-01-15-infanteries"       # darkness
MARKER = "marqueurs-03-paralysie"      # neutral, nothing printed on it

SIDES = (ALLIANCE, DARKNESS)


def figure():
    """A centre of bare plain and three squares around it."""
    centre = well_surrounded_plain()
    first, second, third, _ = ring_of(centre)
    return centre, first, second, third


def test_a_side_with_units_on_the_board_has_troops():
    centre, first, *_ = figure()
    board = Board([(centre, piece(ORC)), (first, piece(DWARF))])

    assert victory.troops_of(board, ALLIANCE) == [first.key]
    assert victory.troops_of(board, DARKNESS) == [centre.key]


def test_both_sides_standing_is_nobody_annihilated():
    centre, first, *_ = figure()
    board = Board([(centre, piece(ORC)), (first, piece(DWARF))])

    assert victory.annihilated_sides(board, SIDES) == []


def test_the_side_with_nothing_left_is_named():
    centre, *_ = figure()
    board = Board([(centre, piece(DWARF))])

    assert victory.annihilated_sides(board, SIDES) == [DARKNESS]


def test_an_empty_board_annihilates_both():
    """What the counting says; whether that is a game lost is not for this module to say."""
    assert victory.annihilated_sides(Board(), SIDES) == list(SIDES)


def test_a_marker_is_not_a_troop():
    """It is neutral, it fights nobody, and a side is not saved by one left lying about."""
    centre, first, *_ = figure()
    board = Board([(centre, piece(DWARF)), (first, piece(MARKER))])

    assert victory.troops_of(board, "neutre") == []
    assert victory.annihilated_sides(board, SIDES) == [DARKNESS]


def test_the_squares_come_back_in_order():
    """As everywhere else in the engine: by square key, so that two identical games read alike."""
    centre, first, second, third = figure()
    board = Board([(square, piece(DWARF)) for square in (centre, first, second, third)])

    assert victory.troops_of(board, ALLIANCE) == sorted(
        square.key for square in (centre, first, second, third))
