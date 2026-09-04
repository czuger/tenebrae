"""Retreat or elimination: where a unit forced to fall back goes, and what it costs its friends.

The figures are built on the map, not hard-coded: a corner of bare plain wide enough to hold a
unit, the ring of its friends and the ring beyond (`tests/engine/plains.py`), so that a terrain fix
does not turn these tests red.
"""

import pytest

from tenebrae.engine.board import Board
from tenebrae.engine.hexagon import MAP, Hex
from tenebrae.engine.piece import piece
from tenebrae.engine.retreat import (fall_back, fall_back_together, retreat_squares,
                                     shortest_chain)
from tests.engine.plains import surroundings, well_surrounded_plain

DWARF = "nains-01-5-infanteries"     # alliance
ELF = "elfes-01-5-infanteries"       # alliance
ORC = "orques-01-15-infanteries"     # darkness


def keys(hexagons):
    """The square keys of an iterable of hexagons, in order."""
    return [hexagon.key for hexagon in hexagons]


def ring(centre, radius):
    """The squares exactly `radius` squares from `centre`, sorted by key."""
    return sorted((hexagon for hexagon in surroundings(centre, radius)
                   if hexagon.distance(centre) == radius), key=lambda square: square.key)


def plain_beside(terrain):
    """A bare plain square with `terrain` next door, for the impassable-terrain tests."""
    for key, elements in MAP.items():
        if elements != ("plaine",):
            continue
        hexagon = Hex.from_key(key)
        if any(MAP.get(neighbour.key, ("",))[0] == terrain for neighbour in hexagon.neighbours()):
            return hexagon
    raise AssertionError(f"no plain square beside a {terrain} on the map")


@pytest.fixture
def plain():
    """A square of bare plain with three rings of bare plain around it."""
    return well_surrounded_plain(radius=3)


# --- Falling back on one's own -------------------------------------------------------------------


class TestTheSquaresOfferedToARetreat:
    def test_an_isolated_unit_may_fall_back_anywhere_around_it(self, plain):
        board = Board([(plain, piece(DWARF))])
        assert keys(retreat_squares(board, plain, ())) == keys(ring(plain, 1))

    def test_a_square_a_friend_occupies_is_not_free(self, plain):
        occupied, *_ = ring(plain, 1)
        board = Board([(plain, piece(DWARF)), (occupied, piece(ELF))])
        assert occupied.key not in keys(retreat_squares(board, plain, ()))

    def test_a_square_under_enemy_control_is_refused(self, plain):
        """"It is forbidden to retreat into an enemy zone of control." """
        board = Board([(plain, piece(DWARF))])
        controlled = {square.key for square in ring(plain, 1)[:2]}
        assert keys(retreat_squares(board, plain, controlled)) == keys(ring(plain, 1)[2:])

    @pytest.mark.parametrize("terrain", ["lac", "riviere"])
    def test_a_lake_or_a_river_is_refused(self, terrain):
        """The two the booklet names: no unit stands there, so no unit falls back there."""
        shore = plain_beside(terrain)
        board = Board([(shore, piece(DWARF))])
        offered = keys(retreat_squares(board, shore, ()))
        water = [neighbour.key for neighbour in shore.neighbours()
                 if neighbour.terrain == terrain]
        assert water
        assert not set(water) & set(offered)


class TestFallingBack:
    def test_the_unit_steps_onto_a_free_square(self, plain):
        board = Board([(plain, piece(DWARF))])
        outcome = fall_back(board, plain)

        assert outcome.fell_back
        assert outcome.pushed == 0
        assert board.piece_on(plain) is None
        assert board.piece_on(outcome.destination).key == DWARF
        assert outcome.eliminated is None

    def test_the_square_taken_is_the_first_by_key(self, plain):
        """Every tie in the engine is broken by square keys: two identical games fall back alike."""
        board = Board([(plain, piece(DWARF))])
        assert fall_back(board, plain).destination == ring(plain, 1)[0]

    def test_the_counter_is_picked_up_and_lies_down_again(self, plain):
        board = Board([(plain, piece(DWARF))])
        outcome = fall_back(board, plain)
        assert board.tilt_on(plain) is None
        assert board.tilt_on(outcome.destination) is not None

    def test_an_empty_square_falls_nothing_back(self, plain):
        board = Board()
        outcome = fall_back(board, plain)
        assert not outcome.fell_back
        assert outcome.eliminated is None

    def test_it_avoids_the_squares_the_enemy_controls(self, plain):
        """The enemy two squares away holds the squares between: they are not fallen back into."""
        enemy, *_ = ring(plain, 2)
        board = Board([(plain, piece(DWARF)), (enemy, piece(ORC))])
        destination = fall_back(board, plain).destination
        assert destination.distance(enemy) > 1


# --- Pushing one's friends -----------------------------------------------------------------------


