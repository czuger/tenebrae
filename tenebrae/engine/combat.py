"""Combat resolution in Ave Tenebrae: Table I of the booklet, and nothing more.

The booklet (`tenebrae/game_box/ave_tenebrae_regles_en.md`, "Combats") gives a two-way table - the
strength ratio in columns, the die roll in rows - each cell of which gives the outcome of the
battle: attacker eliminated, defender eliminated, exchange, or one of the two retreats. This module
transcribes that table, computes the strength ratio ("always rounded in the defender's favour") and
applies the terrain modifiers from the *Terrain table*.

Retreats are not played: `AR` and `DR` leave the board untouched. `EX` removes the engaged units,
without the booklet's "attackers totalling a strength at least equal" sorting - but **missile
troops escape it**: "a unit firing missiles can in no case suffer a retreat or exchange result".
Special abilities, the cavalry charge, phalanxes and the day/night alternation are out of reach -
see `tenebrae/engine/README.md`.

`CombatRegister` keeps separately what a combat phase has already consumed: a unit attacks only
once, a unit is attacked only once. It is a register, not a resolution - it touches neither the
board nor the turn, and is emptied at each new combat phase.
"""

# The five possible outcomes. Only `AE`, `DE` and `EX` change anything on the board; `AR` and
# `DR` - the retreats - are read but left without effect, for want of a retreat rule.
AE, DE, EX, AR, DR = "AE", "DE", "EX", "AR", "DR"

# The ten strength ratios of Table I, from 1 against 5 to 6 against 1, attacker in the numerator.
COLUMNS = ((1, 5), (1, 4), (1, 3), (1, 2), (1, 1), (2, 1), (3, 1), (4, 1), (5, 1), (6, 1))

# Table I, transcribed as it stands: die roll (1 to 6) -> outcome for each of the ten columns.
TABLE_I = {
    1: (AR, AR, DR, DR, DR, DR, DR, DE, DE, DE),
    2: (AE, AR, AR, DR, DR, DR, DR, DR, DE, DE),
    3: (AE, AE, AR, AR, DR, DR, DR, DR, DE, DE),
    4: (AE, AE, AR, AR, AR, DR, DR, DR, DR, DE),
    5: (AE, AE, AE, AR, AR, AR, DR, DR, DR, EX),
    6: (AE, AE, AE, AR, AR, AR, AR, EX, EX, EX),
}

# "Combat" column of the *Terrain table*: the defender's terrain multiplies its strength.
DEFENCE_MULTIPLIERS = {"montagne": 3, "fort": 3, "chateau": 3,
                       "riviere": 2, "lac": 2, "ruines": 2, "village": 2}

# The booklet reserves the woods' "x 2 in defence" to Elves alone.
ELVES_FACTION = "09-elfes"

# Woods and hills add 2 to the attacker's die, whoever the defender is.
DIE_BONUS_TERRAINS = {"bois", "colline"}


