"""Combat resolution: the strength ratio, the terrain modifiers, Table I.

As for movement, the terrain hexagons are not hard-coded: they are looked up on the game map so as
to survive a fix.
"""

import pytest

from tenebrae.engine import combat
from tenebrae.engine.board import Board
from tenebrae.engine.combat import AE, AR, DE, DR, EX
from tenebrae.engine.hexagon import MAP, Hex
from tenebrae.engine.piece import piece
from tests.engine.plains import ring_of, well_surrounded_plain

DWARF = "nains-01-5-infanteries"           # alliance, strength 12
ORC = "orques-01-15-infanteries"           # darkness, strength 8
ARCHER = "yzent-03-8-archers"              # darkness, strength 2, fire 4, range 3
ELF = "elfes-01-5-infanteries"             # alliance, strength 7
CROSSBOWMAN = "nains-02-4-arbaletriers"    # alliance, strength 6, fire 4, range 2
HEAVY_CROSSBOWMAN = "nains-03-4-arbaletriers-lourds"   # alliance, strength 8, fire 5


def hexagon_of_terrain(terrain):
    """A hexagon whose main terrain is `terrain`."""
    return next(Hex.from_key(key) for key, elements in MAP.items() if elements[0] == terrain)


@pytest.fixture
def corner():
    """A centre of bare plain, an adjacent square, and a square two squares away."""
    a = well_surrounded_plain()
    c, _, _, further = ring_of(a)
    return a, c, further


class TestStrengthRatio:
    def test_the_column_the_strengths_fall_into(self):
        """The booklet's own example first - "10/4 counts as 2 against 1", rounded in the
        defender's favour - then the even case, the defender's side of the table, and the two ends
        beyond which the table does not go."""
        for attack, defence, column in ((10, 4, (2, 1)),
                                        (8, 8, (1, 1)),
                                        (4, 10, (1, 3)),
                                        (100, 1, (6, 1)),
                                        (1, 100, (1, 5))):
            assert combat.COLUMNS[combat.ratio_column(attack, defence)] == column, (attack, defence)


class TestTerrainModifiers:
    def test_what_the_ground_multiplies_the_defence_by(self):
        """The plain changes nothing, walls do; and the woods are the booklet's one exception -
        they shelter the elves, and nobody else."""
        assert combat.defence_multiplier(well_surrounded_plain(), piece(ORC)) == 1
        assert combat.defence_multiplier(hexagon_of_terrain("fort"), piece(ORC)) == 3
        assert combat.defence_multiplier(hexagon_of_terrain("ruines"), piece(ORC)) == 2

        woods = hexagon_of_terrain("bois")
        assert combat.defence_multiplier(woods, piece(ELF)) == 2
        assert combat.defence_multiplier(woods, piece(ORC)) == 1

    def test_what_the_ground_adds_to_the_die(self):
        """Height and cover, two points each; open ground, nothing."""
        assert combat.terrain_die_bonus(well_surrounded_plain()) == 0
        assert combat.terrain_die_bonus(hexagon_of_terrain("colline")) == 2
        assert combat.terrain_die_bonus(hexagon_of_terrain("bois")) == 2


class TestRange:
    def test_the_infantry_engages_only_in_contact(self, corner):
        a, c, further = corner
        assert combat.in_range(c, piece(DWARF), a)
        assert not combat.in_range(further, piece(DWARF), a)

    def test_the_archer_engages_up_to_its_range(self, corner):
        a, _, further = corner
        assert combat.in_range(further, piece(ARCHER), a)          # two squares
        very_far = next(Hex.from_key(key) for key in MAP
                        if Hex.from_key(key).distance(a) == 4)
        assert not combat.in_range(very_far, piece(ARCHER), a)


class TestFiresMissiles:
    """Who fires, in the engine's sense: a counter carrying a fire strength **and** a range."""

    def test_who_fires_and_who_does_not(self):
        """The archer carries both values, the infantry neither - and an empty square carries no
        piece at all, which `fight` hands over as it comes: no exception here."""
        assert combat.fires_missiles(piece(ARCHER))
        assert not combat.fires_missiles(piece(DWARF))
        assert not combat.fires_missiles(None)

    def test_the_combat_range_follows_the_same_split(self):
        assert combat.combat_range(piece(ARCHER)) == piece(ARCHER).range
        assert combat.combat_range(piece(DWARF)) == 1


