"""The board: the map with the pieces laid out on it, starting over, and where the game stands.

"/" serves the scenario's set-up as the current game holds it, resumed from base where a save
exists, and passes it to the template as JSON: it is the JavaScript that converts cube coordinates
into pixels and places the pieces on the map. `/game/new` starts over - against the AI if asked,
on another scenario if asked -, `/game/scenarios` lists the set-ups it accepts, and `/game/state`
is the fallback of the stream for a browser that lost it.

A scenario is offered only if its file does not carry `"enabled": false` (see
`tenebrae/scenarios/README.md`). The list is read from disk at every request and `/game/new`
checks the number it is given against that same reading: a scenario disabled a moment ago is
refused, whatever a browser opened before still shows in its chooser.
"""

import json
from collections.abc import Mapping
from typing import Optional

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue

from tenebrae.application import current_game
from tenebrae.application.current_game import (SEATS, current_phase, lay_out_the_scenario,
                                               let_the_ai_play, placed_units,
                                               restore_the_game, resume_the_scenario,
                                               snapshot_the_game, switch_to_the_scenario)
from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN, PIECE_SIZE
from tenebrae.application.logs.battle_log import LOG, log_lines
from tenebrae.application.persistence import game_repository, view_repository
from tenebrae.application.players import current_player, logged_in_player, the_table
from tenebrae.application.repositories.view import ViewRecord
from tenebrae.application.routes.authorization import seat_required
from tenebrae.engine import ai
from tenebrae.engine.scenario import Scenario, enabled_scenarios

blueprint = Blueprint("game", __name__)


def player_view() -> Optional[ViewRecord]:
    """Reads where the session's player had got to on the map.

    Returns:
        The view, or `None` for an anonymous visitor as for a player who has adjusted nothing yet:
        the page then opens fitted to the window.
    """
    player = current_player()
    return view_repository().by_discord_id(player["discord_id"]) if player else None


@blueprint.route("/")
def board() -> ResponseReturnValue:
    """Serves the map, its pieces and the current phase.

    The game is resumed where it was left, on the scenario it was played on - the server puts
    itself back on that set-up, `enabled` or not: disabling a scenario stops new games being
    opened on it, not the one under way. Failing a save - first visit, empty base -, or if the
    saved scenario has no file any more, the current set-up is rebuilt and a new game opened.

    Returns:
        The rendered `map.html`.
    """
    state = game_repository().load()
    if state is None or not resume_the_scenario(state["scenario"]):
        placed = lay_out_the_scenario()
        game_repository().new_game(snapshot_the_game())
    else:
        restore_the_game(state)
        placed = placed_units()
    return render_template(
        "map.html",
        pieces=json.dumps(placed, ensure_ascii=False),
        grid=json.dumps({"origin": GRID_ORIGIN, "matrix": GRID_MATRIX,
                         "piece_size": PIECE_SIZE}),
        phase=json.dumps(current_phase(), ensure_ascii=False),
        table=json.dumps(the_table(), ensure_ascii=False),
        log=json.dumps(log_lines(), ensure_ascii=False),
        view=json.dumps(player_view()),
        version=current_game.VERSION,
    )


def offered_scenarios() -> list[dict[str, object]]:
    """Lists the set-ups a new game can be opened on, read from disk at each call.

    Returns:
        One entry per enabled scenario, in numeric order: `number`, `name`, `max_turns` and the
        number of `units` placed.
    """
    return [{"number": number, "name": found.name, "max_turns": found.max_turns,
             "units": len(found)}
            for number, found in enabled_scenarios().items()]


def chosen_scenario(demand: Mapping[str, object]) -> Scenario:
    """Reads the scenario a new game is asked to be opened on.

    The number is not trusted: it is checked against the files as they stand now, and a scenario
    withdrawn since the chooser was filled is refused like one that never existed. An absent or
    `null` number keeps the set-up being played.

    Args:
        demand: The request body.

    Returns:
        The scenario to lay out.

    Raises:
        ValueError: With a French message, for a number that is not one, or that no enabled
            scenario carries.
    """
    number = demand.get("scenario")
    if number is None:
        return current_game.SCENARIO
    if isinstance(number, bool) or not isinstance(number, int):
        raise ValueError("Le numéro de scénario doit être un entier.")
    offered = enabled_scenarios()
    if number not in offered:
        raise ValueError(f"Le scénario n° {number} n'est pas proposé.")
    return offered[number]