def ratio_column(attacking_strength, defending_strength):
    """The index, in `COLUMNS`, of the attacker / defender strength ratio.

    The ratio runs from 1-5 to 6-1 and is "always rounded in the defender's favour": 10 against 4
    is 2 against 1, 4 against 10 is 1 against 3.
    """
    if attacking_strength <= 0:
        return 0
    if defending_strength <= 0:
        return len(COLUMNS) - 1
    if attacking_strength >= defending_strength:
        return COLUMNS.index((min(attacking_strength // defending_strength, 6), 1))
    return COLUMNS.index((1, min(-(-defending_strength // attacking_strength), 5)))


def defence_multiplier(hexagon, defending_piece):
    """The factor multiplying the defender's strength according to the terrain it occupies."""
    terrain = hexagon.terrain
    if terrain == "bois":
        return 2 if defending_piece.faction == ELVES_FACTION else 1
    return DEFENCE_MULTIPLIERS.get(terrain, 1)


def terrain_die_bonus(hexagon):
    """What the defender's terrain adds to the attacker's die: 2 in woods or hills, 0 otherwise."""
    return 2 if hexagon.terrain in DIE_BONUS_TERRAINS else 0


def fires_missiles(piece):
    """Says whether this piece engages by fire: it carries both a fire strength **and** a range.

    That is the only way of engaging we know of for it - the engine does not offer it a choice
    between fire and melee, and its range covers the adjacent square. A piece that fires is
    therefore held to fire in every combat it fights, whatever the distance.
    """
    if piece is None:
        return False
    return bool(piece.fire and piece.range)


def combat_range(piece):
    """The distance at which this piece can engage: its firing range if it fires, 1 otherwise."""
    if fires_missiles(piece):
        return piece.range
    return 1


def in_range(attacker_hex, attacking_piece, target_hex):
    """Says whether the attacker is close enough to engage the target (as the crow flies)."""
    return attacker_hex.distance(target_hex) <= combat_range(attacking_piece)


class RatioBreakdown:
    """The computation leading to the strength ratio, piece by piece: enough to tell its story.

    The ratio cannot be read off the board. Between the strength printed on the counters and the
    column of Table I there is the **defender's terrain**, which multiplies its strength and adds
    to the attacker's die - two effects of one square, and nothing shows them once the combat is
    resolved. This object keeps them all.

    It builds no sentence: it returns numbers and a terrain name, and it is the application that
    puts them into French (see `describe_the_ratio` in `tenebrae/application/app.py`). The engine,
    for its part, has no business knowing that a log exists.
    """

    __slots__ = ("strengths", "target_strength", "terrain", "multiplier", "die_bonus", "roll")

    def __init__(self, strengths, target_strength, terrain, multiplier, die_bonus, roll):
        self.strengths = list(strengths)
        self.target_strength = target_strength
        self.terrain = terrain
        self.multiplier = multiplier
        self.die_bonus = die_bonus
        self.roll = roll

    @property
    def attacking_strength(self):
        """What the group of attackers totals. Terrain does not play on this side."""
        return sum(self.strengths)

    @property
    def defending_strength(self):
        """The defender's strength, its terrain counted."""
        return self.target_strength * self.multiplier

    @property
    def die(self):
        """The die as the table reads it: the roll, terrain added, brought back between 1 and 6."""
        return min(6, max(1, self.roll + self.die_bonus))

    @property
    def column(self):
        """The index of the Table I column where the combat is read."""
        return ratio_column(self.attacking_strength, self.defending_strength)

    @property
    def ratio(self):
        """The strength ratio as the booklet writes it: a pair, attacker in the numerator."""
        return COLUMNS[self.column]

    @property
    def outcome(self):
        """What Table I says of this ratio and this die."""
        return TABLE_I[self.die][self.column]

    def __repr__(self):
        return (f"RatioBreakdown({self.attacking_strength} against {self.defending_strength} "
                f"in {self.terrain}, die {self.die})")


def break_down(attacking_strengths, defending_piece, defender_hexagon, roll):
    """The strength ratio computation, before its outcome is read.

    This is the only place where the defender's terrain is consulted: both entry points to combat
    - `resolve` and `fight` - go through here, and therefore cannot say two different things
    about it.
    """
    return RatioBreakdown(
        strengths=attacking_strengths,
        target_strength=defending_piece.strength,
        terrain=defender_hexagon.terrain,
        multiplier=defence_multiplier(defender_hexagon, defending_piece),
        die_bonus=terrain_die_bonus(defender_hexagon),
        roll=roll,
    )


def resolve(attacking_strengths, defending_piece, defender_hexagon, roll):
    """The outcome of a combat: one of the strings `AE`, `DE`, `EX`, `AR`, `DR`.

    `roll` is the die result (1 to 6), passed as an argument so that chance stays at the edge of
    the engine. It is modified by terrain then brought back into the table's interval.
    """
    return break_down(attacking_strengths, defending_piece, defender_hexagon, roll).outcome


class CombatResult:
    """What a combat gave: its outcome, the squares cleared, the strength ratio and the die played.

    `outcome` is `None` when the combat could not be resolved (target absent, strength illegible);
    `eliminated` is then empty, and so is `breakdown` - there was no computation to break down.

    `ratio` and `die` are those of `breakdown`: they remain attributes of their own, half the
    project already reading them that way.
    """

    __slots__ = ("outcome", "eliminated", "ratio", "die", "breakdown")

    def __init__(self, outcome, eliminated, ratio, die, breakdown=None):
        self.outcome = outcome
        self.eliminated = list(eliminated)
        self.ratio = ratio
        self.die = die
        self.breakdown = breakdown

    def __repr__(self):
        return f"CombatResult({self.outcome!r}, {len(self.eliminated)} eliminated)"


def fight(board, target_hexagon, attacker_hexagons, roll):
    """Resolves a combat on the board and **removes** the eliminated pieces.

    The attackers are held to be valid - in range, on the right side: it is up to the caller to
    have filtered them. An attacker with no legible strength is ignored in the computation but
    shares the group's fate. `AE` removes the attackers, `DE` the target, `EX` both; `AR` and `DR`
    change nothing.

    One exception, and it comes from the booklet: on an exchange, **attackers firing missiles are
    not removed** - they struck from afar, the exchange does not reach them. They do count in the
    strength ratio, though, and an `AE` eliminates them like the others: the booklet only exempts
    them from retreat and exchange.
    """
    target_piece = board.piece_on(target_hexagon)
    strengths = [board.piece_on(hexagon).strength
                 for hexagon in attacker_hexagons
                 if board.piece_on(hexagon) and board.piece_on(hexagon).strength is not None]
    if target_piece is None or target_piece.strength is None or not strengths:
        return CombatResult(None, [], None, None)

    breakdown = break_down(strengths, target_piece, target_hexagon, roll)
    outcome = breakdown.outcome

    eliminated = []
    if outcome == AE:
        eliminated.extend(attacker_hexagons)
    elif outcome == EX:
        eliminated.extend(hexagon for hexagon in attacker_hexagons
                          if not fires_missiles(board.piece_on(hexagon)))
    if outcome in (DE, EX):
        eliminated.append(target_hexagon)
    for hexagon in eliminated:
        board.remove(hexagon)

    return CombatResult(outcome, eliminated, breakdown.ratio, breakdown.die, breakdown)


class CombatRegister:
    """What a combat phase has already consumed: which squares have attacked, which have been
    attacked.

    The booklet requires that a unit fight only one combat per phase - alone or within a group of
    attackers - and that a unit be taken as a target only once.

    The register keeps **squares**, as "q,r,s" keys, and not piece keys: one counter stands for
    all the units it represents - `orques-01-15-infanteries` is placed fifteen times in scenario
    no. 4 - and the engine gives the unit no identity. The square, on the other hand, designates a
    single one, and nothing moves during a combat phase: movement has its own phase. That is what
    makes the equivalence exact for as long as the register lives.

        register = CombatRegister()
        register.can_attack("1,26,-27")           # True
        register.record(["1,26,-27"], "2,26,-28")
        register.can_attack("1,26,-27")           # False

    A combat counts as soon as it is fought: an outcome the engine leaves without effect - a
    retreat - engages the units just as much as an elimination.
    """

    __slots__ = ("engaged_attackers", "engaged_targets")

    def __init__(self):
        self.engaged_attackers = set()
        self.engaged_targets = set()

    def can_attack(self, square):
        """Says whether the unit on this square has not attacked yet during the current phase."""
        return square not in self.engaged_attackers

    def can_be_targeted(self, square):
        """Says whether the unit on this square has not been attacked yet during the current phase."""
        return square not in self.engaged_targets

    def record(self, attacking_squares, target_square):
        """Marks a combat as fought: the attackers attacked, the target was attacked."""
        self.engaged_attackers.update(attacking_squares)
        self.engaged_targets.add(target_square)
        return self

    def to_dict(self):
        """The register in a serialisable form: two sorted lists of squares.

        The sorting owes nothing to the rules - a set has no order - but it keeps the shape stable
        from one saved game to the next.
        """
        return {"engaged_attackers": sorted(self.engaged_attackers),
                "engaged_targets": sorted(self.engaged_targets)}

    def restore(self, engaged_attackers, engaged_targets):
        """Replaces the register's contents with those of a saved game."""
        self.engaged_attackers.clear()
        self.engaged_attackers.update(engaged_attackers)
        self.engaged_targets.clear()
        self.engaged_targets.update(engaged_targets)
        return self

    def reset(self):
        """Empties the register - a new combat phase makes every unit available again.

        This is also what prevents a retained square from surviving a move: between two combat
        phases there is always a movement phase, and the register is already empty when the units
        change squares.
        """
        self.engaged_attackers.clear()
        self.engaged_targets.clear()
        return self

    def __repr__(self):
        return (f"CombatRegister({len(self.engaged_attackers)} attackers, "
                f"{len(self.engaged_targets)} targets)")
