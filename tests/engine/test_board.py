"""The board: the placed pieces, their sides, and the moves it derives from them."""

import pytest

from tenebrae.engine.board import MAXIMUM_TILT, Board
from tenebrae.engine.hexagon import DEFAULT_MOVEMENT, MAP, Hex, zone_of_control
from tenebrae.engine.piece import ALLIANCE, DARKNESS, NEUTRAL, piece
from tests.engine.plains import ring_of, well_surrounded_plain

ELF = "elfes-01-5-infanteries"             # alliance, 4 movement points
DWARF = "nains-01-5-infanteries"           # alliance, 3 points
ORC = "orques-01-15-infanteries"           # darkness, 4 points
BAT = "conjurations-01-6-chauves-souris"   # neutral, 2 points
MARKER = "marqueurs-03-paralysie"          # neutral, motionless

OFF_MAP = Hex(99, 0, -99)


@pytest.fixture
def ground():
    """A corner of bare plain: the centre A, two squares of its ring, one square further out."""
    a = well_surrounded_plain()
    c, x1, _, further = ring_of(a)
    return a, c, x1, further


class TestPositions:
    def test_a_fresh_board_is_empty(self):
        board = Board()
        assert len(board) == 0
        assert board.pieces == {}

    def test_placing_and_finding_a_piece(self, ground):
        """Placed one by one or handed to the constructor, it comes to the same board; and a square
        nobody stands on answers nothing."""
        _, c, x1, _ = ground
        board = Board()
        board.place(c, piece(ELF))
        assert board.piece_on(c).key == ELF
        assert board.piece_on(x1) is None
        assert len(board) == 1

        assert len(Board([(c, piece(ELF)), (x1, piece(ORC))])) == 2

    def test_removing_returns_the_piece(self, ground):
        _, c, *_ = ground
        board = Board([(c, piece(ELF))])
        assert board.remove(c).key == ELF
        assert board.piece_on(c) is None
        assert board.remove(c) is None

    def test_clearing_removes_everything(self, ground):
        _, c, x1, _ = ground
        board = Board([(c, piece(ELF)), (x1, piece(ORC))])
        board.clear()
        assert len(board) == 0

    def test_one_does_not_place_off_the_map(self):
        with pytest.raises(ValueError):
            Board().place(OFF_MAP, piece(ELF))

    def test_the_returned_positions_are_not_the_boards(self, ground):
        """`pieces` is a copy: modifying it moves nobody."""
        _, c, *_ = ground
        board = Board([(c, piece(ELF))])
        board.pieces.clear()
        assert len(board) == 1


class TestSides:
    def test_the_sides_oppose_each_other(self, ground):
        _, c, x1, _ = ground
        board = Board([(c, piece(ELF)), (x1, piece(ORC))])
        assert board.opponents_of(ALLIANCE) == {x1.key}
        assert board.opponents_of(DARKNESS) == {c.key}

    def test_a_side_does_not_oppose_itself(self, ground):
        _, c, x1, _ = ground
        board = Board([(c, piece(ELF)), (x1, piece(DWARF))])
        assert board.opponents_of(ALLIANCE) == frozenset()
        assert board.squares_held_by(ALLIANCE) == {c.key, x1.key}

    def test_the_neutral_side_takes_no_part(self, ground):
        """It opposes nobody, and nobody opposes it: the relation is empty both ways."""
        _, c, x1, _ = ground
        neutral = Board([(c, piece(BAT)), (x1, piece(ORC))])
        assert neutral.opponents_of(NEUTRAL) == frozenset()
        assert neutral.zones_of_control_against(NEUTRAL) == frozenset()

        against = Board([(c, piece(ELF)), (x1, piece(BAT))])
        assert against.opponents_of(ALLIANCE) == frozenset()


class TestZonesOfControl:
    def test_the_opposing_zone_covers_the_enemys_six_squares(self, ground):
        a, c, *_ = ground
        board = Board([(c, piece(ELF)), (a, piece(ORC))])
        assert board.zones_of_control_against(ALLIANCE) == zone_of_control([a])

    def test_what_stands_next_to_a_friend_exerts_no_zone(self, ground):
        """Two reasons, one result: a marker exerts none at all, and a piece of the same side
        exerts none against its own."""
        a, c, *_ = ground
        for neighbour in (MARKER, DWARF):
            board = Board([(c, piece(ELF)), (a, piece(neighbour))])
            assert board.zones_of_control_against(ALLIANCE) == frozenset(), neighbour


