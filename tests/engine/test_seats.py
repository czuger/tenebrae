"""The seating register: who holds which side, and what it refuses.

These engine bear on the class alone, with no request and no database: `Seats` knows nothing but
player identifiers and side names.
"""

import pytest

from tenebrae.engine.models.seats import Seats

ALLIANCE, DARKNESS = "alliance", "tenebres"

DWARF_PLAYER = "100000000000000001"
ORC_PLAYER = "100000000000000002"


@pytest.fixture
def table():
    return Seats()


def test_a_fresh_table_has_all_its_sides_free(table):
    assert table.is_free(ALLIANCE) and table.is_free(DARKNESS)
    assert table.occupant(ALLIANCE) is None


def test_sitting_down_takes_the_side(table):
    table.seat(ALLIANCE, DWARF_PLAYER)
    assert table.occupant(ALLIANCE) == DWARF_PLAYER
    assert not table.is_free(ALLIANCE)
    assert table.holds(DWARF_PLAYER, ALLIANCE)


def test_the_side_next_door_stays_free(table):
    table.seat(ALLIANCE, DWARF_PLAYER)
    assert table.is_free(DARKNESS)
    assert not table.holds(DWARF_PLAYER, DARKNESS)


def test_an_occupied_seat_is_not_taken_over(table):
    table.seat(ALLIANCE, DWARF_PLAYER)
    with pytest.raises(ValueError):
        table.seat(ALLIANCE, ORC_PLAYER)
    assert table.occupant(ALLIANCE) == DWARF_PLAYER


def test_sitting_back_down_in_ones_own_seat_changes_nothing(table):
    table.seat(ALLIANCE, DWARF_PLAYER).seat(ALLIANCE, DWARF_PLAYER)
    assert table.occupant(ALLIANCE) == DWARF_PLAYER


def test_one_and_the_same_player_may_hold_both_sides(table):
    """The register defends a single invariant: one side, one occupant.

    It is the route that refuses a second side to whoever already holds one. The test suite, for
    its part, plays the game by itself from both sides - and it is that separation which allows
    it.
    """
    table.seat(ALLIANCE, DWARF_PLAYER).seat(DARKNESS, DWARF_PLAYER)
    assert table.sides_of(DWARF_PLAYER) == [ALLIANCE, DARKNESS]


def test_a_spectators_sides_are_an_empty_list(table):
    table.seat(ALLIANCE, DWARF_PLAYER)
    assert table.sides_of(ORC_PLAYER) == []


def test_nobody_holds_a_side_for_an_unknown_player(table):
    assert table.holds(None, ALLIANCE) is False


def test_freeing_gives_the_side_back(table):
    table.seat(ALLIANCE, DWARF_PLAYER).free(ALLIANCE)
    assert table.is_free(ALLIANCE)
    assert table.sides_of(DWARF_PLAYER) == []


def test_freeing_a_free_side_makes_no_fuss(table):
    table.free(ALLIANCE)
    assert table.is_free(ALLIANCE)


def test_clearing_lifts_the_whole_table(table):
    table.seat(ALLIANCE, DWARF_PLAYER).seat(DARKNESS, ORC_PLAYER).clear()
    assert table.is_free(ALLIANCE) and table.is_free(DARKNESS)


def test_the_register_serialises_and_restores(table):
    table.seat(ALLIANCE, DWARF_PLAYER).seat(DARKNESS, ORC_PLAYER)
    resumed = Seats().restore(table.to_dict()["seats"])
    assert resumed.occupant(ALLIANCE) == DWARF_PLAYER
    assert resumed.occupant(DARKNESS) == ORC_PLAYER


def test_restore_replaces_the_previous_seats(table):
    table.seat(ALLIANCE, DWARF_PLAYER)
    table.restore({DARKNESS: ORC_PLAYER})
    assert table.is_free(ALLIANCE)
    assert table.occupant(DARKNESS) == ORC_PLAYER


def test_restore_without_seats_lifts_the_table(table):
    """A game saved before players existed has no seats: it stays resumable."""
    table.seat(ALLIANCE, DWARF_PLAYER)
    table.restore(None)
    assert table.is_free(ALLIANCE)
