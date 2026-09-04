"""Composing and editing a scenario - `/admin/scenarios`, reserved to `ADMIN_DISCORD_IDS`.

The page lays the box's pieces beside the map: a piece taken from that palette is placed with a
click, and the set-up is saved as a **new file** in `tenebrae/scenarios/`, in the very format
`tenebrae.engine.scenario` reads (see `tenebrae/scenarios/README.md`). The route checks the
request - every square on the map and fit to be occupied, every piece one the box shows -, the
engine composes the file's values from the placement, and the route writes them. Each save is a
new scenario, with the next free number.

The same page **edits** a scenario: `/admin/scenarios/<number>/edit` opens it with the file's
pieces already on the map, and saving there rewrites that file - the number kept, the title, the
turns and the placement replaced, and what was written into the armies by hand carried over. That
is the only route that rewrites a file in `tenebrae/scenarios/`.

The `enabled` field is not set from this page: it is written into the file by hand, and it is what
withdraws a scenario from the new-game chooser (`routes/game.py`). A save carries it through
unchanged - a scenario disabled and then edited stays disabled - and the chooser in the toolbar
marks the disabled ones, which are still opened for editing here, since re-enabling one means
opening its file.
"""

import datetime
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from flask import Blueprint, render_template, request, url_for
from flask.typing import ResponseReturnValue

from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN, PIECE_SIZE
from tenebrae.application.pieces import PIECE_CATALOGUE, PIECES_BY_KEY
from tenebrae.application.routes.authorization import administrator_required
from tenebrae.engine import scenario as engine_scenario
from tenebrae.engine.hexagon import MAP, UNINHABITABLE, Hex
from tenebrae.engine.piece import ALLIANCE, CATALOGUE, DARKNESS
from tenebrae.engine.scenario import Scenario

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


def available() -> list[dict[str, object]]:
    """Lists the scenarios the page can open for editing: every file in `tenebrae/scenarios/`.

    The disabled ones are listed too, and marked as such: `"enabled": false` withdraws a scenario
    from the new-game chooser (`/game/scenarios`), not from the page that edits it - re-enabling
    one means opening its file, so hiding it here would lock it away.

    Returns:
        One entry per scenario, in numeric order: `number`, `name`, `file`, `enabled`.
    """
    listed: list[dict[str, object]] = []
    for number, path in engine_scenario.available_scenarios().items():
        existing = engine_scenario.read(path)
        listed.append({"number": number, "name": existing.name, "file": path.name,
                       "enabled": existing.enabled})
    return listed


def to_edit(existing: Scenario) -> dict[str, object]:
    """Shapes a scenario for the page: what the form asks for, and the pieces to lay.

    Args:
        existing: The scenario as read from its file.

    Returns:
        `number`, `name`, `max_turns`, `enabled`, `placement`.
    """
    return {"number": existing.number, "name": existing.name, "max_turns": existing.max_turns,
            "enabled": existing.enabled, "placement": existing.placement}


def render_the_page(existing: Optional[Scenario] = None) -> str:
    """Renders the composing page, empty or with a scenario to edit already on the map.

    The **fixed** map goes to the browser - the one the game is played on -, so that the page
    refuses the same squares as the engine.

    Args:
        existing: The scenario to edit, or `None` to compose a new one.

    Returns:
        The rendered `scenarios.html`.
    """
    save_url = (url_for("scenarios.save_a_scenario") if existing is None
                else url_for("scenarios.update_a_scenario", number=existing.number))
    return render_template(
        "scenarios.html",
        pieces=json.dumps(palette(), ensure_ascii=False),
        grid=json.dumps({"origin": GRID_ORIGIN, "matrix": GRID_MATRIX,
                         "piece_size": PIECE_SIZE}),
        hexagons=json.dumps({key: elements[0] for key, elements in MAP.items()}),
        forbidden=json.dumps(forbidden_squares()),
        scenarios=json.dumps(available(), ensure_ascii=False),
        scenario=json.dumps(to_edit(existing), ensure_ascii=False) if existing else "",
        editing=existing is not None,
        scenario_number=existing.number if existing else None,
        save_url=save_url,
    )


@blueprint.route("/admin/scenarios")
@administrator_required
def compose_a_scenario() -> ResponseReturnValue:
    """Serves the map with the palette of pieces beside it, empty.

    Returns:
        The rendered `scenarios.html`.
    """
    return render_the_page()


