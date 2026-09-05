"""Combat resolution in Ave Tenebrae: Table I of the booklet, and nothing more.

The booklet (`tenebrae/game_box/ave_tenebrae_regles_en.md`, "Combats") gives a two-way table - the
strength ratio in columns, the die roll in rows - each cell of which gives the outcome of the
battle: attacker eliminated, defender eliminated, exchange, or one of the two retreats. This module
transcribes that table, computes the strength ratio ("always rounded in the defender's favour") and
applies the terrain modifiers from the *Terrain table*.

`AR` and `DR` make the units fall back, and the fall-back is a rule of its own -
`tenebrae.engine.retreat`, which this module calls and which alone knows what to do when there is
nowhere to fall back to. `EX` takes the defender and, with it, "attacking units totalling a
strength at least equal" - `exchanged_attackers` picks them, and the group it picks is the
**smallest** that can reach that total. An attacker that fires escapes both `EX` and the retreats:
"a unit firing missiles can in no case suffer a retreat or exchange result", read as covering the
unit that is firing, so a missile unit assaulted in its own square gives ground like any other; a
defender in a fort or a castle escapes `DR` too. Special abilities, the cavalry charge, phalanxes
and the day/night alternation are out of reach - see `tenebrae/engine/README.md`.

The advance after combat is not played: the booklet lets the attacker occupy the square the
defender has just left, "the decision must be announced immediately after the combat", and that is
a player's decision, which nothing here asks for.

What a combat phase has already consumed is kept apart, in `tenebrae.engine.combat_register`, and
the units removed from play in `tenebrae.engine.casualties`.
"""

from collections.abc import Iterable, Sequence
from typing import Optional

from tenebrae.engine.board import Board
from tenebrae.engine.casualties import Casualties
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import OPPONENTS, Piece
from tenebrae.engine.retreat import RetreatOutcome, fall_back, fall_back_together

# The five possible outcomes. `AE`, `DE` and `EX` clear squares, `AR` and `DR` make units fall
# back: all five change the board.
AE, DE, EX, AR, DR = "AE", "DE", "EX", "AR", "DR"

# A defender holding one of these "does not suffer DR results (defender retreats)".
RETREAT_PROOF_TERRAINS = frozenset({"fort", "chateau"})

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
    if terrain is None:
        return 1
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
    # `fires_missiles` has already required the range; the second test only narrows its type.
    if fires_missiles(piece) and piece.range is not None:
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


class StrengthRatio:
    """What a combat weighs, and everything that is known of it **before the die is rolled**.

    The two sides of Table I's column: what the attackers total, and what the defender opposes once
    its terrain has multiplied it. That much is settled the moment the attackers are designated —
    which is why the browser can show it during the combat phase, while the player is still
    choosing whom to send in (`GET /combat/ratio`).

    `RatioBreakdown` is this, plus what the die adds.
    """

    __slots__ = ("strengths", "target_strength", "terrain", "multiplier", "die_bonus")

    strengths: list[int]
    target_strength: int
    terrain: Optional[str]
    multiplier: int
    die_bonus: int

    def __init__(self, strengths: Iterable[int], target_strength: int, terrain: Optional[str],
                 multiplier: int, die_bonus: int) -> None:
        """Keeps the terms the ratio is read from.

        Args:
            strengths: The strength of each attacker.
            target_strength: The defender's printed strength.
            terrain: The defender's terrain.
            multiplier: What that terrain multiplies the defence by.
            die_bonus: What that terrain adds to the die - known before the die is thrown, since
                it is the ground that gives it and not the throw.
        """
        self.strengths = list(strengths)
        self.target_strength = target_strength
        self.terrain = terrain
        self.multiplier = multiplier
        self.die_bonus = die_bonus

    @property
    def attacking_strength(self) -> int:
        """What the group of attackers totals; terrain does not play on this side."""
        return sum(self.strengths)

    @property
    def defending_strength(self) -> int:
        """The defender's strength, its terrain counted."""
        return self.target_strength * self.multiplier

    @property
    def column(self) -> int:
        """The index of the Table I column where the combat is read."""
        return ratio_column(self.attacking_strength, self.defending_strength)

    @property
    def ratio(self) -> tuple[int, int]:
        """The strength ratio as the booklet writes it: a pair, attacker in the numerator."""
        return COLUMNS[self.column]

    @property
    def outcomes(self) -> tuple[str, ...]:
        """What each face of the die would give on this ratio, from 1 to 6.

        The **faces**, not the rows of Table I: on a hill the ground adds 2 to the throw, so a 1
        reads on the third row and three of the six faces read on the sixth. Listing the rows
        instead would announce outcomes that cannot happen there.

        Returns:
            Six outcomes, in the order the die can fall.
        """
        return tuple(TABLE_I[self.die_read_at(roll)][self.column] for roll in range(1, 7))

    def die_read_at(self, roll: int) -> int:
        """The row of Table I a throw is read on: the roll, terrain added, kept between 1 and 6.

        Args:
            roll: The die as thrown.

        Returns:
            The row, 1 to 6.
        """
        return min(6, max(1, roll + self.die_bonus))

    def with_the_die(self, roll: int) -> "RatioBreakdown":
        """The same weighing once the die is rolled: what Table I is then read with.

        Args:
            roll: The die as rolled, before terrain.

        Returns:
            The breakdown, the weighing unchanged in it.
        """
        return RatioBreakdown(self.strengths, self.target_strength, self.terrain,
                              self.multiplier, self.die_bonus, roll)

    def __repr__(self) -> str:
        """The two strengths and the terrain."""
        return (f"StrengthRatio({self.attacking_strength} against {self.defending_strength} "
                f"in {self.terrain})")