class TestFight:
    @pytest.fixture
    def pair(self):
        """A target on the plain and an adjacent square."""
        a = well_surrounded_plain()
        c, *_ = ring_of(a)
        return a, c

    def test_defender_eliminated_clears_its_square(self, pair):
        target, attacker = pair
        board = Board([(target, piece(ARCHER)), (attacker, piece(DWARF))])
        # DWARF 12 against ARCHER 2 -> 6-1; die 1 -> DE.
        result = combat.fight(board, target, [attacker], roll=1)
        assert result.outcome == DE
        assert board.piece_on(target) is None
        assert board.piece_on(attacker) is not None
        assert result.eliminated == [target]
        assert result.ratio == (6, 1)

    def test_attacker_eliminated_clears_its_square(self, pair):
        target, attacker = pair
        board = Board([(target, piece(DWARF)), (attacker, piece(ARCHER))])
        # ARCHER 2 against DWARF 12 -> 1-5; die 2 -> AE.
        result = combat.fight(board, target, [attacker], roll=2)
        assert result.outcome == AE
        assert board.piece_on(attacker) is None
        assert board.piece_on(target) is not None

    def test_an_exchange_clears_both_squares(self, pair):
        target, attacker = pair
        board = Board([(target, piece(ARCHER)), (attacker, piece(DWARF))])
        # DWARF 12 against ARCHER 2 -> 6-1; die 6 -> EX.
        result = combat.fight(board, target, [attacker], roll=6)
        assert result.outcome == EX
        assert board.piece_on(target) is None
        assert board.piece_on(attacker) is None

    def test_the_exchange_spares_the_missile_troops(self, pair):
        """"A unit firing missiles can in no case suffer [...] an exchange result."

        The foot soldier falls with the target, the crossbowman stays: it struck from afar.
        """
        target, foot_soldier = pair
        _, _, shooter, *_ = ring_of(target)
        board = Board([(target, piece(ARCHER)),
                       (foot_soldier, piece(DWARF)), (shooter, piece(CROSSBOWMAN))])
        # DWARF 12 + CROSSBOWMAN 6 = 18 against ARCHER 2 -> 6-1; die 6 -> EX.
        result = combat.fight(board, target, [foot_soldier, shooter], roll=6)
        assert result.outcome == EX
        assert board.piece_on(target) is None
        assert board.piece_on(foot_soldier) is None
        assert board.piece_on(shooter) is not None
        assert result.eliminated == [foot_soldier, target]

    def test_a_lone_shooter_comes_out_of_an_exchange_unharmed(self, pair):
        """The exchange then clears the target's square alone: the attacker leaves nothing there."""
        target, shooter = pair
        board = Board([(target, piece(ARCHER)), (shooter, piece(HEAVY_CROSSBOWMAN))])
        # HEAVY_CROSSBOWMAN 8 against ARCHER 2 -> 4-1; die 6 -> EX.
        result = combat.fight(board, target, [shooter], roll=6)
        assert result.outcome == EX
        assert result.eliminated == [target]
        assert board.piece_on(shooter) is not None

    def test_the_shooter_still_counts_in_the_ratio(self, pair):
        """Spared by the exchange, but not absent from the combat: its strength weighs on the
        column."""
        target, foot_soldier = pair
        _, _, shooter, *_ = ring_of(target)
        board = Board([(target, piece(ARCHER)),
                       (foot_soldier, piece(DWARF)), (shooter, piece(CROSSBOWMAN))])
        breakdown = combat.fight(board, target, [foot_soldier, shooter], roll=6).breakdown
        assert breakdown.strengths == [12, 6]
        assert breakdown.attacking_strength == 18

    def test_attacker_eliminated_does_not_spare_the_shooter(self, pair):
        """The booklet exempts missile troops from retreat and exchange only, not from `AE`."""
        target, shooter = pair
        board = Board([(target, piece(DWARF)), (shooter, piece(CROSSBOWMAN))])
        # CROSSBOWMAN 6 against DWARF 12 -> 1-2; die 3 -> AR, which the engine leaves without
        # effect: the shooter stays where it is, as does the target.
        result = combat.fight(board, target, [shooter], roll=3)
        assert result.outcome == AR
        assert result.eliminated == []
        assert board.piece_on(shooter) is not None

        board = Board([(target, piece(DWARF)), (shooter, piece(ARCHER))])
        # ARCHER 2 against DWARF 12 -> 1-5; die 2 -> AE: the shooter is indeed removed.
        result = combat.fight(board, target, [shooter], roll=2)
        assert result.outcome == AE
        assert board.piece_on(shooter) is None

    def test_a_retreat_changes_nothing(self, pair):
        target, attacker = pair
        board = Board([(target, piece(ORC)), (attacker, piece(DWARF))])
        before = dict(board.pieces)
        result = combat.fight(board, target, [attacker], roll=1)  # 1-1, die 1 -> DR
        assert result.outcome in (AR, DR)
        assert board.pieces == before

    def test_the_defenders_terrain_counts(self, pair):
        _, attacker = pair
        ruins = hexagon_of_terrain("ruines")
        Board([(ruins, piece(ORC)), (attacker, piece(DWARF))])
        # DWARF 12 against ORC 8 -> 1-1 on the plain, but 12 against 16 -> 1-2 in the ruins.
        without_ruins = combat.ratio_column(12, 8)
        with_ruins = combat.ratio_column(12, 8 * 2)
        assert with_ruins < without_ruins

    def test_an_absent_target_resolves_nothing(self, pair):
        target, attacker = pair
        board = Board([(attacker, piece(DWARF))])
        result = combat.fight(board, target, [attacker], roll=6)
        assert result.outcome is None
        assert result.eliminated == []


