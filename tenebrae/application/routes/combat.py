"""Combat: whether a unit can engage a target, and resolving the attack.

The server revalidates everything the browser proposes - the phase, the target's side, each
attacker's range and availability -, rolls the die, applies the result to the board and logs the
outcome in French (`logs/combat_sentences.py`). A unit fights only once per phase: the combat
register (`tenebrae/engine/combat_register.py`) is what refuses a second turn.

A retreat moves units, so the register is filled with the squares they hold **after** the combat
(`CombatResult.square_after`): a unit that has fought and then fallen back must stay marked, and it
is no longer where it was when it was marked.
"""

from collections.abc import Mapping

from flask import Blueprint, request
from flask.typing import ResponseReturnValue

from tenebrae.application import current_game
from tenebrae.application.current_game import (BOARD, CASUALTIES, REGISTER, TURN,
                                               close_the_game_if_a_side_is_wiped_out,
                                               save_the_game, unavailable_units)
from tenebrae.application.logs.battle_log import LOG
from tenebrae.application.logs.combat_sentences import (advance_sentence, combat_message,
                                                        describe_the_ratio, retreat_messages)
from tenebrae.application.routes.authorization import (active_side_required,
                                                       while_the_game_lasts)
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


def read_a_key(key: str) -> Hex:
    """Reads a hexagon written as the map's own key, `"q,r,s"`.

    The form a repeated parameter takes - `a=1,26,-27&a=2,25,-27` - where three parameters per
    attacker would be unreadable.

    Args:
        key: The key, as the query string carries it.

    Returns:
        The hexagon; 400 if unreadable, 404 if off the map, as `read_a_hexagon` decides.
    """
    coordinates = key.split(",")
    return read_a_hexagon(dict(zip(("q", "r", "s"), coordinates)) if len(coordinates) == 3 else {})


@blueprint.route("/combat/ratio")
def weigh_the_forces() -> ResponseReturnValue:
    """Weighs the combat being composed: the ratio, and the points on either side.

    Read while the player is still designating attackers - the toolbar shows it as
    `Ratio : 3/1 (36/12)` - so it must say what the resolution would read and not something close
    to it: the attackers go through the same filter `POST /combat` puts them through, and the
    weighing is the engine's `combat.weigh`, the very one `fight` uses.

    The target is `cq/cr/cs`, as for `/combat/range`; the attackers are one `a=q,r,s` per unit,
    the key a hexagon is known by on the map.

    **Nothing is logged here.** A refused click has its line where it is refused; a weighing is
    recomputed at every attacker taken or withdrawn, and would fill the player's column.

    Returns:
        `ratio` (a pair, attacker first), `attack` and `defence` in points, and `outcomes` - what
        each of the six faces of the die would give, the defender's terrain counted. `ratio` is
        `null` where there is nothing to weigh - no valid attacker, an absent target, an illegible
        strength.
    """
    target = read_prefixed_hexagon("c", request.args)
    attackers = [read_a_key(key) for key in request.args.getlist("a")]
    valid, _ = keep_the_valid_attackers(attackers, target)
    weighed = combat.weigh(BOARD, target, valid)
    if weighed is None:
        return {"ratio": None, "attack": 0, "defence": 0, "outcomes": []}
    return {"ratio": list(weighed.ratio),
            "attack": weighed.attacking_strength,
            "defence": weighed.defending_strength,
            "outcomes": list(weighed.outcomes)}


def sort_the_attackers(squares: list[object], target: Hex) -> tuple[list[Hex], list[str]]:
    """Reads the attackers a request names, and keeps those the rules allow against a target.

    Args:
        squares: The attackers' coordinates, as the browser sent them.
        target: The target's square.

    Returns:
        The valid attackers, and one French message per refused one.
    """
    return keep_the_valid_attackers(
        [read_a_hexagon(square if isinstance(square, Mapping) else {}) for square in squares],
        target)


def keep_the_valid_attackers(attackers: list[Hex], target: Hex) -> tuple[list[Hex], list[str]]:
    """Keeps the attackers the rules allow against a target, and explains each refusal.

    The rules, and no reading of the request: the resolution and the weighing shown in the toolbar
    both come here, from a JSON body for the one and from a query string for the other.

    Args:
        attackers: The attackers' squares.
        target: The target's square.

    Returns:
        The valid attackers, and one French message per refused one.
    """
    valid, messages = [], []
    for attacker in attackers:
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
@while_the_game_lasts
def fight() -> ResponseReturnValue:
    """Resolves a combat: one opposing target, one or more attackers of the active side.

    Body `{"target": {q, r, s}, "attackers": [{q, r, s}, ...], "advance": bool}`. The server
    revalidates everything, discards attackers out of range or having already attacked, rolls the
    die, applies the result to the board and logs the outcome in French. The combat is entered in
    the phase register **whatever its outcome**.

    `advance` is the "Attaquer et avancer" button: the booklet has the decision to occupy the
    square the defender leaves "announced immediately after the combat", and the player announces
    it by the button they press. It is played by the engine, after everything else.

    Returns:
        `resolved`, and on success the outcome, the eliminated squares, the fall-backs, the
        advance, the roll, the die, the ratio and the units now unavailable.
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
    result = combat.fight(BOARD, target, valid, roll, CASUALTIES,
                          advance=bool(demand.get("advance")))
    REGISTER.record([result.square_after(hexagon).key for hexagon in valid],
                    result.square_after(target).key)
    message = combat_message(result)
    # The outcome is logged **last** and therefore read **first**: the browser's column shows the
    # most recent line at the top. Under it come the fall-backs it caused, and under those the
    # computation that gave it - the headline, then its explanation.
    if result.breakdown is not None:
        LOG.info(describe_the_ratio(result))
    for sentence in retreat_messages(result):
        LOG.info(sentence)
    if result.advance is not None:
        LOG.info(advance_sentence(result.advance))
    LOG.info(message)
    # The combat may have taken the last unit of a side: the game then closes here, before the
    # move is marked, so that the browsers receive the sentence with the position it speaks of.
    close_the_game_if_a_side_is_wiped_out()
    save_the_game()
    return {
        "resolved": True,
        "outcome": result.outcome,
        "message": message,
        "eliminated": [hexagon.to_dict() for hexagon in result.eliminated],
        # The angle travels with the square: the unit has been picked up, and it is the server that
        # drew the fresh angle it lies down at - as for a move (`routes/movement.py`).
        "retreats": [{"from": origin.to_dict(), "to": destination.to_dict(),
                      "tilt": BOARD.tilt_on(destination)}
                     for origin, destination in result.moves],
        # The angle travels here too: the counter has been picked up like any other.
        "advance": None if result.advance is None else {
            "from": result.advance[0].to_dict(),
            "to": result.advance[1].to_dict(),
            "tilt": BOARD.tilt_on(result.advance[1])},
        "roll": roll,
        "die": result.die,
        "ratio": list(result.ratio) if result.ratio else None,
        "unavailable": unavailable_units(),
    }
