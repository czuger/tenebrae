"""The board: the map with the pieces laid out on it, starting over, and where the game stands.

"/" serves the scenario's set-up as the current game holds it, resumed from base where a save
exists, and passes it to the template as JSON: it is the JavaScript that converts cube coordinates
into pixels and places the pieces on the map. `/game/new` starts over - against the AI if asked -,
and `/game/state` is the fallback of the stream for a browser that lost it.
"""

import json
from typing import Optional

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue

from tenebrae.application import current_game
from tenebrae.application.current_game import (SCENARIO, SCENARIO_NUMBER, SEATS, current_phase,
                                               lay_out_the_scenario, let_the_ai_play,
                                               placed_units, restore_the_game,
                                               snapshot_the_game)
from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN, PIECE_SIZE
from tenebrae.application.logs.battle_log import LOG, log_lines
from tenebrae.application.persistence import game_repository, view_repository
from tenebrae.application.players import current_player, logged_in_player, the_table
from tenebrae.application.repositories.view import ViewRecord
from tenebrae.application.routes.authorization import seat_required
from tenebrae.engine import ai

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

    The game is resumed where it was left. Failing a save - first visit, empty base, null
    repository -, or if the save is that of another scenario, the set-up is rebuilt and a new game
    opened.

    Returns:
        The rendered `map.html`.
    """
    state = game_repository().load()
    if state is None or state["scenario"] != SCENARIO_NUMBER:
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


def sides_to_entrust_to_the_ai() -> list[str]:
    """Lists the sides the requester does not hold, to give to the AI.

    Returns:
        The opposing sides.

    Raises:
        ValueError: With a French message, if there is no such side or if one is held by a human.
    """
    player = logged_in_player()["discord_id"]
    opposing_sides = [side for side in SCENARIO.sides if not SEATS.holds(player, side)]
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

    With a body `{"against_ai": true}`, the side the requester does not hold is entrusted to the AI
    - if it is free, or already the AI's. If the scenario opens on the AI's side, it plays its
    first turn straight away. The table is set and the line written **before** the set-up, which
    is what pushes the game to the open streams.

    Returns:
        The pieces, the phase and the table; 409 if no side can go to the AI.
    """
    against_ai = bool((request.get_json(silent=True) or {}).get("against_ai"))
    if against_ai:
        try:
            opposing_sides = sides_to_entrust_to_the_ai()
        except ValueError as refusal:
            return {"message": str(refusal)} | the_table(), 409
        for side in opposing_sides:
            SEATS.seat(side, ai.AI_PLAYER)
        LOG.info("New game against the AI: scenario %s, the AI holds %s",
                 SCENARIO_NUMBER, ", ".join(opposing_sides))
    else:
        LOG.info("New game: scenario %s", SCENARIO_NUMBER)
    lay_out_the_scenario()
    game_repository().new_game(snapshot_the_game())
    let_the_ai_play()
    return {"pieces": placed_units(), "phase": current_phase()} | the_table()


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
