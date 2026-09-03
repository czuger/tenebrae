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

What a combat phase has already consumed is kept apart, in `tenebrae.engine.combat_register`.
"""

from collections.abc import Iterable, Sequence
from typing import Optional

from tenebrae.engine.board import Board
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import Piece

# The five possible outcomes. Only `AE`, `DE` and `EX` change anything on the board; the retreats
# `AR` and `DR` are read but left without effect, for want of a retreat rule.
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


def ratio_column(attacking_strength: int, defending_strength: int) -> int:
    """Finds the Table I column of a strength ratio.

    The ratio runs from 1-5 to 6-1 and is "always rounded in the defender's favour": 10 against 4
    is 2 against 1, 4 against 10 is 1 against 3.

    Args:
        attacking_strength: What the attackers total.
        defending_strength: The defender's strength, terrain counted.

    Returns:
        The index in `COLUMNS`.
    """
    if attacking_strength <= 0:
        return 0
    if defending_strength <= 0:
        return len(COLUMNS) - 1
    if attacking_strength >= defending_strength:
        return COLUMNS.index((min(attacking_strength // defending_strength, 6), 1))
    return COLUMNS.index((1, min(-(-defending_strength // attacking_strength), 5)))


def defence_multiplier(hexagon: Hex, defending_piece: Piece) -> int:
    """Reads the factor the defender's terrain applies to its strength.

    Args:
        hexagon: The square the defender occupies.
        defending_piece: The defender, whose faction decides the woods' bonus.

    Returns:
        1, 2 or 3.
    """
    terrain = hexagon.terrain
    if terrain == "bois":
        return 2 if defending_piece.faction == ELVES_FACTION else 1
    return DEFENCE_MULTIPLIERS.get(terrain, 1)


def terrain_die_bonus(hexagon: Hex) -> int:
    """Reads what the defender's terrain adds to the attacker's die.

    Args:
        hexagon: The square the defender occupies.

    Returns:
        2 in woods or hills, 0 otherwise.
    """
    return 2 if hexagon.terrain in DIE_BONUS_TERRAINS else 0


def fires_missiles(piece: Optional[Piece]) -> bool:
    """Says whether a piece engages by fire: it carries both a fire strength **and** a range.

    The engine offers no choice between fire and melee: a piece that fires is held to fire in every
    combat it fights, whatever the distance.

    Args:
        piece: The piece, or `None` for an empty square.

    Returns:
        True for missile troops.
    """
    if piece is None:
        return False
    return bool(piece.fire and piece.range)


def combat_range(piece: Piece) -> int:
    """Reads the distance at which a piece can engage.

    Args:
        piece: The attacker.

    Returns:
        Its firing range if it fires, 1 otherwise.
    """
    if fires_missiles(piece):
        return piece.range
    return 1


def in_range(attacker_hex: Hex, attacking_piece: Piece, target_hex: Hex) -> bool:
    """Says whether an attacker is close enough to engage a target, as the crow flies.

    Args:
        attacker_hex: The attacker's square.
        attacking_piece: The attacker.
        target_hex: The target's square.

    Returns:
        True if the distance does not exceed the attacker's combat range.
    """
    return attacker_hex.distance(target_hex) <= combat_range(attacking_piece)


class RatioBreakdown:
    """The computation leading to the strength ratio, piece by piece: enough to tell its story.

    Between the strength printed on the counters and the column of Table I there is the
    **defender's terrain**, which multiplies its strength and adds to the attacker's die. This
    object keeps every term; it is the application that puts them into French
    (`describe_the_ratio` in `tenebrae/application/app.py`).
    """

    __slots__ = ("strengths", "target_strength", "terrain", "multiplier", "die_bonus", "roll")

    strengths: list[int]
    target_strength: int
    terrain: Optional[str]
    multiplier: int
    die_bonus: int
    roll: int

    def __init__(self, strengths: Iterable[int], target_strength: int, terrain: Optional[str],
                 multiplier: int, die_bonus: int, roll: int) -> None:
        """Keeps the terms of the computation.

        Args:
            strengths: The strength of each attacker.
            target_strength: The defender's printed strength.
            terrain: The defender's terrain.
            multiplier: What that terrain multiplies the defence by.
            die_bonus: What that terrain adds to the die.
            roll: The die as rolled, before terrain.
        """
        self.strengths = list(strengths)
        self.target_strength = target_strength
        self.terrain = terrain
        self.multiplier = multiplier
        self.die_bonus = die_bonus
        self.roll = roll

    @property
    def attacking_strength(self) -> int:
        """What the group of attackers totals; terrain does not play on this side."""
        return sum(self.strengths)

    @property
    def defending_strength(self) -> int:
        """The defender's strength, its terrain counted."""
        return self.target_strength * self.multiplier

    @property
    def die(self) -> int:
        """The die as the table reads it: the roll, terrain added, brought back between 1 and 6."""
        return min(6, max(1, self.roll + self.die_bonus))

    @property
    def column(self) -> int:
        """The index of the Table I column where the combat is read."""
        return ratio_column(self.attacking_strength, self.defending_strength)

    @property
    def ratio(self) -> tuple[int, int]:
        """The strength ratio as the booklet writes it: a pair, attacker in the numerator."""
        return COLUMNS[self.column]

    @property
    def outcome(self) -> str:
        """What Table I says of this ratio and this die."""
        return TABLE_I[self.die][self.column]

    def __repr__(self) -> str:
        """The two strengths, the terrain and the die."""
        return (f"RatioBreakdown({self.attacking_strength} against {self.defending_strength} "
                f"in {self.terrain}, die {self.die})")


