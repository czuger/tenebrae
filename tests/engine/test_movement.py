"""The movement allowance: what a unit has left, and what happens when it has nothing.

The booklet allots each unit a capital of points "during their active phase", not a rate per click.
These tests hold the two halves of that: the register that counts, and the entry point that refuses
a unit which has spent everything.

As everywhere in the engine, the terrain is looked up on the game map rather than hard-coded, so
that a fix to the map does not break the arithmetic: `well_surrounded_plain` gives a corner where
every step costs exactly one point.
"""

from fractions import Fraction

import pytest

from tenebrae.engine import movement
from tenebrae.engine.board import Board
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.movement_register import MovementRegister
from tenebrae.engine.piece import piece
from tests.engine.plains import ring_of, well_surrounded_plain

DWARF = "nains-01-5-infanteries"           # alliance, 3 movement points
ELF = "elfes-01-5-infanteries"             # alliance, 4 movement points
MARKER = "marqueurs-03-paralysie"          # no movement printed: it never budges


@pytest.fixture
def plain():
    """A centre of bare plain and three consecutive squares of its ring."""
    centre = well_surrounded_plain()
    c, x1, x2, _ = ring_of(centre)
    return centre, c, x1, x2


class TestTheRegister:
    def test_a_unit_that_has_not_moved_has_its_whole_allowance(self):
        register = MovementRegister()
        assert register.points_left("1,26,-27", 3) == Fraction(3)
        assert not register.has_moved("1,26,-27")
        assert not register.is_exhausted("1,26,-27", 3)

    def test_what_is_spent_travels_with_the_unit(self):
        """The allowance is written on the square arrived at and cleared from the one left: the
        engine designates a unit by where it stands, and the square left behind must say nothing
        about the counter that takes it over next."""
        register = MovementRegister()
        assert register.spend("1,26,-27", "2,26,-28", Fraction(1), 3) == Fraction(2)

        assert register.points_left("2,26,-28", 3) == Fraction(2)
        assert register.has_moved("2,26,-28")
        assert not register.has_moved("1,26,-27")
        assert register.points_left("1,26,-27", 3) == Fraction(3)

    def test_the_allowance_runs_out_and_never_goes_below_nothing(self):
        register = MovementRegister()
        register.spend("1,26,-27", "2,26,-28", Fraction(3), 3)
        assert register.points_left("2,26,-28", 3) == Fraction(0)
        assert register.is_exhausted("2,26,-28", 3)

        register.spend("2,26,-28", "3,26,-29", Fraction(2), 3)
        assert register.points_left("3,26,-29", 3) == Fraction(0)

    def test_a_new_phase_gives_every_unit_its_points_back(self):
        register = MovementRegister()
        register.spend("1,26,-27", "2,26,-28", Fraction(3), 3)
        assert register.reset() is register
        assert not register.has_moved("2,26,-28")
        assert register.points_left("2,26,-28", 3) == Fraction(3)

    def test_a_saved_register_reopens_on_the_very_fraction_it_was_left_with(self):
        """A road costs a third of a point: written as a float it would come back drifting, and a
        unit would end its phase owing or owning a fraction it never walked."""
        register = MovementRegister()
        register.spend("1,26,-27", "2,26,-28", Fraction(1, 3), 3)
        written = register.to_dict()
        assert written == {"remaining": {"2,26,-28": "8/3"}}

        assert MovementRegister().restore(written["remaining"]).points_left("2,26,-28", 3) \
            == Fraction(8, 3)


