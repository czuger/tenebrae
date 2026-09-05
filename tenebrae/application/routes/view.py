"""Where the player is on the map: the one route that has nothing to do with the game.

It touches neither the board nor the version, and **publishes nothing** - pushing a view to the
stream would make the other player's map jump. The view is kept per player (`models/view.py`,
`repositories/view.py`), and given back to the board at the next visit.
"""

import math
from typing import Optional

from flask import Blueprint, abort, request
from flask.typing import ResponseReturnValue

from tenebrae.application.persistence import view_repository
from tenebrae.application.players import logged_in_player
from tenebrae.application.repositories.view import ViewRecord
from tenebrae.application.routes.authorization import login_required

blueprint = Blueprint("view", __name__)


def read_a_view(data: object) -> Optional[ViewRecord]:
    """Reads the view sent by the browser, reduced to its four fields.

    The scale is not bounded here: `static/zoom.js` bounds it for good, when setting as when
    restoring.

    Args:
        data: The request body, whatever it is.

    Returns:
        `{scale, x, y, fitted}`, or `None` if the body is not a dict of finite numbers.
    """
    if not isinstance(data, dict):
        return None
    try:
        view = {field: float(data[field]) for field in ("scale", "x", "y")}
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in view.values()):
        return None
    view["fitted"] = bool(data.get("fitted"))
    return view


@blueprint.route("/view", methods=["POST"])
@login_required
def record_the_view() -> ResponseReturnValue:
    """Keeps where the player is on the map - body `{scale, x, y, fitted}`.

    Login required, no seat: a logged-in spectator's view is kept too.

    Returns:
        The view as stored; 400 if unreadable.
    """
    view = read_a_view(request.get_json(silent=True))
    if view is None:
        abort(400, "unreadable view; expected {scale, x, y, fitted}")
    return view_repository().record(logged_in_player()["discord_id"], view)
