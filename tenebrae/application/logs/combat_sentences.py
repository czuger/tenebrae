"""The French sentences a combat writes to the log - and that the browser repeats.

A resolved combat writes two lines - the ratio computation, then its outcome, which names the
result Table I gave - and one more per unit that had to fall back. The engine builds no sentence
(see `tenebrae/engine/README.md` § "The breakdown of the computation"): it returns numbers, squares
and a terrain name, and this module puts them into French - what the player reads, like everything
on screen.
"""

from tenebrae.engine.combat import CombatResult
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.retreat import RetreatOutcome

# The five outcomes of Table I, each in its sentence: the two retreats name themselves like the
# three eliminations, a result the table gave never being read as no result.
COMBAT_MESSAGES = {
    "DE": "Combat résolu : Défenseur Éliminé",
    "AE": "Combat résolu : Attaquant Éliminé",
    "EX": "Combat résolu : Échange — la cible est éliminée, avec les attaquants qui ne tirent pas",
    "DR": "Combat résolu : Défenseur Recule",
    "AR": "Combat résolu : Attaquant Recule",
}

# What a retreat adds when it moved nobody: the exemption that held. Without it the outcome would
# be followed by no fall-back line at all, and would read as a combat that did nothing.
NO_RETREAT_NOTES = {
    "DR": " — mais un défenseur en fort ou en château ne recule pas",
    "AR": " — mais une unité qui tire ne recule pas",
}

# Kept for the combat that could not be resolved: an absent target, an illegible strength.
NO_EFFECT_MESSAGE = "Combat résolu : sans effet"


def describe_the_ratio(result: CombatResult) -> str:
    """Puts the strength ratio computation into one French sentence, for the log.

    What the ratio alone does not say: what the attackers total, what the defender opposes once
    its terrain is counted, and the die as that terrain modified it. Each term is only spelled out
    when there is a detail to spell out; the terrain is always named.

        Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4

    Args:
        result: A resolved combat, whose `breakdown` is not `None`.

    Returns:
        The sentence.

    Raises:
        ValueError: If the combat was not resolved: there is no computation to describe.
    """
    breakdown = result.breakdown
    if breakdown is None:
        raise ValueError("this combat was not resolved: no ratio to describe")
    attack = " + ".join(str(strength) for strength in breakdown.strengths)
    if len(breakdown.strengths) > 1:
        attack += f" = {breakdown.attacking_strength}"
    defence = str(breakdown.target_strength)
    if breakdown.multiplier != 1:
        defence += f" × {breakdown.multiplier} = {breakdown.defending_strength}"
    die = str(breakdown.roll)
    if breakdown.die_bonus:
        die += f" + {breakdown.die_bonus} = {breakdown.roll + breakdown.die_bonus}"
        # Table I has only six rows: saying the die was brought back avoids an addition that would
        # look wrong.
        if breakdown.roll + breakdown.die_bonus != breakdown.die:
            die += f", ramené à {breakdown.die}"
    ratio = "-".join(map(str, breakdown.ratio))
    return (f"Rapport {ratio} : attaque {attack} contre défense {defence} "
            f"({breakdown.terrain}) — dé {die}")


def combat_message(result: CombatResult) -> str:
    """Puts a combat's outcome into the French sentence the log and the browser show.

    A retreat that moved nobody says why: the two exemptions - a defender in a fort or a castle, an
    attacker that fires - leave the board as it was, and no fall-back line follows the outcome.

    Args:
        result: The combat, resolved or not.

    Returns:
        The sentence of `COMBAT_MESSAGES`, the exemption noted where one held, and
        `NO_EFFECT_MESSAGE` for a combat that could not be resolved.
    """
    if result.outcome is None:
        return NO_EFFECT_MESSAGE
    message = COMBAT_MESSAGES.get(result.outcome, NO_EFFECT_MESSAGE)
    if result.outcome in NO_RETREAT_NOTES and not gave_ground(result):
        return message + NO_RETREAT_NOTES[result.outcome]
    return message


def gave_ground(result: CombatResult) -> bool:
    """Says whether a combat moved or felled anybody through a retreat.

    Args:
        result: The combat.

    Returns:
        True if at least one unit fell back, or fell for want of anywhere to fall back to.
    """
    return any(retreat.fell_back or retreat.eliminated is not None
               for retreat in result.retreats)


def retreat_sentence(retreat: RetreatOutcome) -> str:
    """Puts one unit's fall-back into a French sentence.

        Recul : 1,26,-27 → 1,27,-28
        Recul : 1,26,-27 → 1,27,-28 (2 unités amies poussées)
        Recul impossible : unité éliminée en 1,26,-27

    Args:
        retreat: What the unit did, as `tenebrae/engine/retreat.py` reports it.

    Returns:
        The sentence.

    Raises:
        ValueError: If the outcome says neither a move nor an elimination: there is nothing to
            tell.
    """
    if retreat.eliminated is not None:
        return f"Recul impossible : unité éliminée en {retreat.eliminated.key}"
    origin, destination = _the_fall_back(retreat)
    sentence = f"Recul : {origin.key} → {destination.key}"
    if retreat.pushed == 1:
        return f"{sentence} (1 unité amie poussée)"
    if retreat.pushed > 1:
        return f"{sentence} ({retreat.pushed} unités amies poussées)"
    return sentence


def _the_fall_back(retreat: RetreatOutcome) -> tuple[Hex, Hex]:
    """Reads the retreating unit's own move off an outcome that has one.

    Args:
        retreat: The outcome.

    Returns:
        Its origin and its destination.

    Raises:
        ValueError: If the unit neither moved nor fell.
    """
    if not retreat.moves:
        raise ValueError("this outcome says nothing: no fall-back to describe")
    return retreat.moves[0]


def retreat_messages(result: CombatResult) -> list[str]:
    """Puts every fall-back of a combat into French, in the order they happened.

    Args:
        result: The combat, resolved or not.

    Returns:
        One sentence per unit that had to give ground; empty for a combat that moved nobody.
    """
    return [retreat_sentence(retreat) for retreat in result.retreats
            if retreat.fell_back or retreat.eliminated is not None]
