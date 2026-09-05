"""The landing page: the games already saved, and the means to open one more.

"/" no longer serves the map. It lists what `parties` holds - one card per game, most recently
played first - and carries the form that opens a new one. The map is at `/game/<id>`, one address
per game, and `/game` sends to the last one played.

**It touches nothing.** As long as "/" was the map it laid a scenario out on an empty base, which
made every arrival - an anonymous visitor's included - open a game. A list that created a game each
time it was read would fill the base with empty ones, so the creating stays where it belongs: on
`/game`, which is asked for a game to play, and on `POST /game/new`, which is asked for a new one.

The page is **public**, like the map: one watches a game without an account, and the form is
replaced by the way in to Discord for whoever has none.

The scenarios are read here from `available_scenarios()` and not from `enabled_scenarios()`: a game
under way on a set-up since disabled must still be named on its card. What a *new* game may be
opened on is another list, and that one is `offered_scenarios()`.
"""

import json
from collections.abc import Iterable, Mapping
from typing import Optional

from flask import Blueprint, render_template
from flask.typing import ResponseReturnValue

from tenebrae.application.logs.combat_sentences import label_the_end
from tenebrae.application.persistence import game_repository
from tenebrae.application.players import current_player, nickname_of, the_visitor
from tenebrae.application.routes.game import offered_scenarios
from tenebrae.engine.phase import LABELS
from tenebrae.engine.repositories.game import GameSummary
from tenebrae.engine.scenario import Scenario, available_scenarios, read

blueprint = Blueprint("home", __name__)


@blueprint.route("/")
def games() -> ResponseReturnValue:
    """Serves the list of saved games and the form that opens a new one.

    Returns:
        The rendered `home.html`.
    """
    return render_template(
        "home.html",
        games=json.dumps(saved_games(), ensure_ascii=False),
        scenarios=json.dumps(offered_scenarios(), ensure_ascii=False),
        visitor=json.dumps(the_visitor(), ensure_ascii=False),
    )


def saved_games() -> list[dict[str, object]]:
    """Describes every saved game as a card shows it, most recently played first.

    Returns:
        One entry per game in base; empty on an empty base.
    """
    summaries = game_repository().games()
    scenarios = scenarios_of(summary["scenario"] for summary in summaries)
    player = current_player()
    me = player["discord_id"] if player else None
    return [describe(summary, scenarios.get(summary["scenario"]), me) for summary in summaries]


def scenarios_of(numbers: Iterable[int]) -> dict[int, Scenario]:
    """Reads the scenario files the games listed were played on, each one once.

    `available_scenarios()` and not `enabled_scenarios()`: a game already under way on a set-up
    withdrawn since must still be able to say what it is being played on.

    Args:
        numbers: The scenario numbers the summaries carry, repeats included.

    Returns:
        Number -> scenario, a number whose file has gone simply absent.
    """
    files = available_scenarios()
    return {number: read(files[number]) for number in set(numbers) if number in files}


def describe(summary: GameSummary, scenario: Optional[Scenario],
             me: Optional[str]) -> dict[str, object]:
    """Turns one summary into the card the page shows, in French.

    Nothing composes a sentence of its own here: the phase reads through `LABELS`, the same table
    `Turn.label` uses, and the end through `label_the_end`, the very sentence the board's toolbar
    shows. One truth per sentence, wherever it is read.

    Args:
        summary: The game as the repository summarises it.
        scenario: Its set-up, or `None` if the file has gone - the card is then not openable.
        me: The visitor's Discord identifier, or `None` for an anonymous one.

    Returns:
        What `home.js` lays out: identity, where the game stands, its two sides, and whether it is
        the visitor's.
    """
    armies = {army["camp"]: army["armee"] for army in scenario.armies} if scenario else {}
    sides = seats_of(summary, armies, me)
    return {
        "id": summary["identifier"],
        "scenario": summary["scenario"],
        "scenario_name": scenario.name if scenario else None,
        "turn": summary["turn_number"],
        "phase": LABELS[summary["phase_type"]],
        "army": armies.get(summary["active_side"], summary["active_side"]),
        "units": summary["units"],
        "over": summary["over"],
        "end": end_of(summary, armies),
        "sides": sides,
        "mine": any(side["mine"] for side in sides),
        "played_at": summary["updated_at"].isoformat(),
    }


def seats_of(summary: GameSummary, armies: Mapping[str, str],
             me: Optional[str]) -> list[dict[str, object]]:
    """One entry per side of the game: its army, who holds it, and whether that is the visitor.

    The sides come from the scenario when its file is there, and from the seats themselves when it
    is not: a card whose set-up has gone still says who was playing it.

    Args:
        summary: The game as the repository summarises it.
        armies: Side -> readable army name; empty for a vanished set-up.
        me: The visitor's Discord identifier, or `None`.

    Returns:
        The sides, in the set-up's order.
    """
    seats = summary["seats"]
    sides = list(armies) or sorted(seats)
    return [{"side": side, "army": armies.get(side, side),
             "occupant": nickname_of(seats.get(side)),
             "mine": me is not None and seats.get(side) == me}
            for side in sides]


def end_of(summary: GameSummary, armies: Mapping[str, str]) -> Optional[str]:
    """How a finished game ended, as the board's own toolbar says it.

    Args:
        summary: The game as the repository summarises it.
        armies: Side -> readable army name.

    Returns:
        The French sentence, or `None` for a game still being played.
    """
    if not summary["over"]:
        return None
    winner = summary["winner"]
    return label_the_end(armies.get(winner, winner) if winner is not None else None)