class TestMoves:
    def test_the_placed_piece_gives_its_movement(self, ground):
        _, c, *_ = ground
        board = Board([(c, piece(DWARF))])
        assert board.movement_of(c) == 3
        assert board.moves(c) == c.moves(3)

    def test_an_empty_square_answers_with_the_flat_rate_or_the_piece_offered(self, ground):
        """Nobody there: the flat rate, unless the caller says which piece it has in hand."""
        _, c, *_ = ground
        board = Board()
        assert board.movement_of(c) == DEFAULT_MOVEMENT
        assert board.moves(c) == c.moves()

        assert board.movement_of(c, piece(DWARF)) == 3
        assert board.moves(c, piece(DWARF)) == c.moves(3)

    def test_the_placed_piece_prevails_over_the_proposed_one(self, ground):
        _, c, *_ = ground
        board = Board([(c, piece(DWARF))])
        assert board.moves(c, piece(ELF)) == c.moves(3)

    def test_a_nearby_enemy_reduces_the_reach(self, ground):
        a, c, *_ = ground
        board = Board([(c, piece(ELF))])
        alone = board.moves(c)
        board.place(a, piece(ORC))
        assert len(board.moves(c)) < len(alone)

    def test_a_friend_does_not_hinder_the_walk(self, ground):
        """A friendly square does not bar the way: beyond it, everything stays reachable."""
        a, c, *_ = ground
        board = Board([(c, piece(ELF))])
        beyond = [h for h in board.moves(c) if h.distance(a) == 1 and h != c]
        board.place(a, piece(DWARF))
        reached = board.moves(c)
        assert all(hexagon in reached for hexagon in beyond)

    def test_one_does_not_stop_on_an_occupied_square(self, ground):
        """Stacking: one crosses a friend, one does not take their place - and an enemy's square
        is no more a destination than a friend's."""
        a, c, *_ = ground
        for occupant in (DWARF, ORC):
            board = Board([(c, piece(ELF)), (a, piece(occupant))])
            assert a not in board.moves(c), occupant

    def test_the_neutral_side_goes_where_it_likes(self, ground):
        """With no opponent, neither zone nor held square stops it - occupied squares apart."""
        a, c, *_ = ground
        board = Board([(c, piece(BAT)), (a, piece(ORC))])
        assert board.moves(c) == [h for h in c.moves(2) if h != a]


class TestMoving:
    def test_an_allowed_move_changes_the_square(self, ground):
        _, c, _, further = ground
        board = Board([(c, piece(ELF))])
        assert board.move(c, further) is True
        assert board.piece_on(c) is None
        assert board.piece_on(further).key == ELF

    def test_a_move_out_of_reach_moves_nothing(self, ground):
        _, c, *_ = ground
        distant = next(Hex.from_key(key) for key in MAP
                       if Hex.from_key(key).distance(c) == 20)
        board = Board([(c, piece(ELF))])
        assert board.move(c, distant) is False
        assert board.piece_on(c).key == ELF

    def test_one_does_not_move_onto_a_held_square(self, ground):
        a, c, *_ = ground
        board = Board([(c, piece(ELF)), (a, piece(ORC))])
        assert board.move(c, a) is False
        assert board.piece_on(a).key == ORC

    def test_the_zones_follow_the_moved_piece(self, ground):
        """Once the enemy has gone, the reach becomes full again."""
        a, c, _, further = ground
        board = Board([(c, piece(ELF)), (a, piece(ORC))])
        hindered = len(board.moves(c))
        board.remove(a)
        assert len(board.moves(c)) > hindered

    def test_an_empty_square_answers_without_moving_anything(self, ground):
        _, c, _, further = ground
        board = Board()
        assert board.move(c, further) is True
        assert len(board) == 0


