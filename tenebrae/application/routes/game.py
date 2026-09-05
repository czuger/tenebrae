"""The board: one saved game shown on the map, starting a new one, and where the game stands.

`/game/<id>` serves that game - its pieces, its phase, its table - and passes it to the template as
JSON: it is the JavaScript that converts cube coordinates into pixels and places the pieces on the
map. `/game` is the entry that needs no identifier: it sends to the game played most recently, and
opens one where there is none to resume. `/game/new` opens one, `/game/scenarios` lists the set-ups
it accepts, and `/game/state` is the fallback of the stream for a browser that lost it.

**Opening a game takes the server onto it.** There is one board, one turn and one table per
process; several games live in base and each has its own address, but the process plays one of them
at a time. `GET /game/<id>` is therefore not a reading: it moves the whole table, and the tabs
watching the game it left are told so (see the application README, "One game per process, several
URLs").

A scenario is offered only if its file does not carry `"enabled": false` (see
`tenebrae/scenarios/README.md`). The list is read from disk at every request and `/game/new`
checks the number it is given against that same reading: a scenario disabled a moment ago is
refused, whatever a browser opened before still shows in its chooser.
"""

import json
from collections.abc import Mapping
from typing import Optional

from flask import Blueprint, redirect, render_template, request, url_for
from flask.typing import ResponseReturnValue

from tenebrae.application import current_game
from tenebrae.application.current_game import (SEATS, current_phase, let_the_ai_play,
                                               open_a_new_game, placed_units, restore_the_game,
                                               resume_the_scenario, switch_to_the_scenario)
from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN, PIECE_SIZE
from tenebrae.application.logs.battle_log import LOG, log_lines
from tenebrae.application.persistence import game_repository, view_repository
from tenebrae.application.players import current_player, logged_in_player, the_table
from tenebrae.application.repositories.view import ViewRecord
from tenebrae.application.routes.authorization import login_required
from tenebrae.engine import ai
from tenebrae.engine.scenario import Scenario, available_scenarios, enabled_scenarios

blueprint = Blueprint("game", __name__)


def player_view() -> Optional[ViewRecord]:
    """Reads where the session's player had got to on the map.

    Returns:
        The view, or `None` for an anonymous visitor as for a player who has adjusted nothing yet:
        the page then opens fitted to the window.
    """
    player = current_player()
    return view_repository().by_discord_id(player["discord_id"]) if player else None


@blueprint.route("/game")
def latest_board() -> ResponseReturnValue:
    """The board without an identifier: the game played most recently.

    Redirects rather than renders a second copy of the map: a game has one address, and a page
    served at two of them is a game two tabs cannot compare. The query string travels with the
    redirect, so `/game?debug=1` arrives on the board with its log turned on.

    Returns:
        A redirect to `/game/<id>`.
    """
    target = url_for("game.board", identifier=the_game_to_resume())
    query = request.query_string.decode()
    return redirect(f"{target}?{query}" if query else target)


def the_game_to_resume() -> str:
    """The game to open when none is named: the last one played, or a fresh one.

    The two cases the map's own route handled as long as it was "/": an empty base, and a saved
    game whose scenario has no file any more. Either way the set-up being played is laid out and a
    game opened on it. The table is not touched there - there is no other game whose seats could be
    inherited.

    Returns:
        The identifier of a game that can be opened.
    """
    found = game_repository().most_recent()
    if found is not None and found[1]["scenario"] in available_scenarios():
        return found[0]
    return open_a_new_game()


