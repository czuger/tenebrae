"""Reading the request: the hexagons and pieces a query string or a JSON body names.

Every reader answers a malformed parameter with the HTTP status the browser expects - 400 for
what cannot be read, 404 for a hexagon off the map - rather than a Python error.
"""

from collections.abc import Mapping
from typing import Optional

from flask import abort

from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import CATALOGUE, Piece


def read_a_piece(key: Optional[str]) -> Optional[Piece]:
    """Finds the piece a request names in the catalogue.

    Movement points and side come from the catalogue, never from the request.

    Args:
        key: The piece key, or `None` if the request names none.

    Returns:
        The piece, or `None`; 400 for an unknown key - better refuse than move an imaginary piece.
    """
    if key is None:
        return None
    if key not in CATALOGUE:
        abort(400, f"unknown piece: {key}")
    return CATALOGUE[key]


def read_a_hexagon(source: Mapping[str, object]) -> Hex:
    """Builds a `Hex` from `q`, `r`, `s` parameters.

    Args:
        source: The query string or the request body.

    Returns:
        The hexagon; 400 if unreadable, 404 if off the map.
    """
    try:
        hexagon = Hex(*(read_a_coordinate(source[name]) for name in ("q", "r", "s")))
    except (KeyError, TypeError, ValueError):
        abort(400, "q, r and s coordinates expected, integers summing to zero")
    if not hexagon.is_on_map:
        abort(404, f"hexagon {hexagon.key} is not on the map")
    return hexagon


def read_a_coordinate(value: object) -> int:
    """Reads one cube coordinate, as the query string (text) or the JSON body (a number) gives it.

    Args:
        value: The parameter, whatever the request put there.

    Returns:
        The integer.

    Raises:
        TypeError: For anything that is neither text nor a number.
        ValueError: For text that is not an integer.
    """
    if isinstance(value, (str, int, float)):
        return int(value)
    raise TypeError(f"coordinate expected, not {type(value).__name__}")
