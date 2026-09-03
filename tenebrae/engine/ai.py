"""The artificial opponent: one more player, with no browser and no Discord account.

The booklet assumes two players around the map; this module takes the place of the second. It
knows nothing of the rules - it **chooses**, and lets the engine judge: every move goes through
`Board.move`, every combat through `combat.fight`, every availability check through
`CombatRegister`. An illegal decision is simply refused, as it would be for a human.

The strategy is short and deliberate. Each unit picks its target - the nearest opponent, the
weakest at equal distance - and marches until it has it within engagement range: adjacent for
infantry, within firing range for whatever fires. In combat, attacks concentrate: every available
unit within range of a target engages it together, in a single combat - the "one attack per target
per phase" rule forbids coming back to it anyway. The AI does not attack below parity: Table I
forgives nothing under column 1-1.

The limits are deliberate too: the march aims as the crow flies, not by path cost - a unit may
therefore skirt a lake instead of going round it the short way; magic is not played, the engine
already skipping it; and there is neither withdrawal, nor garrison, nor terrain defence - the AI
advances, always.

Every tie-break is deterministic: units play in the order of their square keys, and every sort key
ends with a square key. At equal die, two identical games replay identically - that is what makes
the AI testable. The die itself stays at the edge of the engine: `roll` is a callable supplied by
the caller, one draw per combat.
"""

from collections.abc import Callable
from typing import Optional

from tenebrae.engine import combat
from tenebrae.engine.board import Board
from tenebrae.engine.combat import CombatResult
from tenebrae.engine.combat_register import CombatRegister
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.phase import MOVEMENT, Turn

# The occupant of a seat held by the AI. No human can carry it: Discord identifiers are strings of
# digits. The value travels into the saved game, and therefore stays as it is.
AI_PLAYER = "ia"

# The name the interface displays for that seat.
AI_NAME = "IA"

# The Table I column below which the AI declines to attack: parity. This is the only difficulty
# knob - lowering it makes the AI reckless, raising it makes it timid.
MINIMUM_RATIO = combat.COLUMNS.index((1, 1))

# A move played: `(origin, destination)`.
Move = tuple[Hex, Hex]

# A combat fought: `(target, attackers, result)`.
Combat = tuple[Hex, list[Hex], CombatResult]


def target_priority(board: Board, origin: Hex, side: str) -> list[Hex]:
    """Ranks the opposing squares seen from `origin`: nearest first, weakest next.

    The sort is on (distance as the crow flies, effective defending strength, square key): aim
    near, strike weak, break ties the same way from one game to the next. Opponents with no legible
    strength are discarded. A future difficulty setting would live here: this sort steers both
    movement and combat.

    Args:
        board: The board.
        origin: The square the unit looks from.
        side: The unit's side.

    Returns:
        The opposing squares, in priority order.
    """
    targets = []
    for key in board.opponents_of(side):
        hexagon = Hex.from_key(key)
        piece = board.piece_on(hexagon)
        if piece is None or piece.strength is None:
            continue
        defence = piece.strength * combat.defence_multiplier(hexagon, piece)
        targets.append((origin.distance(hexagon), defence, key, hexagon))
    return [hexagon for _, _, _, hexagon in sorted(targets, key=lambda entry: entry[:3])]


def choose_target(board: Board, origin: Hex, side: str) -> Optional[Hex]:
    """Picks the opposing square to aim at from `origin`.

    Args:
        board: The board.
        origin: The square the unit looks from.
        side: The unit's side.

    Returns:
        The first square of `target_priority`, or `None` if no opponent is left.
    """
    targets = target_priority(board, origin, side)
    return targets[0] if targets else None


def play_movement(board: Board, side: str) -> list[Move]:
    """Plays the side's movement phase: each unit marches towards its target.

    A unit already within engagement range of its target does not move. The others take, among
    their permitted moves, the square that is least out of range; at equal shortfall, the one least
    distant from their position - so a shooter stops at range, and nobody moves for nothing. The
    engine revalidates every step.

    A single pass over the squares frozen at the start gives one action per unit: an occupied
    square is never a destination, so every square in the list keeps its occupant until its own
    turn comes.

    Args:
        board: The board, modified in place.
        side: The side that plays.

    Returns:
        The `(origin, destination)` pairs played, in order.
    """
    moves_played = []
    for key in sorted(board.squares_held_by(side)):
        origin = Hex.from_key(key)
        piece = board.piece_on(origin)
        if piece is None or not piece.is_a_unit or piece.movement_points == 0:
            continue
        target = choose_target(board, origin, side)
        if target is None:
            continue
        objective = combat.combat_range(piece)
        if origin.distance(target) <= objective:
            continue

        def rank(hexagon: Hex, origin: Hex = origin, target: Hex = target,
                 objective: int = objective) -> tuple[int, int, str]:
            """The sort key of a candidate destination: shortfall, distance walked, square key."""
            shortfall = max(0, hexagon.distance(target) - objective)
            return (shortfall, origin.distance(hexagon), hexagon.key)

        candidates = board.moves(origin)
        if not candidates:
            continue
        destination = min(candidates, key=rank)
        if rank(destination) >= rank(origin):
            continue
        if board.move(origin, destination):
            moves_played.append((origin, destination))
    return moves_played