def break_down(attacking_strengths: Iterable[int], defending_piece: Piece,
               defender_hexagon: Hex, roll: int) -> RatioBreakdown:
    """Computes the strength ratio, before its outcome is read.

    The only place where the defender's terrain is consulted: `resolve` and `fight` both go
    through here and cannot disagree about it.

    Args:
        attacking_strengths: The strength of each attacker.
        defending_piece: The defender.
        defender_hexagon: The square it occupies.
        roll: The die result, 1 to 6.

    Returns:
        The breakdown of the computation.
    """
    return RatioBreakdown(
        strengths=attacking_strengths,
        target_strength=defending_piece.strength,
        terrain=defender_hexagon.terrain,
        multiplier=defence_multiplier(defender_hexagon, defending_piece),
        die_bonus=terrain_die_bonus(defender_hexagon),
        roll=roll,
    )


def resolve(attacking_strengths: Iterable[int], defending_piece: Piece,
            defender_hexagon: Hex, roll: int) -> str:
    """Reads the outcome of a combat off Table I, without touching any board.

    Args:
        attacking_strengths: The strength of each attacker.
        defending_piece: The defender.
        defender_hexagon: The square it occupies.
        roll: The die result, 1 to 6, passed in so that chance stays at the edge of the engine.

    Returns:
        One of `AE`, `DE`, `EX`, `AR`, `DR`.
    """
    return break_down(attacking_strengths, defending_piece, defender_hexagon, roll).outcome


class CombatResult:
    """What a combat gave: its outcome, the squares cleared, the strength ratio and the die played.

    `outcome` is `None` when the combat could not be resolved (target absent, strength illegible);
    `eliminated` is then empty, and so is `breakdown`. `ratio` and `die` repeat those of
    `breakdown` as attributes of their own.
    """

    __slots__ = ("outcome", "eliminated", "ratio", "die", "breakdown")

    outcome: Optional[str]
    eliminated: list[Hex]
    ratio: Optional[tuple[int, int]]
    die: Optional[int]
    breakdown: Optional[RatioBreakdown]

    def __init__(self, outcome: Optional[str], eliminated: Iterable[Hex],
                 ratio: Optional[tuple[int, int]], die: Optional[int],
                 breakdown: Optional[RatioBreakdown] = None) -> None:
        """Keeps the result of a combat.

        Args:
            outcome: The Table I outcome, or `None` if the combat could not be resolved.
            eliminated: The squares cleared.
            ratio: The strength ratio read, attacker in the numerator.
            die: The die as the table read it.
            breakdown: The computation behind the ratio.
        """
        self.outcome = outcome
        self.eliminated = list(eliminated)
        self.ratio = ratio
        self.die = die
        self.breakdown = breakdown

    def __repr__(self) -> str:
        """The outcome and the number of squares cleared."""
        return f"CombatResult({self.outcome!r}, {len(self.eliminated)} eliminated)"


def fight(board: Board, target_hexagon: Hex, attacker_hexagons: Sequence[Hex],
          roll: int) -> CombatResult:
    """Resolves a combat on the board and **removes** the eliminated pieces.

    The attackers are held to be valid - in range, on the right side: it is up to the caller to
    have filtered them. An attacker with no legible strength is ignored in the computation but
    shares the group's fate. `AE` removes the attackers, `DE` the target, `EX` both - except the
    attackers firing missiles, whom the booklet exempts from retreat and exchange; `AR` and `DR`
    change nothing.

    Args:
        board: The board the combat is played on.
        target_hexagon: The defender's square.
        attacker_hexagons: The attackers' squares.
        roll: The die result, 1 to 6.

    Returns:
        The result; its `outcome` is `None` if the target is absent or has no legible strength.
    """
    target_piece = board.piece_on(target_hexagon)
    strengths = [board.piece_on(hexagon).strength
                 for hexagon in attacker_hexagons
                 if board.piece_on(hexagon) and board.piece_on(hexagon).strength is not None]
    if target_piece is None or target_piece.strength is None or not strengths:
        return CombatResult(None, [], None, None)

    breakdown = break_down(strengths, target_piece, target_hexagon, roll)
    outcome = breakdown.outcome

    eliminated: list[Hex] = []
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