class TestSerialisation:
    """`to_dict` and `restore`: the game fits in a "square -> piece key" dict."""

    def test_to_dict_gives_the_scenario_format(self, ground):
        a, c, *_ = ground
        board = Board([(c, piece(ELF)), (a, piece(ORC))])
        assert board.to_dict() == {c.key: ELF, a.key: ORC}

    def test_the_round_trip_places_the_same_pieces(self, ground):
        a, c, *_ = ground
        board = Board([(c, piece(ELF)), (a, piece(ORC))])
        copy = Board().restore(board.to_dict())
        assert copy.to_dict() == board.to_dict()
        assert copy.piece_on(c).key == ELF

    def test_restore_works_in_place_and_overwrites_what_is_there(self, ground):
        a, c, _, further = ground
        board = Board([(further, piece(DWARF))])
        returned = board.restore({c.key: ELF, a.key: ORC})
        assert returned is board
        assert board.piece_on(further) is None
        assert len(board) == 2

    def test_an_unknown_piece_is_refused_without_touching_the_board(self, ground):
        _, c, _, further = ground
        board = Board([(further, piece(DWARF))])
        with pytest.raises(KeyError):
            board.restore({c.key: "counter-that-does-not-exist"})
        assert board.piece_on(further).key == DWARF

    def test_a_square_off_the_map_is_refused_without_touching_the_board(self, ground):
        _, _, _, further = ground
        board = Board([(further, piece(DWARF))])
        with pytest.raises(ValueError):
            board.restore({OFF_MAP.key: ELF})
        assert board.piece_on(further).key == DWARF


class TestTilts:
    """The angle of the placed counter: drawn on placing, kept, and restored on restore.

    It is not a rule from the booklet, but it is part of the game state - see the header of
    `tenebrae/engine/board.py`: a piece lying down differently at each reread of the board would
    betray an angle recomputed rather than kept.
    """

    def test_placing_lays_the_counter_askew_unless_told_at_what_angle(self, ground):
        """The board draws one, within the bounds; a caller resuming a game gives its own. A square
        with no counter on it has no angle either."""
        _, c, x1, _ = ground
        board = Board([(c, piece(ELF))])
        assert abs(board.tilt_on(c)) <= MAXIMUM_TILT
        assert board.tilt_on(x1) is None

        given = Board()
        given.place(c, piece(ELF), 3.14)
        assert given.tilt_on(c) == 3.14

    def test_the_counters_are_not_all_laid_the_same(self):
        """A frozen tilt would show: fifty placings would give only one angle."""
        squares = [Hex.from_key(key) for key in list(MAP)[:50]]
        board = Board([(square, piece(ELF)) for square in squares])
        assert len(set(board.tilts.values())) > len(squares) / 2

    def test_taking_a_counter_off_forgets_its_tilt(self, ground):
        """One by one or all at once: no angle outlives the counter it belonged to."""
        _, c, x1, _ = ground
        board = Board([(c, piece(ELF))])
        board.remove(c)
        assert board.tilt_on(c) is None
        assert board.tilts == {}

        whole = Board([(c, piece(ELF)), (x1, piece(ORC))])
        whole.clear()
        assert whole.tilts == {}

    def test_the_returned_tilts_are_not_the_boards(self, ground):
        _, c, *_ = ground
        board = Board([(c, piece(ELF))])
        board.tilts.clear()
        assert board.tilt_on(c) is not None

    def test_moving_lays_the_counter_down_again(self, ground):
        """The only moment when the angle changes: the piece is picked up."""
        _, c, *_ = ground
        board = Board()
        board.place(c, piece(ELF), 4.2)
        destination = board.moves(c)[0]
        assert board.move(c, destination) is True
        assert board.tilt_on(c) is None
        assert board.tilt_on(destination) != 4.2
        assert abs(board.tilt_on(destination)) <= MAXIMUM_TILT

    def test_a_refused_move_lays_nothing_down_again(self, ground):
        """Out of reach the piece does not move - so it does not lie down again either."""
        _, c, *_ = ground
        board = Board()
        board.place(c, piece(ELF), 4.2)
        assert board.move(c, OFF_MAP) is False
        assert board.tilt_on(c) == 4.2

    def test_restore_lays_the_counters_back_as_they_were(self, ground):
        a, c, *_ = ground
        board = Board([(c, piece(ELF)), (a, piece(ORC))])
        copy = Board().restore(board.to_dict(), board.tilts)
        assert copy.tilts == board.tilts

    def test_a_square_restored_without_an_angle_is_given_one(self, ground):
        """Whether the save carried no angle at all - one written before we started keeping them -
        or carried some and not others, every counter comes back lying at an angle."""
        a, c, *_ = ground
        without = Board().restore({c.key: ELF, a.key: ORC})
        assert set(without.tilts) == {c.key, a.key}
        assert all(abs(angle) <= MAXIMUM_TILT for angle in without.tilts.values())

        partial = Board().restore({c.key: ELF, a.key: ORC}, {c.key: 1.5})
        assert partial.tilt_on(c) == 1.5
        assert partial.tilt_on(a) is not None