class TestRatioBreakdown:
    """The computation kept piece by piece: enough to tell its story, not to redo it.

    The ratio cannot be read off the board - the defender's terrain plays twice between the
    counters and the Table I column - and the breakdown is what makes it showable.
    """

    @pytest.fixture
    def pair(self):
        a = well_surrounded_plain()
        c, *_ = ring_of(a)
        return a, c

    def test_the_breakdown_keeps_the_strengths_one_by_one(self, pair):
        """The group of attackers does not reduce to its total: each counter has its strength."""
        target, attacker = pair
        _, second, *_ = ring_of(target)  # a second square adjacent to the target
        board = Board([(target, piece(ARCHER)), (attacker, piece(DWARF)), (second, piece(ELF))])
        breakdown = combat.fight(board, target, [attacker, second], roll=1).breakdown
        assert breakdown.strengths == [12, 7]
        assert breakdown.attacking_strength == 19

    def test_the_breakdown_keeps_the_terrain_and_its_multiplier(self):
        ruins = hexagon_of_terrain("ruines")
        _, attacker, *_ = ring_of(ruins)
        board = Board([(ruins, piece(ORC)), (attacker, piece(DWARF))])
        breakdown = combat.fight(board, ruins, [attacker], roll=1).breakdown
        assert breakdown.terrain == "ruines"
        assert (breakdown.target_strength, breakdown.multiplier,
                breakdown.defending_strength) == (8, 2, 16)

    def test_the_breakdown_keeps_the_roll_and_the_terrain_bonus(self):
        """The result's die is already modified: without the breakdown, the raw roll would be lost."""
        hill = hexagon_of_terrain("colline")
        _, attacker, *_ = ring_of(hill)
        board = Board([(hill, piece(ORC)), (attacker, piece(DWARF))])
        breakdown = combat.fight(board, hill, [attacker], roll=3).breakdown
        assert (breakdown.roll, breakdown.die_bonus, breakdown.die) == (3, 2, 5)

    def test_the_die_stays_within_the_table(self):
        """Table I has only six rows: a roll of 6 on a hill is brought back into it."""
        hill = hexagon_of_terrain("colline")
        _, attacker, *_ = ring_of(hill)
        board = Board([(hill, piece(ORC)), (attacker, piece(DWARF))])
        breakdown = combat.fight(board, hill, [attacker], roll=6).breakdown
        assert (breakdown.roll + breakdown.die_bonus, breakdown.die) == (8, 6)

    def test_the_breakdown_repeats_the_results_ratio_and_outcome(self, pair):
        """Two ways of reading the same combat: they cannot diverge."""
        target, attacker = pair
        board = Board([(target, piece(ARCHER)), (attacker, piece(DWARF))])
        result = combat.fight(board, target, [attacker], roll=1)
        assert result.breakdown.ratio == result.ratio == (6, 1)
        assert result.breakdown.die == result.die == 1
        assert result.breakdown.outcome == result.outcome == DE

    def test_an_unresolved_combat_has_nothing_to_break_down(self, pair):
        target, attacker = pair
        board = Board([(attacker, piece(DWARF))])
        assert combat.fight(board, target, [attacker], roll=6).breakdown is None

    def test_resolve_reads_the_same_computation(self, pair):
        """`resolve` and `fight` both go through `break_down`: a single reading of the terrain."""
        target, attacker = pair
        board = Board([(target, piece(ARCHER)), (attacker, piece(DWARF))])
        outcome = combat.resolve([12], piece(ARCHER), target, roll=1)
        assert outcome == combat.fight(board, target, [attacker], roll=1).outcome


