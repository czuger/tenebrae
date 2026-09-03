"""The images served from `tenebrae/game_box/`: the scan of the map, and the piece photographs."""

from flask import Blueprint, abort, send_from_directory
from flask.typing import ResponseReturnValue

from tenebrae.application.pieces import BOX, PIECES, is_a_piece

blueprint = Blueprint("images", __name__)


@blueprint.route("/map.jpg")
def map_image() -> ResponseReturnValue:
    """Serves the scan of the map.

    Returns:
        `game_box/map.jpg`.
    """
    return send_from_directory(BOX, "map.jpg")


@blueprint.route("/pieces/<path:path>")
def piece_image(path: str) -> ResponseReturnValue:
    """Serves the photograph of a piece.

    Args:
        path: The path relative to `pions/`.

    Returns:
        The photograph; 404 for anything that is not a single piece.
    """
    if not is_a_piece(path):
        abort(404)
    return send_from_directory(PIECES, path)
