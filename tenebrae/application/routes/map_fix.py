"""Fixing the map - `/admin/map_fix`, reserved to the accounts in `ADMIN_DISCORD_IDS`.

The page fixes by eye the errors of the map transcription, and it is the only place where the
application writes into `tenebrae/game_box/` - into `map_fix.json`, never into `carte.json`. The
engine lays the fixes over the transcribed map at its next start-up (see `game_box/map.md`).
"""

import json
from collections.abc import Mapping

from flask import Blueprint, abort, render_template, request
from flask.typing import ResponseReturnValue

from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN
from tenebrae.application.routes.authorization import administrator_required
from tenebrae.application.routes.reading import read_a_hexagon
from tenebrae.engine import hexagon as engine_hexagon
from tenebrae.engine.hexagon import TRANSCRIBED_MAP

blueprint = Blueprint("map_fix", __name__)

# The 16 terrains of the map, in the priority order of game_box/map.md: also the order of the fix
# buttons. The names are those of the data files, and stay in French.
TERRAINS = ("ville", "fort", "chateau", "tour", "ruines", "village", "ile", "lac", "montagne",
            "colline", "bois", "faille", "riviere", "route", "chemin", "plaine")


def write_the_fixes(fixes: Mapping[str, str]) -> None:
    """Rewrites `map_fix.json`, sorted and one entry per line.

    The application alone writes this file; the engine reads it at its next start-up.

    Args:
        fixes: "q,r,s" -> fixed terrain.
    """
    with engine_hexagon.FIXES_PATH.open("w", encoding="utf-8") as target:
        json.dump(dict(sorted(fixes.items())), target, ensure_ascii=False, indent=0)
        target.write("\n")


@blueprint.route("/admin/map_fix")
@administrator_required
def fix_the_map() -> ResponseReturnValue:
    """Serves the map with the terrain of each hexagon on hover, and a click to fix it.

    The **transcribed** map goes to the browser, fixes apart: the page says what the scan gave, and
    what has been fixed of it.

    Returns:
        The rendered `map_fix.html`.
    """
    return render_template(
        "map_fix.html",
        map=json.dumps({key: elements[0] for key, elements in TRANSCRIBED_MAP.items()}),
        fixes=json.dumps(engine_hexagon.read_fixes(), ensure_ascii=False),
        applied=json.dumps(engine_hexagon.APPLIED_FIXES, ensure_ascii=False),
        terrains=json.dumps(TERRAINS),
        grid=json.dumps({"origin": GRID_ORIGIN, "matrix": GRID_MATRIX}),
    )


@blueprint.route("/admin/map_fix", methods=["POST"])
@administrator_required
def fix_a_hexagon() -> ResponseReturnValue:
    """Records the fix of a hexagon - body `{q, r, s, terrain}`.

    Choosing the terrain the **transcribed** map already gives removes the fix instead of writing
    one: that is how one goes back.

    Returns:
        The key, the terrain chosen, the original one and whether a fix now stands; 400 for an
        unknown terrain.
    """
    demand = request.get_json(silent=True) or {}
    aimed = read_a_hexagon(demand)
    terrain = demand.get("terrain")
    if terrain not in TERRAINS:
        abort(400, f"unknown terrain; expected one of {', '.join(TERRAINS)}")

    original = TRANSCRIBED_MAP[aimed.key][0]
    fixes = engine_hexagon.read_fixes()
    if terrain == original:
        fixes.pop(aimed.key, None)
    else:
        fixes[aimed.key] = terrain
    write_the_fixes(fixes)

    return {"key": aimed.key, "terrain": terrain, "original": original,
            "fixed": terrain != original}