def available_attackers(board: Board, side: str, target: Hex,
                        register: CombatRegister) -> list[Hex]:
    """Gathers every unit of the side that can still engage a target this phase.

    Args:
        board: The board.
        side: The attacking side.
        target: The square aimed at.
        register: What the phase has already consumed.

    Returns:
        The attackers' squares, in key order.
    """
    attackers = []
    for key in sorted(board.squares_held_by(side)):
        hexagon = Hex.from_key(key)
        piece = board.piece_on(hexagon)
        if (piece is not None and piece.is_a_unit and piece.strength is not None
                and register.can_attack(key) and combat.in_range(hexagon, piece, target)):
            attackers.append(hexagon)
    return attackers


def strength_on(board: Board, hexagon: Hex) -> int:
    """Reads the strength printed on the counter standing on a square.

    Args:
        board: The board.
        hexagon: The square.

    Returns:
        The strength; 0 for an empty square or an illegible counter, which weigh nothing.
    """
    piece = board.piece_on(hexagon)
    return 0 if piece is None or piece.strength is None else piece.strength


def worth_attacking(board: Board, target: Hex, attackers: list[Hex]) -> bool:
    """Says whether the group reaches the ratio below which the AI declines to attack.

    Args:
        board: The board.
        target: The square aimed at.
        attackers: The attackers' squares.

    Returns:
        True if the Table I column is at least `MINIMUM_RATIO`; False for an absent or illegible
        target, which no one can be sent against.
    """
    target_piece = board.piece_on(target)
    if target_piece is None or target_piece.strength is None:
        return False
    defending_strength = target_piece.strength * combat.defence_multiplier(target, target_piece)
    strengths = sum(strength_on(board, hexagon) for hexagon in attackers)
    return combat.ratio_column(strengths, defending_strength) >= MINIMUM_RATIO


def play_combat(board: Board, side: str, register: CombatRegister,
                roll: Callable[[], int]) -> list[Combat]:
    """Plays the side's combat phase: attacks concentrate on the priority targets.

    Each still-available unit looks, in its order of priorities, for a target within range and not
    yet engaged; every available unit of the side within range of that target then joins in, in a
    single combat. Below parity the unit declines and stays available for a better-staffed group.

    Args:
        board: The board, modified in place.
        side: The side that plays.
        register: The phase register, the same one humans use; filled as combats are fought.
        roll: Called once per combat fought, returns the die.

    Returns:
        The `(target, attackers, result)` triples of the combats fought, in order.
    """
    combats_fought = []
    for key in sorted(board.squares_held_by(side)):
        origin = Hex.from_key(key)
        piece = board.piece_on(origin)
        if piece is None or piece.side != side:
            continue  # eliminated in an exchange earlier in the phase
        if not piece.is_a_unit or piece.strength is None or not register.can_attack(key):
            continue

        target = next((candidate for candidate in target_priority(board, origin, side)
                       if register.can_be_targeted(candidate.key)
                       and combat.in_range(origin, piece, candidate)), None)
        if target is None:
            continue

        attackers = available_attackers(board, side, target, register)
        if not worth_attacking(board, target, attackers):
            continue

        result = combat.fight(board, target, attackers, roll())
        register.record([hexagon.key for hexagon in attackers], target.key)
        combats_fought.append((target, attackers, result))
    return combats_fought


def play_turn(board: Board, turn: Turn, register: CombatRegister,
              roll: Callable[[], int]) -> tuple[list[Move], list[Combat]]:
    """Plays the active side's whole turn - movement then combat - and hands play back.

    On entry, the current phase must be the movement phase of the AI's side; on exit, it is the
    movement phase of the next side. The phase changes are those a human clicking "next phase"
    makes: `Turn.advance()` and a combat register wiped clean.

    Args:
        board: The board, modified in place.
        turn: The turn, advanced in place.
        register: The phase register, reset at each phase change.
        roll: Called once per combat fought, returns the die.

    Returns:
        `(moves, combats)`, what the two phases played.

    Raises:
        ValueError: If the current phase is not a movement phase.
    """
    if turn.phase_type != MOVEMENT:
        raise ValueError("the AI comes into play at its movement phase, nowhere else")
    side = turn.active_side
    moves = play_movement(board, side)
    turn.advance()
    register.reset()
    combats = play_combat(board, side, register, roll)
    turn.advance()
    register.reset()
    return moves, combats
