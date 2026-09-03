"""Combat: whether a unit can engage a target, and resolving the attack.

The server revalidates everything the browser proposes - the phase, the target's side, each
attacker's range and availability -, rolls the die, applies the result to the board and logs the
outcome in French (`logs/combat_sentences.py`). A unit fights only once per phase: the combat
register (`tenebrae/engine/combat_register.py`) is what refuses a second turn.
"""

from collections.abc import Mapping

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from tenebrae.application import current_game
from tenebrae.application.current_game import (BOARD, REGISTER, TURN, save_the_game,
                                               unavailable_units)
from tenebrae.application.logs.battle_log import LOG
from tenebrae.application.logs.combat_sentences import combat_message, describe_the_ratio
from tenebrae.application.routes.authorization import active_side_required
from tenebrae.application.routes.reading import read_a_hexagon
from tenebrae.engine import combat
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.phase import COMBAT

blueprint = Blueprint("combat", __name__)

# The refusals, French like everything the player reads. The two of the combat register go to the
# log, and the browser uses them so as not to highlight a unit that has already had its turn.
OUT_OF_RANGE_MESSAGE = "Cette unité n'est pas à portée de la cible"
NO_UNIT_MESSAGE = "Aucune unité sur cette case."
ALREADY_ATTACKED = "Cette unité a déjà attaqué durant cette phase de combat."
ALREADY_TARGETED = "Cette unité a déjà été attaquée durant cette phase de combat."


def read_prefixed_hexagon(prefix: str, source: Mapping[str, object]) -> Hex:
    """Reads a `Hex` from `{prefix}q`, `{prefix}r`, `{prefix}s` - for two hexagons in one URL.

    Args:
        prefix: `"a"` for the attacker, `"c"` for the target.
        source: The query string.

    Returns:
        The hexagon; 400 or 404 as `read_a_hexagon` decides.
    """
    return read_a_hexagon({name: source.get(f"{prefix}{name}") for name in ("q", "r", "s")})


@blueprint.route("/combat/range")
def check_range() -> ResponseReturnValue:
    """Says whether the unit at `a...` can engage the target at `c...`.

    An attacker out of range, or that has already had its turn this phase, is refused and the
    refusal goes to the log.

    Returns:
        `in_range`, `available` and a French `message` when refused.
    """
    target = read_prefixed_hexagon("c", request.args)
    attacker = read_prefixed_hexagon("a", request.args)
    attacking_piece = BOARD.piece_on(attacker)
    if attacking_piece is None:
        return {"in_range": False, "available": False, "message": NO_UNIT_MESSAGE}
    within_range = combat.in_range(attacker, attacking_piece, target)
    available = REGISTER.can_attack(attacker.key)
    if not available:
        message = ALREADY_ATTACKED
    elif not within_range:
        message = OUT_OF_RANGE_MESSAGE
    else:
        message = None
    if message:
        LOG.info(message)
    return {"in_range": within_range, "available": available, "message": message}


@blueprint.route("/combat/target")
def check_target() -> ResponseReturnValue:
    """Says whether the unit at `c...` can still be taken as a target this combat phase.

    Returns:
        `available` and a French `message` when refused.
    """
    target = read_prefixed_hexagon("c", request.args)
    if BOARD.piece_on(target) is None:
        return {"available": False, "message": NO_UNIT_MESSAGE}
    available = REGISTER.can_be_targeted(target.key)
    message = None if available else ALREADY_TARGETED
    if message:
        LOG.info(message)
    return {"available": available, "message": message}


def sort_the_attackers(squares: list[object], target: Hex) -> tuple[list[Hex], list[str]]:
    """Keeps the attackers the rules allow against a target, and explains each refusal.

    Args:
        squares: The attackers' coordinates, as the browser sent them.
        target: The target's square.

    Returns:
        The valid attackers, and one French message per refused one.
    """
    valid, messages = [], []
    for square in squares:
        attacker = read_a_hexagon(square if isinstance(square, Mapping) else {})
        attacking_piece = BOARD.piece_on(attacker)
        if attacking_piece is None or attacking_piece.side != TURN.active_side:
            messages.append("Cette unité ne peut pas attaquer cette cible.")
        elif not REGISTER.can_attack(attacker.key):
            messages.append(ALREADY_ATTACKED)
        elif not combat.in_range(attacker, attacking_piece, target):
            messages.append(OUT_OF_RANGE_MESSAGE)
        else:
            valid.append(attacker)
    return valid, messages


@blueprint.route("/combat", methods=["POST"])
@active_side_required
def fight() -> ResponseReturnValue:
    """Resolves a combat: one opposing target, one or more attackers of the active side.

    Body `{"target": {q, r, s}, "attackers": [{q, r, s}, ...]}`. The server revalidates
    everything, discards attackers out of range or having already attacked, rolls the die, applies
    the result to the board and logs the outcome in French. The combat is entered in the phase
    register **whatever its outcome**.

    Returns:
        `resolved`, and on success the outcome, the eliminated squares, the roll, the die, the
        ratio and the units now unavailable.
    """
    demand = request.get_json(silent=True) or {}
    if TURN.phase_type != COMBAT:
        return {"resolved": False, "message": "Ce n'est pas la phase de combat."}

    target = read_a_hexagon(demand.get("target") or {})
    if target.key not in BOARD.opponents_of(TURN.active_side):
        return {"resolved": False, "message": "La cible doit être une unité adverse."}
    if not REGISTER.can_be_targeted(target.key):
        LOG.info(ALREADY_TARGETED)
        return {"resolved": False, "message": ALREADY_TARGETED}

    valid, messages = sort_the_attackers(demand.get("attackers") or [], target)
    for message in messages:
        LOG.info(message)
    if not valid:
        return {"resolved": False, "message": "Aucun attaquant valide.", "messages": messages}

    # Read from the module at call time: the tests fix the die there, for the AI as for this route.
    roll = current_game.roll_the_die()
    result = combat.fight(BOARD, target, valid, roll)
    REGISTER.record([hexagon.key for hexagon in valid], target.key)
    message = combat_message(result)
    # The computation first, the outcome next: the browser's column reads bottom-up, so the outcome
    # ends up at the top, its breakdown just below.
    if result.breakdown is not None:
        LOG.info(describe_the_ratio(result))
    LOG.info(message)
    save_the_game()
    return {
        "resolved": True,
        "outcome": result.outcome,
        "message": message,
        "eliminated": [hexagon.to_dict() for hexagon in result.eliminated],
        "roll": roll,
        "die": result.die,
        "ratio": list(result.ratio) if result.ratio else None,
        "unavailable": unavailable_units(),
    }