def sides_to_entrust_to_the_ai(chosen: Scenario) -> list[str]:
    """Lists the sides the requester does not hold in a scenario, to give to the AI.

    Args:
        chosen: The scenario the new game opens on - its sides, not those of the game just left.

    Returns:
        The opposing sides.

    Raises:
        ValueError: With a French message, if there is no such side or if one is held by a human.
    """
    player = logged_in_player()["discord_id"]
    opposing_sides = [side for side in chosen.sides if not SEATS.holds(player, side)]
    if not opposing_sides:
        raise ValueError("Aucun camp à confier à l'IA.")
    for side in opposing_sides:
        if SEATS.occupant(side) not in (None, ai.AI_PLAYER):
            raise ValueError("Ce camp est déjà tenu.")
    return opposing_sides


@blueprint.route("/game/new", methods=["POST"])
@seat_required
def new_game() -> ResponseReturnValue:
    """Starts over: the scenario's set-up, and a fresh game in base.

    The body carries `{"scenario": N}` for a set-up other than the one being played - one of those
    `/game/scenarios` offers, checked again here - and `{"against_ai": true}` to entrust the side
    the requester does not hold to the AI, if it is free or already the AI's. If the scenario
    opens on the AI's side, it plays its first turn straight away.

    Nothing is changed until both have been read: a request refused leaves the game where it was.
    The scenario is then switched, the table set and the line written **before** the set-up, which
    is what pushes the game to the open streams.

    Returns:
        The pieces, the phase and the table; 409 for a scenario that is not offered, or if no side
        can go to the AI.
    """
    demand = request.get_json(silent=True) or {}
    try:
        chosen = chosen_scenario(demand)
        opposing_sides = (sides_to_entrust_to_the_ai(chosen)
                          if bool(demand.get("against_ai")) else [])
    except ValueError as refusal:
        return {"message": str(refusal)} | the_table(), 409
    switch_to_the_scenario(chosen)
    if opposing_sides:
        for side in opposing_sides:
            SEATS.seat(side, ai.AI_PLAYER)
        LOG.info("New game against the AI: scenario %s, the AI holds %s",
                 chosen.number, ", ".join(opposing_sides))
    else:
        LOG.info("New game: scenario %s", chosen.number)
    lay_out_the_scenario()
    game_repository().new_game(snapshot_the_game())
    let_the_ai_play()
    return {"pieces": placed_units(), "phase": current_phase()} | the_table()


@blueprint.route("/game/scenarios")
def scenarios_on_offer() -> ResponseReturnValue:
    """Lists the set-ups a new game can be opened on, and the one being played.

    Read from the files at every request rather than kept, so that a scenario disabled by hand
    leaves the chooser as soon as it is asked for again. Public, like the map: the chooser is
    filled when the table dialog opens, whoever opens it.

    Returns:
        `scenarios` and the `current` number.
    """
    return {"scenarios": offered_scenarios(), "current": current_game.SCENARIO_NUMBER}


@blueprint.route("/game/state")
def game_state() -> ResponseReturnValue:
    """Tells where the game stands - the SSE stream's **fallback**.

    A browser whose `EventSource` fails five times in a row falls back on it (see `followTheGame`
    in `map.js`). With `?version=N`, only the number comes back as long as nothing has moved.
    Public, like the map.

    Returns:
        `version` and `changed`; the pieces, phase, table and log too when something moved.
    """
    known = request.args.get("version", type=int)
    if known == current_game.VERSION:
        return {"version": current_game.VERSION, "changed": False}
    return {"version": current_game.VERSION, "changed": True, "pieces": placed_units(),
            "phase": current_phase(), "table": the_table(),
            "log": log_lines()}
