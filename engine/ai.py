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

from engine import combat
from engine.hexagon import Hex
from engine.phase import MOVEMENT

# The occupant of a seat held by the AI. No human can carry it: Discord identifiers are strings of
# digits. The value travels into the saved game, and therefore stays as it is.
AI_PLAYER = "ia"

# The name the interface displays for that seat.
AI_NAME = "IA"

# The Table I column below which the AI declines to attack: parity. This is the only difficulty
# knob - lowering it makes the AI reckless, raising it makes it timid.
MINIMUM_RATIO = combat.COLUMNS.index((1, 1))


def target_priority(board, origin, side):
    """The opposing squares in priority order, seen from `origin`: nearest first, weakest next.

    The sort is on (distance as the crow flies, effective defending strength - the counter's
    strength multiplied by the terrain occupied -, square key): aim near, strike weak, break ties
    the same way from one game to the next. Opponents with no legible strength are discarded:
    neither combat targets nor march objectives.

    This is where a future difficulty setting would live: changing this sort changes the whole AI,
    movement and combat aiming through the same function.
    """
    targets = []
    for key in board.opponents_of(side):
        hexagon = Hex.from_key(key)
        piece = board.piece_on(hexagon)
        if piece.strength is None:
            continue
        defence = piece.strength * combat.defence_multiplier(hexagon, piece)
        targets.append((origin.distance(hexagon), defence, key, hexagon))
    return [hexagon for _, _, _, hexagon in sorted(targets, key=lambda entry: entry[:3])]


def choose_target(board, origin, side):
    """The opposing square to aim at from `origin`, or `None` if no opponent is left."""
    targets = target_priority(board, origin, side)
    return targets[0] if targets else None


def play_movement(board, side):
    """Plays the side's movement phase: each unit marches towards its target.

    A unit already within engagement range of its target does not move - an archer in position
    holds it, an infantry in contact stays there. The others take, among their permitted moves,
    the square that is least out of range; at equal shortfall, the one least distant from their
    position - so a shooter stops at range instead of sticking to its target, and nobody moves for
    nothing. The engine revalidates every step: terrain, zones of control, occupied squares.

    The board changes under the iteration, but a single pass over the squares frozen at the start
    is enough to give one action per unit: an occupied square is never a destination, so every
    square in the list keeps its occupant until its own turn comes, and a freed square can only be
    taken by a unit played after it - when it has already had its turn.

    Returns the list of `(origin, destination)` pairs played - enough to write the log.
    """
    moves_played = []
    for key in sorted(board.squares_held_by(side)):
        origin = Hex.from_key(key)
        piece = board.piece_on(origin)
        if not piece.is_a_unit or piece.movement_points == 0:
            continue
        target = choose_target(board, origin, side)
        if target is None:
            continue
        objective = combat.combat_range(piece)
        if origin.distance(target) <= objective:
            continue

        def rank(hexagon, origin=origin, target=target, objective=objective):
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


def play_combat(board, side, register, roll):
    """Plays the side's combat phase: attacks concentrate on the priority targets.

    Each still-available unit looks, in its order of priorities, for a target within range and not
    yet engaged; every available unit of the side within range of that target then joins in, in a
    single combat - that is the concentration the engine allows, several attackers for one
    `fight`. Below parity (`MINIMUM_RATIO`) the unit declines and stays available: it may join a
    better-staffed group on another target.

    The `register` - the same one humans use - holds the booklet's two rules: one attack per unit
    per phase, one attack per target per phase. `roll` is called once per combat fought.

    Returns the list of combats fought: `(target, attackers, CombatResult)`.
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

        attackers = []
        for friendly_key in sorted(board.squares_held_by(side)):
            hexagon = Hex.from_key(friendly_key)
            friendly_piece = board.piece_on(hexagon)
            if (friendly_piece.is_a_unit and friendly_piece.strength is not None
                    and register.can_attack(friendly_key)
                    and combat.in_range(hexagon, friendly_piece, target)):
                attackers.append(hexagon)

        target_piece = board.piece_on(target)
        defending_strength = (target_piece.strength
                              * combat.defence_multiplier(target, target_piece))
        strengths = sum(board.piece_on(hexagon).strength for hexagon in attackers)
        if combat.ratio_column(strengths, defending_strength) < MINIMUM_RATIO:
            continue

        result = combat.fight(board, target, attackers, roll())
        register.record([hexagon.key for hexagon in attackers], target.key)
        combats_fought.append((target, attackers, result))
    return combats_fought


def play_turn(board, turn, register, roll):
    """Plays the active side's whole turn - movement then combat - and hands play back.

    On entry, the current phase must be the movement phase of the AI's side; on exit, it is the
    movement phase of the next side. In between, the phase change is everyone's: `Turn.advance()`
    and a combat register wiped clean - exactly what a human player clicking "next phase" does.

    Returns `(moves, combats)`, what the two phases played.
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