@blueprint.route("/game/<identifier>")
def board(identifier: str) -> ResponseReturnValue:
    """Serves one saved game: its map, its pieces, its phase and its table.

    **The process takes that game up**: its board, its turn and its seats replace whatever it was
    holding, and it is into its document that the next move is saved. The server puts itself back
    on the scenario it was played on, `enabled` or not - disabling a scenario stops new games being
    opened on it, not the one under way.

    A game other than the one in play is a move for everyone watching, and `restore_the_game`
    publishes it: the tabs on the game just left see the identifier change and say so rather than
    go on showing a board that is no longer theirs. Opening the game already in play publishes
    nothing.

    Args:
        identifier: The game to open, as the list of games gives it out.

    Returns:
        The rendered `map.html`; 404 with a French message for an identifier no game carries - one
        that is not an identifier at all included - and for a game whose scenario has left the disk.
    """
    state = game_repository().load(identifier)
    if state is None:
        return {"message": "Cette partie n'existe pas."}, 404
    if not resume_the_scenario(state["scenario"]):
        return {"message": "Le scénario de cette partie n'est plus sur le disque."}, 404
    restore_the_game(identifier, state)
    return render_template(
        "map.html",
        game=identifier,
        pieces=json.dumps(placed_units(), ensure_ascii=False),
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

    `armies` is what the new-game form fills its side chooser from: a set-up's sides are its own,
    and one picks the side one takes before the game exists to sit down at.

    Returns:
        One entry per enabled scenario, in numeric order: `number`, `name`, `max_turns`, the
        number of `units` placed, and `armies` - side -> readable army name, in player order.
    """
    return [{"number": number, "name": found.name, "max_turns": found.max_turns,
             "units": len(found),
             "armies": {army["camp"]: army["armee"] for army in found.armies}}
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


def the_opening_table(chosen: Scenario, demand: Mapping[str, object]) -> dict[str, str]:
    """The table a new game opens with: its creator seated, and the AI facing them if asked.

    Nothing is read from `SEATS`. Those seats belong to the game the process happens to be on, and
    a new game is a new document at which nobody sits yet: there is no side to take from anyone,
    and nothing left for the old refusals - "Aucun camp à confier à l'IA", "Ce camp est déjà tenu"
    - to refuse. The side is asked for instead, on the form that opens the game.

    Args:
        chosen: The scenario the game opens on; its sides, in the file's order.
        demand: The request body: the `side` the creator takes, and `against_ai`.

    Returns:
        Side -> Discord identifier, the AI's own for the sides it holds.

    Raises:
        ValueError: With a French message, for a side this scenario has not.
    """
    side = demand.get("side") or chosen.sides[0]
    if side not in chosen.sides:
        raise ValueError("Ce camp n'est pas celui de ce scénario.")
    table = {str(side): logged_in_player()["discord_id"]}
    if bool(demand.get("against_ai")):
        table.update({other: ai.AI_PLAYER for other in chosen.sides if other != side})
    return table


@blueprint.route("/game/new", methods=["POST"])
@login_required
def new_game() -> ResponseReturnValue:
    """Opens a game and answers with its address; the browser then goes to it.

    The body carries `{"scenario": N}` - one of those `/game/scenarios` offers, checked again here
    -, `{"side": "alliance"}` for the side its creator takes, and `{"against_ai": true}` to give
    the rest to the machine. If the scenario opens on the AI's side, it plays its first turn
    straight away.

    A **seat is no longer required**: a game is created before anyone is seated at it, and it is
    the creator's own side that seats them. The table opened is that game's alone - the seats of
    the game the process happened to be on are not carried over, or a new game would open with two
    strangers already at it.

    Nothing is changed until the whole body has been read: a request refused leaves the game where
    it was. The scenario is then switched, the table set and the line written **before** the
    set-up, which is what pushes the game to the open streams.

    Returns:
        `{"id": ..., "url": ...}`; 409 for a scenario that is not offered or a side that is not of
        it.
    """
    demand = request.get_json(silent=True) or {}
    try:
        chosen = chosen_scenario(demand)
        seating = the_opening_table(chosen, demand)
    except ValueError as refusal:
        return {"message": str(refusal)}, 409
    switch_to_the_scenario(chosen)
    SEATS.restore(seating)
    held_by_the_ai = [side for side, who in seating.items() if who == ai.AI_PLAYER]
    if held_by_the_ai:
        LOG.info("New game against the AI: scenario %s, the AI holds %s",
                 chosen.number, ", ".join(held_by_the_ai))
    else:
        LOG.info("New game: scenario %s", chosen.number)
    identifier = open_a_new_game()
    let_the_ai_play()
    return {"id": identifier, "url": url_for("game.board", identifier=identifier)}


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

    **`game` is in both answers**, the unchanged one included. The version counts the moves of the
    process, not of one game: a tab whose game has been swapped out from under it would otherwise
    be told "nothing has moved" while the board it is watching belongs to someone else.

    Returns:
        `game`, `version` and `changed`; the pieces, phase, table and log too when something moved.
    """
    known = request.args.get("version", type=int)
    if known == current_game.VERSION:
        return {"game": current_game.GAME_ID, "version": current_game.VERSION, "changed": False}
    return {"game": current_game.GAME_ID, "version": current_game.VERSION, "changed": True,
            "pieces": placed_units(), "phase": current_phase(), "table": the_table(),
            "log": log_lines()}