@blueprint.route("/admin/scenarios/<int:number>/edit")
@administrator_required
def edit_a_scenario(number: int) -> ResponseReturnValue:
    """Serves the same page with a scenario's pieces already on the map.

    Args:
        number: The scenario's number, the one its file name carries.

    Returns:
        The rendered `scenarios.html`; 404 with a French `message` for a number no file has.
    """
    try:
        existing = engine_scenario.scenario(number)
    except KeyError:
        return {"message": f"Aucun scénario n° {number}."}, 404
    return render_the_page(existing)


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
def attack_point_totals(placement: Mapping[str, str]) -> dict[str, int]:
    """Totals the close-combat and ranged attack points placed for each side.

    A counter's `strength` and `fire` are respectively the catalogue's `force` and `tir` values.
    Missing values are `None` and contribute no points; neutral counters contribute to neither
    side.

    Args:
        placement: "q,r,s" -> piece key.

    Returns:
        The Alliance and Darkness totals, including zero when a side is absent.
    """
    totals = {ALLIANCE: 0, DARKNESS: 0}
    for key in placement.values():
        piece = CATALOGUE[key]
        if piece.side in totals:
            totals[piece.side] += (piece.strength or 0) + (piece.fire or 0)
    return totals


# Any: the raw JSON of a scenario file, in the French vocabulary of the box.
def write_the_scenario(values: Mapping[str, Any]) -> Path:
    """Writes a scenario's values as a file in `tenebrae/scenarios/`, named after its title.

    The layout is that of the files fixed by hand: two-space indent, accents kept, a final newline.

    Args:
        values: What `tenebrae.engine.scenario.compose` or `recompose` gave.

    Returns:
        The file written.
    """
    totals = attack_point_totals(values["placement"])
    enriched = dict(values)
    enriched["total_points_alliance"] = totals[ALLIANCE]
    enriched["total_points_tenebres"] = totals[DARKNESS]

    path = engine_scenario.path_for(enriched["numero"], enriched["nom"])
    with path.open("w", encoding="utf-8") as target:
        json.dump(enriched, target, ensure_ascii=False, indent=2)
        target.write("\n")
    return path


class Demand:
    """What the request asks for, read and checked: the title, the turns, the placement."""

    __slots__ = ("name", "max_turns", "placement")

    def __init__(self, demand: Mapping[str, object]) -> None:
        """Reads the request body.

        Args:
            demand: The JSON body, `{name, max_turns, placement}`.

        Raises:
            ValueError: With a French message, for whatever no scenario can be made from.
        """
        self.name = read_the_name(demand)
        self.max_turns = read_the_max_turns(demand)
        self.placement = read_the_placement(demand)


def saved(values: Mapping[str, Any], path: Path) -> dict[str, object]:
    """Shapes the answer to a save: what the page states under the toolbar.

    Args:
        values: The file's fields.
        path: The file written.

    Returns:
        `saved`, the `number`, `name`, `file` and `units`.
    """
    return {"saved": True, "number": values["numero"], "name": values["nom"], "file": path.name,
            "units": len(values["placement"])}


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
    try:
        demand = Demand(request.get_json(silent=True) or {})
    except ValueError as refusal:
        return {"saved": False, "message": str(refusal)}, 400
    try:
        values = engine_scenario.compose(
            demand.name, demand.placement, demand.max_turns,
            source=f"composé sur /admin/scenarios le {datetime.date.today().isoformat()}")
    except ValueError:
        return {"saved": False, "message": NO_SIDE}, 400
    return saved(values, write_the_scenario(values))


@blueprint.route("/admin/scenarios/<int:number>/edit", methods=["POST"])
@administrator_required
def update_a_scenario(number: int) -> ResponseReturnValue:
    """Rewrites a scenario's file - the same body as a save.

    The number stays; the title, the turns and the placement are those of the request; the armies
    are derived again, what was written into them by hand carried over
    (`tenebrae.engine.scenario.recompose`). A new title renames the file: the old one is removed
    once the new one is written.

    Args:
        number: The scenario's number.

    Returns:
        What a save answers; 400 with a French `message` for a request no scenario can be
        composed from, the file untouched; 404 for a number no file has.
    """
    files = engine_scenario.available_scenarios()
    if number not in files:
        return {"saved": False, "message": f"Aucun scénario n° {number}."}, 404
    try:
        demand = Demand(request.get_json(silent=True) or {})
    except ValueError as refusal:
        return {"saved": False, "message": str(refusal)}, 400
    try:
        values = engine_scenario.recompose(engine_scenario.read(files[number]), demand.name,
                                           demand.placement, demand.max_turns)
    except ValueError:
        return {"saved": False, "message": NO_SIDE}, 400
    path = write_the_scenario(values)
    if path != files[number]:
        files[number].unlink()
    return saved(values, path)
