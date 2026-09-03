"""The pieces as the browser receives them: the catalogue reduced to what shows a single piece.

The engine's catalogue carries the 127 photographs; the page keeps only those showing a single
piece - not the overview sheets. Markers stay: they are placed on the map, they do not move from it.
Everything printed on the counter goes with each piece, for the card the browser shows on hover.
"""

from pathlib import Path
from typing import Optional

from tenebrae.engine.piece import CATALOGUE

BOX = Path(__file__).resolve().parent.parent / "game_box"
PIECES = BOX / "pions"

# What, within `pions/`, does not show a single piece: the directory of whole sheets, and the
# photographs of record sheets taken "as an overview".
EXCLUDED_DIRECTORIES = {"21-vues-d-ensemble"}
EXCLUDED_SUFFIX = "-vue-d-ensemble"

# A piece as the browser receives it: strings, integers or `None` for what the counter lacks.
PieceEntry = dict[str, Optional[str] | Optional[int]]


def is_a_piece(path: str) -> bool:
    """Says whether a photograph really shows a single piece.

    Args:
        path: The path relative to `pions/`, e.g. `"01-yzent/yzent-05-1-belier.jpg"`.

    Returns:
        False for the overview directory and the "vue-d-ensemble" photographs.
    """
    directory, _, filename = path.partition("/")
    return (directory not in EXCLUDED_DIRECTORIES
            and not filename.removesuffix(".jpg").endswith(EXCLUDED_SUFFIX))


def name_of(path: Path) -> str:
    """Builds the readable name of a piece from its photograph's path.

    The file name repeats the directory name without its number, followed by the piece's rank
    within the faction then by its description (see `game_box/pions/README.md`).

    Args:
        path: The photograph, e.g. `.../01-yzent/yzent-05-1-belier.jpg`.

    Returns:
        The faction and the description, e.g. `"yzent · 1 belier"`.
    """
    faction = path.parent.name.split("-", 1)[1]
    description = path.stem.removeprefix(f"{faction}-")[3:]
    return f"{faction.replace('-', ' ')} · {description.replace('-', ' ')}"


def load_pieces() -> list[PieceEntry]:
    """Lists the available pieces, values read off the counter included.

    `Piece.to_dict()` is not reused as it is: its `movement` is the raw counter value, sometimes
    absent, whereas `movement` here is the movement budget, and its `image` is the repository path,
    not that of the `/pieces/` route.

    Returns:
        One entry per piece, sorted by photograph, with `key`, `path`, `name`, `movement`, `side`
        and everything the counter carries.
    """
    pieces: list[PieceEntry] = []
    for piece in sorted(CATALOGUE.values(), key=lambda piece: piece.image):
        path = PIECES / piece.image.removeprefix("game_box/pions/")
        relative = f"{path.parent.name}/{path.name}"
        if is_a_piece(relative):
            pieces.append({"key": piece.key, "path": relative, "name": name_of(path),
                           "movement": piece.movement_points, "side": piece.side,
                           "faction": piece.faction, "symbol": piece.symbol,
                           "strength": piece.strength, "fire": piece.fire, "range": piece.range,
                           "flight_movement": piece.flight_movement,
                           "special_abilities": piece.special_abilities,
                           "remarks": piece.remarks})
    return pieces


PIECE_CATALOGUE = load_pieces()
PIECES_BY_KEY = {piece["key"]: piece for piece in PIECE_CATALOGUE}