class RatioBreakdown(StrengthRatio):
    """The whole computation leading to an outcome, piece by piece: enough to tell its story.

    The weighing, and what the **defender's terrain** adds to the attacker's die on top of
    multiplying the defence. This object keeps every term; it is the application that puts them
    into French (`describe_the_ratio` in `tenebrae/application/logs/combat_sentences.py`).
    """

    __slots__ = ("roll",)

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
        super().__init__(strengths, target_strength, terrain, multiplier, die_bonus)
        self.roll = roll

    @property
    def die(self) -> int:
        """The die as the table reads it: the roll, terrain added, brought back between 1 and 6."""
        return self.die_read_at(self.roll)

    @property
    def outcome(self) -> str:
        """What Table I says of this ratio and this die."""
        return TABLE_I[self.die][self.column]

    def __repr__(self) -> str:
        """The two strengths, the terrain and the die."""
        return (f"RatioBreakdown({self.attacking_strength} against {self.defending_strength} "
                f"in {self.terrain}, die {self.die})")


def weigh(board: Board, target_hexagon: Hex,
          attacker_hexagons: Sequence[Hex]) -> Optional[StrengthRatio]:
    """Weighs a combat on the board, before any die: what the ratio will be read from.

    The **one** place where a combat's forces are collected off the board, `fight` included: an
    attacker with no legible strength does not count, and a target that is absent or has no legible
    strength is no combat at all. The forecast the browser shows during the combat phase is
    therefore the very weighing the resolution will use, and the two cannot come to disagree.

    The attackers are held to be valid - in range, on the right side: it is up to the caller to
    have filtered them, as for `fight`.

    Args:
        board: The board the combat would be played on.
        target_hexagon: The defender's square.
        attacker_hexagons: The attackers' squares.

    Returns:
        The weighing, or `None` where there is nothing to weigh.
    """
    target_piece = board.piece_on(target_hexagon)
    attacking_pieces = [board.piece_on(hexagon) for hexagon in attacker_hexagons]
    strengths = [piece.strength for piece in attacking_pieces
                 if piece is not None and piece.strength is not None]
    if target_piece is None or target_piece.strength is None or not strengths:
        return None
    return StrengthRatio(strengths, target_piece.strength, target_hexagon.terrain,
                         defence_multiplier(target_hexagon, target_piece),
                         terrain_die_bonus(target_hexagon))


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

    Raises:
        ValueError: If the defender has no legible strength: there is no ratio to compute.
    """
    if defending_piece.strength is None:
        raise ValueError(f"{defending_piece.key} has no legible strength: no ratio to compute")
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
    """What a combat gave: its outcome, the squares cleared, the fall-backs, the ratio and the die.

    `outcome` is `None` when the combat could not be resolved (target absent, strength illegible);
    `eliminated` is then empty, and so is `breakdown`. `ratio` and `die` repeat those of
    `breakdown` as attributes of their own.

    `eliminated` holds **every** square cleared, whether the table said so or a unit fell for want
    of a retreat; `retreats` tells the fall-backs themselves, one outcome per unit that had to give
    ground (`tenebrae/engine/retreat.py`).
    """

    __slots__ = ("outcome", "eliminated", "ratio", "die", "breakdown", "retreats")

    outcome: Optional[str]
    eliminated: list[Hex]
    ratio: Optional[tuple[int, int]]
    die: Optional[int]
    breakdown: Optional[RatioBreakdown]
    retreats: list[RetreatOutcome]

    def __init__(self, outcome: Optional[str], eliminated: Iterable[Hex],
                 ratio: Optional[tuple[int, int]], die: Optional[int],
                 breakdown: Optional[RatioBreakdown] = None,
                 retreats: Iterable[RetreatOutcome] = ()) -> None:
        """Keeps the result of a combat.

        Args:
            outcome: The Table I outcome, or `None` if the combat could not be resolved.
            eliminated: The squares cleared, the fall-backs' own eliminations included.
            ratio: The strength ratio read, attacker in the numerator.
            die: The die as the table read it.
            breakdown: The computation behind the ratio.
            retreats: What each unit forced to fall back did.
        """
        self.outcome = outcome
        self.eliminated = list(eliminated)
        self.ratio = ratio
        self.die = die
        self.breakdown = breakdown
        self.retreats = list(retreats)

    @property
    def moves(self) -> list[tuple[Hex, Hex]]:
        """Every unit that gave ground, `(origin, destination)`, in the order they moved."""
        return [move for retreat in self.retreats for move in retreat.moves]

    def square_after(self, hexagon: Hex) -> Hex:
        """Follows the unit that stood on a square through the fall-backs of this combat.

        The combat register counts units by their square, and a combat that moves them would
        otherwise mark squares they have left (see `tenebrae/engine/combat_register.py`). A pushed
        unit may be moved by more than one chain: the moves are therefore followed in order.

        Args:
            hexagon: The square the unit stood on when the combat was declared.

        Returns:
            The square it stands on now - the same one if it did not move, and the one it was
            eliminated on if it was.
        """
        square = hexagon
        for origin, destination in self.moves:
            if origin == square:
                square = destination
        return square

    def __repr__(self) -> str:
        """The outcome, the squares cleared and the units that gave ground."""
        return (f"CombatResult({self.outcome!r}, {len(self.eliminated)} eliminated, "
                f"{len(self.moves)} fell back)")


def suffers_a_retreat(piece: Optional[Piece], hexagon: Hex, as_defender: bool) -> bool:
    """Says whether a unit is one the booklet lets a retreat result touch.

    Two exemptions, both the booklet's own: "a unit firing missiles can in no case suffer a
    retreat or exchange result", and "a unit defending in a castle or a citadel does not suffer DR
    results". The first covers the unit **that is firing**, which is the attacker: the engine holds
    a missile unit to fire in every combat it declares. A defender fires nothing - a catapult
    assaulted in its own square falls back like any other unit, and only its terrain can hold it
    there.

    Args:
        piece: The unit, or `None` for an empty square.
        hexagon: The square it holds.
        as_defender: True when it is suffering a `DR`, False for an `AR`.

    Returns:
        True if it must fall back.
    """
    if piece is None:
        return False
    if as_defender:
        return hexagon.terrain not in RETREAT_PROOF_TERRAINS
    return not fires_missiles(piece)


def record_the_loss(casualties: Optional[Casualties], hexagon: Hex,
                    piece: Optional[Piece]) -> None:
    """Enters a unit removed from play in the game's register of casualties.

    "Eliminated units are kept by the player who eliminated them": the taker is the side opposing
    the one that fell - the only other side in a combat, and the one that forced the retreat when
    a unit falls for want of one.

    Args:
        casualties: The register, or `None` when the caller keeps none.
        hexagon: The square the unit fell on.
        piece: The piece removed; nothing is recorded for an empty square.
    """
    if casualties is None or piece is None:
        return
    casualties.record(hexagon, piece, OPPONENTS.get(piece.side))


def exchanged_attackers(board: Board, attacker_hexagons: Sequence[Hex],
                        defending_strength: int) -> list[Hex]:
    """Picks the attackers an exchange takes with the defender.

    The booklet asks for "attacking units totalling a strength at least equal"; **which** units is
    left open, and it is read here as the fewest counters that can reach that total. Taking the
    strongest first gives exactly that: no *k* counters can total more than the *k* strongest, so
    the first *k* to reach the defender's strength are the smallest group there is. Ties are broken
    by square key, as everywhere else in the engine.

    Note what the reading costs: the fewest counters are the biggest ones, so a general standing
    among its infantry is what the exchange takes. That is the price of counting counters rather
    than strength, and it is what the sentence asks for read this way.

    The strength to reach is the defender's own, as it is printed on the counter: the terrain
    multiplier is what the ratio is worked out on, and an exchange trades units, not positions.

    Two attackers are never picked - a unit that fires, which the booklet exempts from the exchange
    altogether, and one whose strength is illegible, which cannot help reach a total. Should
    everything that can be picked still fall short - a defender stronger than all its assailants
    together - the whole group goes, which is as far as the sentence carries.

    Args:
        board: The board, read for the attacking pieces.
        attacker_hexagons: The attackers' squares.
        defending_strength: The strength the group must total: the defender's.

    Returns:
        The squares the exchange clears, in the order the attackers were given.
    """
    candidates = [(piece.strength, hexagon) for hexagon in attacker_hexagons
                  if (piece := board.piece_on(hexagon)) is not None
                  and piece.strength is not None and not fires_missiles(piece)]

    taken: set[str] = set()
    total = 0
    for strength, hexagon in sorted(candidates, key=lambda one: (-one[0], one[1].key)):
        if total >= defending_strength:
            break
        taken.add(hexagon.key)
        total += strength
    return [hexagon for hexagon in attacker_hexagons if hexagon.key in taken]


def fight(board: Board, target_hexagon: Hex, attacker_hexagons: Sequence[Hex], roll: int,
          casualties: Optional[Casualties] = None) -> CombatResult:
    """Resolves a combat on the board, **removing** the eliminated pieces and falling back the rest.

    The attackers are held to be valid - in range, on the right side: it is up to the caller to
    have filtered them. An attacker with no legible strength is ignored in the computation; under
    `AE` it shares the group's fate all the same, under `EX` it is never one of those picked. `AE`
    removes the attackers, `DE` the target, `EX` the target and as few attackers as total its
    strength (`exchanged_attackers`) - the attackers firing missiles apart, whom the booklet
    exempts from retreat and exchange; `AR` and `DR` make them fall back one square, and a unit
    with nowhere to fall back to is removed from play in its turn
    (`tenebrae/engine/retreat.py`).

    Args:
        board: The board the combat is played on.
        target_hexagon: The defender's square.
        attacker_hexagons: The attackers' squares.
        roll: The die result, 1 to 6.
        casualties: The game's register of units removed from play, filled as they fall. Optional:
            a caller that keeps no count - a test questioning the table - passes none.

    Returns:
        The result; its `outcome` is `None` if the target is absent or has no legible strength.
    """
    weighed = weigh(board, target_hexagon, attacker_hexagons)
    if weighed is None:
        return CombatResult(None, [], None, None)

    breakdown = weighed.with_the_die(roll)
    outcome = breakdown.outcome

    eliminated: list[Hex] = []
    if outcome == AE:
        eliminated.extend(attacker_hexagons)
    elif outcome == EX:
        eliminated.extend(exchanged_attackers(board, attacker_hexagons, weighed.target_strength))
    if outcome in (DE, EX):
        eliminated.append(target_hexagon)
    for hexagon in eliminated:
        record_the_loss(casualties, hexagon, board.piece_on(hexagon))
        board.remove(hexagon)

    retreats = fall_back_from(board, target_hexagon, attacker_hexagons, outcome, casualties)
    # A unit that could not fall back has left the board too: the caller clears one list of
    # squares, whichever way they were emptied.
    eliminated.extend(retreat.eliminated for retreat in retreats
                      if retreat.eliminated is not None)

    return CombatResult(outcome, eliminated, breakdown.ratio, breakdown.die, breakdown, retreats)


def fall_back_from(board: Board, target_hexagon: Hex, attacker_hexagons: Sequence[Hex],
                   outcome: str, casualties: Optional[Casualties]) -> list[RetreatOutcome]:
    """Applies whichever of the two retreat results the table gave, if it gave one.

    Args:
        board: The board, modified in place.
        target_hexagon: The defender's square.
        attacker_hexagons: The attackers' squares.
        outcome: The Table I outcome.
        casualties: The register to enter a unit that falls for want of a retreat.

    Returns:
        One outcome per unit that had to give ground; empty for the three eliminations.
    """
    if outcome == DR:
        defender = board.piece_on(target_hexagon)
        if not suffers_a_retreat(defender, target_hexagon, as_defender=True):
            return []
        outcomes = [fall_back(board, target_hexagon)]
    elif outcome == AR:
        falling = [hexagon for hexagon in attacker_hexagons
                   if suffers_a_retreat(board.piece_on(hexagon), hexagon, as_defender=False)]
        outcomes = fall_back_together(board, falling)
    else:
        return []

    for retreat in outcomes:
        # The piece is already off the board: the outcome carries it, which is what the register
        # needs to name it.
        if retreat.eliminated is not None:
            record_the_loss(casualties, retreat.eliminated, retreat.piece)
    return outcomes
