"""The artificial opponent: targeting, the march towards the enemy, the concentration of attacks.

The file is not called `test_ai.py`: `tenebrae/application/engine/` already has one, and pytest
imports test modules by their file name alone.

As everywhere, the hexagons are not hard-coded: the figures are looked up on the game map - a
corner of bare plain, ruins adjacent to a plain - so as to survive a terrain fix. The die is a
callable supplied by the test: the AI is deterministic at equal die.
"""

import pytest

from tenebrae.engine import ai
from tenebrae.engine.board import Board
from tenebrae.engine.combat import DE, DR
from tenebrae.engine.combat_register import CombatRegister
from tenebrae.engine.hexagon import MAP, Hex
from tenebrae.engine.phase import Turn
from tenebrae.engine.piece import piece
from tests.engine.plains import ring_of, surroundings, well_surrounded_plain

DWARF = "nains-01-5-infanteries"           # alliance, strength 12, movement 3
ELF = "elfes-01-5-infanteries"             # alliance, strength 7, movement 4
ORC = "orques-01-15-infanteries"           # darkness, strength 8, movement 4
ORC_ARCHER = "orques-03-5-archers"         # darkness, strength 4, movement 4, fire 8, range 3
ARCHER = "yzent-03-8-archers"              # darkness, strength 2, movement 4, fire 4, range 3


def the_die_must_not_be_used():
    raise AssertionError("no combat was meant to be fought")


def ruins_in_the_plain():
    """Ruins, an adjacent plain, and a second plain adjacent to the first."""
    for key, elements in MAP.items():
        if elements[0] != "ruines":
            continue
        ruins = Hex.from_key(key)
        for origin in ruins.neighbours():
            if MAP[origin.key][0] != "plaine":
                continue
            for plain in origin.neighbours():
                if plain != ruins and MAP[plain.key][0] == "plaine":
                    return ruins, origin, plain
    raise AssertionError("no ruins bordered by two plains on the map")


@pytest.fixture
def corner():
    """A centre of bare plain, two adjacent squares that touch, and a square two squares away."""
    a = well_surrounded_plain()
    c, x1, _, further = ring_of(a)
    return a, c, x1, further


class TestTargetPriority:
    def test_the_nearest_first(self, corner):
        a, c, _, further = corner
        # The orc in contact comes before the weaker but more distant archer.
        board = Board([(c, piece(ORC)), (further, piece(ORC_ARCHER))])
        assert ai.target_priority(board, a, "alliance") == [c, further]

    def test_the_weakest_at_equal_distance(self, corner):
        a, c, x1, _ = corner
        board = Board([(c, piece(ORC)), (x1, piece(ORC_ARCHER))])
        # Both are in contact; the archer (strength 4) comes before the orc (strength 8).
        assert ai.target_priority(board, a, "alliance")[0] == x1

    def test_the_terrain_strengthens_the_target(self):
        ruins, origin, plain = ruins_in_the_plain()
        # The same orc: strength 8 in the plain, but 16 in the ruins, which double the defence.
        board = Board([(ruins, piece(ORC)), (plain, piece(ORC))])
        assert ai.target_priority(board, origin, "alliance")[0] == plain

    def test_the_order_is_broken_by_the_key(self, corner):
        a, c, x1, _ = corner
        # Two identical targets at the same distance: the key order decides, always the same way.
        board = Board([(c, piece(ORC)), (x1, piece(ORC))])
        expected = [hexagon for hexagon in sorted((c, x1), key=lambda h: h.key)]
        assert ai.target_priority(board, a, "alliance") == expected

    def test_without_an_opponent_there_is_no_target(self, corner):
        a, c, *_ = corner
        board = Board([(c, piece(DWARF))])
        assert ai.choose_target(board, a, "alliance") is None