class TestPushingFriends:
    def test_a_surrounded_unit_pushes_a_friend_and_takes_its_place(self, plain):
        """"Unless it is surrounded by friendly units. In that case, it pushes one of those units
        and takes its place." """
        friends = ring(plain, 1)
        board = Board([(plain, piece(DWARF))] + [(square, piece(ELF)) for square in friends])
        outcome = fall_back(board, plain)

        assert outcome.pushed == 1
        pushed_from, pushed_to = outcome.moves[1]
        assert outcome.destination == pushed_from            # it took the friend's square
        assert board.piece_on(outcome.destination).key == DWARF
        assert board.piece_on(pushed_to).key == ELF
        assert board.piece_on(plain) is None

    def test_the_square_left_behind_is_not_handed_to_a_friend(self, plain):
        """A fall-back is not an exchange of places: nobody moves into the abandoned square."""
        friends = ring(plain, 1)
        board = Board([(plain, piece(DWARF))] + [(square, piece(ELF)) for square in friends])
        fall_back(board, plain)
        assert board.piece_on(plain) is None

    def test_the_chain_is_the_shortest_one_and_not_the_first(self, plain):
        """Two rings of friends, one hole: the way out is two moves, through whichever friend
        borders the hole - and not three moves through the friend that comes first by key."""
        friends = ring(plain, 1) + ring(plain, 2)
        hole = ring(plain, 2)[-1]
        board = Board([(plain, piece(DWARF))]
                      + [(square, piece(ELF)) for square in friends if square != hole])

        chain = shortest_chain(board, plain, "alliance", ())
        assert chain is not None
        assert len(chain) == 3                                # origin, one friend, the hole
        assert chain[0] == plain and chain[-1] == hole
        assert chain[1].distance(plain) == 1 and chain[1].distance(hole) == 1

        outcome = fall_back(board, plain)
        assert outcome.pushed == 1
        assert board.piece_on(hole).key == ELF
        assert board.piece_on(chain[1]).key == DWARF

    def test_a_deeper_pocket_pushes_two_friends(self, plain):
        """Nothing free within two squares: the chain runs out to the third ring."""
        friends = ring(plain, 1) + ring(plain, 2)
        board = Board([(plain, piece(DWARF))] + [(square, piece(ELF)) for square in friends])
        outcome = fall_back(board, plain)

        assert outcome.pushed == 2
        assert board.piece_on(plain) is None
        assert [origin.distance(plain) for origin, _ in outcome.moves] == [0, 1, 2]
        assert board.piece_on(outcome.destination).key == DWARF

    def test_a_friend_under_enemy_control_is_not_pushed(self, plain):
        """Its square could not be fallen back into: taking it from a friend does not make it
        lawful (see the caveats in `tenebrae/engine/README.md`)."""
        friends = ring(plain, 1)
        board = Board([(plain, piece(DWARF))] + [(square, piece(ELF)) for square in friends])
        controlled = {friends[0].key}
        chain = shortest_chain(board, plain, "alliance", controlled)
        assert chain is not None
        assert chain[1] != friends[0]

    def test_the_enemy_is_never_pushed(self, plain):
        """Only "friendly units" give way; an enemy blocks as a lake does."""
        neighbours = ring(plain, 1)
        board = Board([(plain, piece(DWARF))]
                      + [(square, piece(ORC)) for square in neighbours])
        outcome = fall_back(board, plain)
        assert outcome.eliminated == plain
        assert all(board.piece_on(square).key == ORC for square in neighbours)


# --- Eliminated for want of a retreat ------------------------------------------------------------


class TestElimination:
    def test_a_unit_with_nowhere_to_go_is_removed_from_play(self, plain):
        """"A unit that finds itself unable to fall back […] is removed from play." """
        board = Board([(plain, piece(DWARF))]
                      + [(square, piece(ORC)) for square in ring(plain, 1)])
        outcome = fall_back(board, plain)

        assert outcome.eliminated == plain
        assert not outcome.fell_back
        assert outcome.piece.key == DWARF
        assert board.piece_on(plain) is None

    def test_a_pocket_of_friends_ringed_by_the_enemy_saves_nobody(self, plain):
        """Surrounded by friends, but the friends have nowhere to go either: the chain fails and
        it is the retreating unit that falls - the friends stay where they are."""
        friends = ring(plain, 1)
        enemies = ring(plain, 2)
        board = Board([(plain, piece(DWARF))]
                      + [(square, piece(ELF)) for square in friends]
                      + [(square, piece(ORC)) for square in enemies])
        outcome = fall_back(board, plain)

        assert outcome.eliminated == plain
        assert board.piece_on(plain) is None
        assert all(board.piece_on(square).key == ELF for square in friends)

    def test_the_whole_first_ring_under_control_leaves_no_way_out(self, plain):
        """Not one piece around it, but every square held under an enemy zone of control."""
        board = Board([(plain, piece(DWARF))])
        controlled = {square.key for square in ring(plain, 1)}
        assert shortest_chain(board, plain, "alliance", controlled) is None


# --- A whole group falling back ------------------------------------------------------------------


class TestAGroupFallingBack:
    def test_each_unit_falls_back_in_square_order(self, plain):
        first, second, *_ = ring(plain, 1)
        board = Board([(first, piece(DWARF)), (second, piece(DWARF))])
        outcomes = fall_back_together(board, [second, first])

        assert len(outcomes) == 2
        assert keys(origin for outcome in outcomes for origin, _ in outcome.moves) \
            == sorted([first.key, second.key])

    def test_no_unit_gives_ground_twice(self, plain):
        """The booklet calls it one simultaneous fall-back: a unit a comrade's chain has already
        pushed has given its ground, and is passed over when its own turn comes.

        Seven units of the same side, all asked to fall back, one of them surrounded by the six
        others: without that rule the one pushed out of the centre would be moved again from the
        square it had just been pushed into."""
        friends = ring(plain, 1)
        board = Board([(plain, piece(DWARF))] + [(square, piece(DWARF)) for square in friends])
        outcomes = fall_back_together(board, [plain] + friends)

        moved = [origin.key for outcome in outcomes for origin, _ in outcome.moves]
        assert len(moved) == len(set(moved)), moved
        assert len(board) == 7            # and the fall-back cost nobody their place
        assert all(outcome.eliminated is None for outcome in outcomes)