class TestCombatRegister:
    """A unit fights only one combat per phase, and is taken as a target only once.

    The register designates units by their square: one counter stands for several units, the square
    designates only one, and nothing moves during a combat phase.
    """

    @pytest.fixture
    def register(self):
        return combat.CombatRegister()

    @pytest.fixture
    def squares(self, corner):
        """Three distinct squares: the centre, an adjacent square, a square two squares away."""
        centre, contact, further = corner
        return centre.key, contact.key, further.key

    def test_everything_is_available_at_the_start(self, squares, register):
        centre, contact, _ = squares
        assert register.can_attack(contact)
        assert register.can_be_targeted(centre)

    def test_an_engaged_attacker_can_no_longer_attack(self, squares, register):
        centre, contact, _ = squares
        register.record([contact], centre)
        assert not register.can_attack(contact)
        # It remains attackable, though: that is the business of the other side's combat phase.
        assert register.can_be_targeted(contact)

    def test_an_engaged_target_can_no_longer_be_attacked(self, squares, register):
        centre, contact, _ = squares
        register.record([contact], centre)
        assert not register.can_be_targeted(centre)
        assert register.can_attack(centre)

    def test_the_whole_group_of_attackers_is_marked(self, squares, register):
        centre, contact, further = squares
        register.record([contact, further], centre)
        assert not register.can_attack(contact)
        assert not register.can_attack(further)

    def test_a_unit_outside_the_combat_stays_free(self, squares, register):
        centre, contact, further = squares
        register.record([contact], centre)
        assert register.can_attack(further)
        assert register.can_be_targeted(further)

    def test_the_new_phase_frees_everyone(self, squares, register):
        centre, contact, _ = squares
        register.record([contact], centre)
        register.reset()
        assert register.can_attack(contact)
        assert register.can_be_targeted(centre)

    def test_to_dict_delivers_the_two_sorted_lists(self, squares, register):
        centre, contact, further = squares
        register.record([further, contact], centre)
        assert register.to_dict() == {"engaged_attackers": sorted([contact, further]),
                                      "engaged_targets": [centre]}

    def test_restore_replaces_the_register_in_place(self, squares, register):
        centre, contact, further = squares
        register.record([further], further)
        saved = {"engaged_attackers": [contact], "engaged_targets": [centre]}
        assert register.restore(**saved) is register
        assert register.to_dict() == saved
        # What the saved game does not cite has become free again.
        assert register.can_attack(further) and register.can_be_targeted(further)
        assert not register.can_attack(contact)
        assert not register.can_be_targeted(centre)