class TestPlayMovement:
    def test_the_infantry_comes_into_contact(self, corner):
        a, _, _, further = corner
        board = Board([(a, piece(ORC)), (further, piece(DWARF))])
        played = ai.play_movement(board, "alliance")
        assert len(played) == 1
        origin, destination = played[0]
        assert origin == further
        assert destination.distance(a) == 1
        assert board.piece_on(destination).key == DWARF

    def test_a_unit_in_range_holds_its_position(self, corner):
        a, c, *_ = corner
        board = Board([(a, piece(ORC)), (c, piece(DWARF))])
        assert ai.play_movement(board, "alliance") == []
        assert board.piece_on(c).key == DWARF

    def test_the_shooter_stops_at_range(self):
        # A corner of plain wide enough to place the archer four squares from its target.
        a = well_surrounded_plain(radius=4)
        far = next(hexagon for hexagon in surroundings(a, 4) if hexagon.distance(a) == 4)
        board = Board([(a, piece(DWARF)), (far, piece(ORC_ARCHER))])
        played = ai.play_movement(board, "tenebres")
        # Range 3: the archer closes to firing range, and not one step further.
        assert len(played) == 1
        assert played[0][1].distance(a) == 3

    def test_without_an_opponent_nobody_moves(self, corner):
        a, *_ = corner
        board = Board([(a, piece(DWARF))])
        assert ai.play_movement(board, "alliance") == []


class TestPlayCombat:
    def test_the_attacks_concentrate(self, corner):
        a, c, x1, _ = corner
        board = Board([(a, piece(ORC)), (c, piece(DWARF)), (x1, piece(ELF))])
        register = CombatRegister()
        # Dwarf and elf (12 + 7) against the orc (8): 2-1; die 1 -> DR, the orc falls back.
        combats = ai.play_combat(board, "alliance", register, roll=lambda: 1)
        assert len(combats) == 1
        target, attackers, result = combats[0]
        assert target == a
        assert sorted(hexagon.key for hexagon in attackers) == sorted([c.key, x1.key])
        assert result.outcome == DR
        # The register counts units by their square, and the target has just changed square: it is
        # marked where it now stands, or it could be attacked again this very phase.
        assert register.to_dict() == {"engaged_attackers": sorted([c.key, x1.key]),
                                      "engaged_targets": [result.square_after(a).key]}
        assert result.square_after(a) != a

    def test_a_unit_attacks_only_once(self, corner):
        a, c, x1, _ = corner
        # Two orcs in contact with the dwarf: it engages only one, the other stays unharmed.
        board = Board([(a, piece(ORC)), (x1, piece(ORC)), (c, piece(DWARF))])
        register = CombatRegister()
        combats = ai.play_combat(board, "alliance", register, roll=lambda: 1)
        assert len(combats) == 1
        assert not register.can_attack(c.key)
        assert len(register.engaged_targets) == 1

    def test_no_attack_below_parity(self, corner):
        a, _, _, further = corner
        # The orc archer (strength 4, range 3) sees the dwarf (strength 12): 1-3, it declines.
        board = Board([(a, piece(DWARF)), (further, piece(ORC_ARCHER))])
        register = CombatRegister()
        combats = ai.play_combat(board, "tenebres", register, roll=the_die_must_not_be_used)
        assert combats == []
        assert register.can_attack(further.key)

    def test_the_eliminated_leave_the_board(self, corner):
        a, c, *_ = corner
        board = Board([(a, piece(ARCHER)), (c, piece(DWARF))])
        register = CombatRegister()
        # Dwarf 12 against archer 2: 6-1; die 1 -> DE, the target is removed.
        combats = ai.play_combat(board, "alliance", register, roll=lambda: 1)
        assert combats[0][2].outcome == DE
        assert board.piece_on(a) is None
        assert board.piece_on(c).key == DWARF


class TestPlayTurn:
    def test_the_full_turn_hands_play_back(self, corner):
        a, _, _, further = corner
        board = Board([(a, piece(ELF)), (further, piece(ORC))])
        turn = Turn(("alliance", "tenebres"))
        turn.advance().advance()          # alliance played: darkness, movement phase
        register = CombatRegister()
        moves, combats = ai.play_turn(board, turn, register, roll=lambda: 1)
        # The orc marched into contact then engaged the elf (8 against 7: 1-1; die 1 -> DR).
        assert len(moves) == 1
        assert len(combats) == 1
        assert combats[0][2].outcome == DR
        # Play is handed back: alliance movement phase, next turn, empty register.
        assert turn.active_side == "alliance"
        assert turn.phase_type == "mouvement"
        assert turn.number == 2
        assert register.to_dict() == {"engaged_attackers": [], "engaged_targets": []}

    def test_the_ai_refuses_to_enter_outside_movement(self, corner):
        a, c, *_ = corner
        board = Board([(a, piece(ELF)), (c, piece(ORC))])
        turn = Turn(("alliance", "tenebres"))
        turn.advance()                    # alliance, combat phase
        with pytest.raises(ValueError):
            ai.play_turn(board, turn, CombatRegister(), roll=lambda: 1)
