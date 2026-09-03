"""Composing a scenario - `/admin/scenarios`, reserved to the accounts in `ADMIN_DISCORD_IDS`.

The page lays the box's pieces beside the map: a piece taken from that palette is placed with a
click, and the set-up is saved as a **new file** in `tenebrae/scenarios/`, in the very format
`tenebrae.engine.scenario` reads (see `tenebrae/scenarios/README.md`). The route checks the
request - every square on the map and fit to be occupied, every piece one the box shows -, the
engine composes the file's values from the placement, and the route writes them. Each save is a
new scenario, with the next free number: nothing here rewrites a file.
"""

import datetime
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from flask import Blueprint, render_template, request
from flask.typing import ResponseReturnValue

from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN, PIECE_SIZE
from tenebrae.application.pieces import PIECE_CATALOGUE, PIECES_BY_KEY
from tenebrae.application.routes.authorization import administrator_required
from tenebrae.engine import scenario as engine_scenario
from tenebrae.engine.hexagon import MAP, UNINHABITABLE, Hex

blueprint = Blueprint("scenarios", __name__)

# The engine's refusal of a placement without any unit of a side, as the administrator reads it.
NO_SIDE = "Placez au moins une unité de l'Alliance ou des Ténèbres."


def palette() -> list[dict[str, object]]:
    """Lists the pieces the page offers: the display catalogue, `path` renamed to `image`.

    The same shape as the board's placed units, square apart: the JavaScript lays both with the
    same code.

    Returns:
        One entry per piece showing a single counter.
    """
    entries: list[dict[str, object]] = []
    for piece in PIECE_CATALOGUE:
        entry = dict(piece)
        entries.append({"image": entry.pop("path"), **entry})
    return entries


def forbidden_squares() -> list[str]:
    """Lists the squares no unit can occupy on the fixed map: lakes, rivers, the rift.

    Returns:
        Their "q,r,s" keys.
    """
    return [key for key, elements in MAP.items() if elements[0] in UNINHABITABLE]


@blueprint.route("/admin/scenarios")
@administrator_required
def compose_a_scenario() -> ResponseReturnValue:
    """Serves the map with the palette of pieces beside it.

    The **fixed** map goes to the browser - the one the game is played on -, so that the page
    refuses the same squares as the engine.

    Returns:
        The rendered `scenarios.html`.
    """
    return render_template(
        "scenarios.html",
        pieces=json.dumps(palette(), ensure_ascii=False),
        grid=json.dumps({"origin": GRID_ORIGIN, "matrix": GRID_MATRIX,
                         "piece_size": PIECE_SIZE}),
        hexagons=json.dumps({key: elements[0] for key, elements in MAP.items()}),
        forbidden=json.dumps(forbidden_squares()),
    )


def read_the_name(demand: Mapping[str, object]) -> str:
    """Reads the scenario's title.

    Args:
        demand: The request body.

    Returns:
        The title, stripped.

    Raises:
        ValueError: With a French message, if there is none.
    """
    name = demand.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Le scénario doit avoir un nom.")
    return name.strip()


def read_the_max_turns(demand: Mapping[str, object]) -> Optional[int]:
    """Reads the number of turns - `null`, absent or empty for an undetermined one.

    Args:
        demand: The request body.

    Returns:
        A positive integer, or `None`.

    Raises:
        ValueError: With a French message, for anything else.
    """
    value = demand.get("max_turns")
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("Le nombre de tours doit être un entier positif, ou rester vide.")
    return value


def read_a_square(square: object) -> Hex:
    """Reads a placement key into a hexagon a unit can occupy.

    Args:
        square: The "q,r,s" key.

    Returns:
        The hexagon.

    Raises:
        ValueError: With a French message, if the key is unreadable, off the map, or on a terrain
            no unit can occupy.
    """
    try:
        hexagon = Hex.from_key(str(square))
    except (TypeError, ValueError):
        raise ValueError(f"Case illisible : {square}.") from None
    if not hexagon.is_on_map:
        raise ValueError(f"La case {square} n'est pas sur la carte.")
    if hexagon.terrain in UNINHABITABLE:
        raise ValueError(f"Un pion ne peut pas occuper la case {hexagon.key} ({hexagon.terrain}).")
    return hexagon


def read_the_placement(demand: Mapping[str, object]) -> dict[str, str]:
    """Reads the placement, square by square.

    Args:
        demand: The request body.

    Returns:
        "q,r,s" -> piece key, the keys normalised.

    Raises:
        ValueError: With a French message, if it is empty, a square unfit, or a piece unknown.
    """
    placement = demand.get("placement")
    if not isinstance(placement, dict) or not placement:
        raise ValueError("Placez au moins un pion sur la carte.")
    read: dict[str, str] = {}
    for square, key in placement.items():
        hexagon = read_a_square(square)
        if not isinstance(key, str) or key not in PIECES_BY_KEY:
            raise ValueError(f"Pion inconnu : {key}.")
        read[hexagon.key] = key
    return read


# Any: the raw JSON of a scenario file, in the French vocabulary of the box.
def write_the_scenario(values: Mapping[str, Any]) -> Path:
    """Writes a composed scenario as a new file in `tenebrae/scenarios/`.

    The layout is that of the files fixed by hand: two-space indent, accents kept, a final newline.

    Args:
        values: What `tenebrae.engine.scenario.compose` gave.

    Returns:
        The file written.
    """
    path = engine_scenario.path_for(values["numero"], values["nom"])
    with path.open("w", encoding="utf-8") as target:
        json.dump(values, target, ensure_ascii=False, indent=2)
        target.write("\n")
    return path


@blueprint.route("/admin/scenarios", methods=["POST"])
@administrator_required
def save_a_scenario() -> ResponseReturnValue:
    """Saves a new scenario - body `{name, max_turns, placement}`.

    `placement` is "q,r,s" -> piece key, the engine's format; `max_turns` is `null` for a game
    with an undetermined number of turns. The number is the engine's: the next free one after the
    booklet's five and the files present.

    Returns:
        `saved`, then the `number`, `name`, `file` and `units` of the new scenario; 400 with a
        French `message` for a request no scenario can be composed from.
    """
    demand = request.get_json(silent=True) or {}
    try:
        name = read_the_name(demand)
        max_turns = read_the_max_turns(demand)
        placement = read_the_placement(demand)
    except ValueError as refusal:
        return {"saved": False, "message": str(refusal)}, 400
    try:
        values = engine_scenario.compose(
            name, placement, max_turns,
            source=f"composé sur /admin/scenarios le {datetime.date.today().isoformat()}")
    except ValueError:
        return {"saved": False, "message": NO_SIDE}, 400
    path = write_the_scenario(values)
    return {"saved": True, "number": values["numero"], "name": name, "file": path.name,
            "units": len(placement)}
