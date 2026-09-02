"""Zones of control: what an opponent's presence forbids to movement.

The reference hexagons are looked up on the map by `plains.py`, and not hard-coded: the test thus
survives a terrain fix.
"""

import pytest

from tenebrae.engine.hexagon import Hex, zone_of_control
from tests.engine.plains import MAXIMUM_BUDGET, minimum_budget, ring_of, well_surrounded_plain


@pytest.fixture(scope="module")
def ring():
    """The opposing unit **A**, and three consecutive squares of its zone of control: C, X1, X2.

    This is the figure of the booklet's example: C stands in A's zone of control, X1 and X2 too,
    and C would like to reach X2 by way of X1.
    """
    a = well_surrounded_plain()
    c, x1, x2, _ = ring_of(a)
    return a, c, x1, x2


@pytest.fixture(scope="module")
def zone(ring):
    """The six squares A holds under its control."""
    a, *_ = ring
    return zone_of_control([a])


class TestZoneOfControl:
    """The function that says which squares a unit holds under its control."""

    def test_it_is_the_squares_around_the_unit_and_not_its_own(self, ring):
        """Six in open country, fewer at the map's edge - it is `neighbours` that decides, and
        `neighbours` never leaves the map."""
        a, *_ = ring
        assert zone_of_control([a]) == {neighbour.key for neighbour in a.neighbours()}
        assert len(zone_of_control([a])) == 6
        assert a.key not in zone_of_control([a])

        corner = Hex(0, 0, 0)
        assert zone_of_control([corner]) == {neighbour.key for neighbour in corner.neighbours()}
        assert len(zone_of_control([corner])) < 6

    def test_the_zones_of_several_units_join_up(self, ring):
        a, c, *_ = ring
        assert zone_of_control([a, c]) == zone_of_control([a]) | zone_of_control([c])

    def test_without_a_unit_there_is_no_zone(self):
        assert zone_of_control([]) == frozenset()


class TestMovementUnderControl:
    """What the zone changes about the walk, from the origin square to the destination."""

    def test_without_an_opponent_the_walk_is_the_terrains(self, ring):
        _, c, *_ = ring
        assert c.moves(4, enemies=(), under_control=()) == c.moves(4)

    def test_one_enters_a_zone_at_the_terrain_rate(self, ring):
        """"Without spending additional points": the square costs what its plain costs."""
        a, c, x1, x2 = ring
        from_further_out = next(neighbour for neighbour in c.neighbours()
                                if neighbour.distance(a) == 2)
        assert minimum_budget(from_further_out, c, under_control=zone_of_control([a])) == 1

    def test_one_stops_as_soon_as_one_has_entered(self, ring, zone):
        """Once in the zone, one goes no further: A's square stays out of reach."""
        a, c, *_ = ring
        from_further_out = next(neighbour for neighbour in c.neighbours()
                                if neighbour.distance(a) == 2)
        reached = from_further_out.moves(MAXIMUM_BUDGET, under_control=zone)
        assert c in reached
        assert a not in reached

    def test_one_does_not_pass_from_one_controlled_square_to_another(self, ring, zone):
        """C is already in the zone: the direct step to X1, adjacent though it is, is forbidden."""
        _, c, x1, _ = ring
        assert x1 in c.moves(1)
        assert x1 not in c.moves(1, under_control=zone)

    def test_one_leaves_the_zone_one_stands_in(self, ring, zone):
        """A unit starting its move under control can leave it - through a free square."""
        a, c, *_ = ring
        exit_square = next(neighbour for neighbour in c.neighbours()
                           if neighbour.distance(a) == 2)
        assert exit_square in c.moves(1, under_control=zone)

    def test_the_detour_of_the_booklets_example(self, ring, zone):
        """"It will therefore spend 4 movement points instead of 2."

        C, under A's control, cannot reach X2 by way of X1: it must leave the zone, go round X1 the
        long way and re-enter at X2. A holding its square, C does not cross it either. The
        booklet's count comes out exactly right, square for square.
        """
        a, c, _, x2 = ring
        assert minimum_budget(c, x2) == 2
        assert minimum_budget(c, x2, enemies={a.key}, under_control=zone) == 4

    def test_the_zone_reduces_the_reach(self, ring, zone):
        _, c, *_ = ring
        assert len(c.moves(4, under_control=zone)) < len(c.moves(4))


class TestHeldSquares:
    """The squares occupied by the opponent, which movement does not enter."""

    def test_one_does_not_enter_an_enemy_square(self, ring):
        a, c, *_ = ring
        assert a in c.moves(1)
        assert a not in c.moves(MAXIMUM_BUDGET, enemies={a.key})

    def test_an_enemy_square_is_not_crossed(self, ring):
        """What was only reachable through A now calls for a detour."""
        a, c, x1, x2 = ring
        opposite = next(neighbour for neighbour in a.neighbours()
                        if neighbour.distance(c) == 2 and neighbour.distance(x1) == 2)
        assert minimum_budget(c, opposite) == 2
        assert minimum_budget(c, opposite, enemies={a.key}) > 2

    def test_the_two_rules_add_up(self, ring, zone):
        a, c, *_ = ring
        reached = c.moves(4, enemies={a.key}, under_control=zone)
        assert a not in reached
        assert reached and len(reached) < len(c.moves(4))