class TestSpendingOnTheBoard:
    def test_a_move_is_charged_to_the_unit_that_played_it(self, plain):
        centre, c, _, _ = plain
        board = Board([(centre, piece(DWARF))])
        register = MovementRegister()

        outcome = movement.move(board, register, centre, c)

        assert outcome.allowed
        assert outcome.cost == Fraction(1)
        assert outcome.remaining == Fraction(2)
        assert board.piece_on(c).key == DWARF
        assert board.piece_on(centre) is None

    def test_the_same_unit_may_walk_on_until_its_points_are_gone(self, plain):
        """Three points, three squares of plain, and the fourth click is refused: the capital is
        the phase's, not the click's."""
        centre, c, x1, x2 = plain
        board = Board([(centre, piece(DWARF))])
        register = MovementRegister()

        assert movement.move(board, register, centre, c).allowed
        assert movement.move(board, register, c, x1).allowed
        assert movement.move(board, register, x1, x2).allowed
        assert movement.points_left(board, register, x2) == Fraction(0)

        refused = movement.move(board, register, x2, centre)
        assert not refused.allowed
        assert refused.refusal == movement.EXHAUSTED
        assert board.piece_on(x2).key == DWARF

    def test_what_is_left_is_what_the_walk_is_offered(self, plain):
        """A unit with one point left is offered one square, not the four its counter is printed
        for: the reach is computed on the remainder."""
        centre, c, _, _ = plain
        board = Board([(centre, piece(ELF))])
        register = MovementRegister()
        movement.move(board, register, centre, c)

        left = movement.points_left(board, register, c)
        assert left == Fraction(3)
        assert len(board.moves(c, budget=left)) < len(board.moves(c))
        assert all(square.distance(c) <= 3 for square in board.moves(c, budget=left))

    def test_a_move_beyond_what_is_left_is_refused_as_any_other_move_too_far(self, plain):
        centre, c, x1, x2 = plain
        board = Board([(centre, piece(DWARF))])
        register = MovementRegister()
        movement.move(board, register, centre, c)      # two points left
        movement.move(board, register, c, x1)          # one point left

        far = next(square for square in x1.neighbours()[0].neighbours()
                   if square.distance(x1) == 2 and board.piece_on(square) is None)
        refused = movement.move(board, register, x1, far)

        assert not refused.allowed
        assert refused.refusal == movement.ILLEGAL
        assert refused.remaining == Fraction(1)
        assert board.piece_on(x1).key == DWARF

    def test_a_counter_that_never_moves_is_exhausted_from_the_start(self, plain):
        """A marker carries no movement: it has nothing to spend, and says so before being asked
        rather than after."""
        centre, c, _, _ = plain
        board = Board([(centre, piece(MARKER))])
        register = MovementRegister()

        assert movement.is_exhausted(board, register, centre)
        assert not movement.move(board, register, centre, c).allowed

    def test_the_squares_the_browser_greys_out_are_those_with_nothing_left(self, plain):
        centre, c, x1, x2 = plain
        board = Board([(centre, piece(DWARF)), (x2, piece(ELF))])
        register = MovementRegister()
        assert movement.exhausted_squares(board, register) == []

        movement.move(board, register, centre, c)
        movement.move(board, register, c, x1)
        movement.move(board, register, x1, centre)

        assert movement.exhausted_squares(board, register) == [centre.key]
        assert movement.exhausted_squares(board, register, ["tenebres"]) == []

    def test_a_board_questioned_by_hand_charges_nobody(self, plain):
        """An empty origin square moves nothing and must therefore leave no trace: an allowance
        written on a square nobody stands on would be charged to whoever takes it next."""
        centre, c, _, _ = plain
        board = Board()
        register = MovementRegister()

        assert movement.move(board, register, centre, c).allowed
        assert not register.has_moved(c.key)


class TestTheAllowanceAndTheOtherRules:
    def test_a_unit_stopped_by_a_zone_of_control_keeps_what_it_did_not_spend(self, plain):
        """The two limits are not the same one: the zone of control stops the walk, the allowance
        counts what the walk cost. A unit that stopped after one square still has two points."""
        centre, c, x1, _ = plain
        opponent = next(square for square in x1.neighbours()
                        if square.distance(centre) == 2 and square != c)
        board = Board([(centre, piece(DWARF)),
                       (opponent, piece("orques-01-15-infanteries"))])
        register = MovementRegister()

        outcome = movement.move(board, register, centre, x1)

        assert outcome.allowed
        assert outcome.remaining == Fraction(2)
        # It stopped where the zone of control made it stop, and the two points it did not spend
        # are still its own: what it may reach next is what two points reach, no more.
        reachable = board.moves(x1, budget=outcome.remaining)
        assert reachable and all(square.distance(x1) <= 2 for square in reachable)
        # The zone of control it walked into is still refused to it, allowance or no allowance.
        assert opponent.key not in {square.key for square in reachable}


def test_the_hexagon_walk_says_what_each_square_costs():
    """`reach` is what `moves` is built on: the same squares, each with the points it took to get
    there, which is what a unit spending from a capital must be charged."""
    centre = well_surrounded_plain()
    costs = centre.reach(2)

    assert set(costs) == {hexagon.key for hexagon in centre.moves(2)}
    assert centre.key not in costs
    for neighbour in centre.neighbours():
        assert costs[neighbour.key] == Fraction(1)
    assert set(costs.values()) == {Fraction(1), Fraction(2)}


def test_a_fractional_budget_walks_as_far_as_it_reaches():
    """The budget is a fraction as soon as a unit has walked a road: half a point buys nothing on
    the plain, and the walk must say so rather than round it up."""
    centre = well_surrounded_plain()
    assert centre.reach(Fraction(1, 2)) == {}
    assert centre.reach(Fraction(3, 2)).keys() == {hexagon.key for hexagon in centre.neighbours()}


def test_the_map_is_never_left_by_a_charged_move():
    """The board refuses a square off the map before anything is charged: `Hex` raises, and the
    register keeps its count intact - there is nothing here that catches an exception halfway."""
    centre = well_surrounded_plain()
    board = Board([(centre, piece(DWARF))])
    register = MovementRegister()

    off_the_map = Hex(1000, -500, -500)
    assert not movement.move(board, register, centre, off_the_map).allowed
    assert not register.has_moved(centre.key)
    assert board.piece_on(centre).key == DWARF
