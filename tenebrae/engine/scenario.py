"""The scenarios: a fixed set-up, read from `tenebrae/scenarios/`.

The booklet describes each scenario in a sentence - "the dwarf army masses south of the volcano of
Toth" - without saying which piece goes on which square. The step from the sentence to the
hexagons was taken once and for all, and the result lives in `tenebrae/scenarios/*.json` (see
`tenebrae/scenarios/README.md`): the engine only reads it.

Those files are data, and their field names stay in French like the rest of the box; they are read
as such here.

A scenario yields a `Board` ready to play, with each side already in place.

The engine also **composes** a scenario from a placement (`compose`): the values of a new file, its
armies derived from the pieces placed. Writing the file is left to the caller - the application's
`/admin/scenarios` page -, which is also where the placement is checked.
"""

import json
import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Optional

from tenebrae.engine.board import Board
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import ALLIANCE, CATALOGUE, DARKNESS, NEUTRAL

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"

# The booklet's scenarios, numbered 1 to 5: a composed scenario takes the next number after them,
# so that fixing a booklet scenario later never collides with one made on the map.
BOOKLET_SCENARIOS = 5

# What a composed file names a scenario whose title yields no slug at all.
UNTITLED = "sans-titre"


class Scenario:
    """A set-up: the armies present, and the piece placed on each square."""

    __slots__ = ("number", "name", "source", "max_turns", "armies", "placement")

    number: int
    name: str
    source: str
    max_turns: Optional[int]
    armies: tuple[dict[str, str], ...]
    placement: dict[str, str]

    # Any: the raw JSON of a scenario file, in the French vocabulary of the box.
    def __init__(self, values: Mapping[str, Any]) -> None:
        """Reads a scenario from its JSON values.

        Args:
            values: The file's fields: `numero`, `nom`, `source`, `armees`, `placement`, and
                `nombre_de_tours` - absent or `null` for a game "with an undetermined number of
                turns", as the booklet puts it.
        """
        self.number = values["numero"]
        self.name = values["nom"]
        self.source = values["source"]
        self.max_turns = values.get("nombre_de_tours")
        self.armies = tuple(values["armees"])
        self.placement = dict(values["placement"])

    @property
    def sides(self) -> tuple[str, ...]:
        """The sides present, in player order."""
        return tuple(army["camp"] for army in self.armies)

    def board(self) -> Board:
        """Lays the set-up out on a fresh board.

        Returns:
            A `Board` with each piece on its square.

        Raises:
            KeyError: If a piece key is unknown to the catalogue.
            ValueError: If a square is off the map. Better a refused scenario than an army
                quietly cut short.
        """
        return Board((Hex.from_key(square), CATALOGUE[key])
                     for square, key in self.placement.items())

    def __len__(self) -> int:
        """The number of pieces placed."""
        return len(self.placement)

    def __repr__(self) -> str:
        """The number, the name and the size of the set-up."""
        return f"Scenario({self.number}, {self.name!r}, {len(self.placement)} units)"


def read(path: Path) -> Scenario:
    """Reads a scenario from its JSON file.

    Args:
        path: The file to read.

    Returns:
        The scenario.
    """
    with Path(path).open(encoding="utf-8") as source:
        return Scenario(json.load(source))


def available_scenarios() -> dict[int, Path]:
    """Lists the fixed scenarios.

    Returns:
        Number -> file, in numeric order.
    """
    files = {}
    for path in sorted(SCENARIOS.glob("scenario-*.json")):
        files[int(path.stem.split("-")[1])] = path
    return files


def scenario(number: int) -> Scenario:
    """Reads the scenario with a given number.

    Args:
        number: The booklet's scenario number.

    Returns:
        The scenario.

    Raises:
        KeyError: If it has not been fixed yet.
    """
    return read(available_scenarios()[number])


# --- Composing a scenario -----------------------------------------------------------------------


def next_number() -> int:
    """Finds the number a scenario composed now would take.

    Returns:
        One more than the highest number in use, the booklet's five counting as used.
    """
    return max([BOOKLET_SCENARIOS, *available_scenarios()]) + 1


def slug(name: str) -> str:
    """Turns a title into the file-name convention of the box: no accents, no apostrophes.

    Args:
        name: The title, e.g. `"L'aube des Ténèbres"`.

    Returns:
        Lower-case ASCII words joined by hyphens, e.g. `"l-aube-des-tenebres"`.
    """
    plain = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return "-".join(re.findall(r"[a-z0-9]+", plain.lower()))


def path_for(number: int, name: str) -> Path:
    """Names the file of a scenario, as `available_scenarios` expects it.

    Args:
        number: The scenario number, written on two digits.
        name: The title, slugified.

    Returns:
        `tenebrae/scenarios/scenario-NN-<slug>.json`.
    """
    return SCENARIOS / f"scenario-{number:02d}-{slug(name) or UNTITLED}.json"


def army_name(factions: list[str]) -> str:
    """Names an army after its factions.

    Args:
        factions: The faction directories, e.g. `["09-elfes", "10-nains"]`.

    Returns:
        The readable names joined by "et", e.g. `"Elfes et Nains"`.
    """
    return " et ".join(faction.split("-", 1)[1].replace("-", " ").capitalize()
                       for faction in factions)


def armies_of(placement: Mapping[str, str]) -> list[dict[str, Any]]:
    """Derives the `armees` entries from a placement: one per side present, alliance first.

    The neutral pieces - spellcasters, conjurations, markers - belong to no army: they play no
    turn. What the booklet gives an army and the map cannot - the instruction, the anchor, the
    magic potential, the spellcaster - stays `null`.

    Args:
        placement: "q,r,s" -> piece key.

    Returns:
        The entries, in player order; empty if only neutral pieces are placed.
    """
    armies: list[dict[str, Any]] = []
    for side in (ALLIANCE, DARKNESS):
        keys = [key for key in placement.values() if CATALOGUE[key].side == side]
        if not keys:
            continue
        factions = sorted({CATALOGUE[key].faction for key in keys})
        armies.append({"joueur": len(armies) + 1, "camp": side, "armee": army_name(factions),
                       "consigne": None, "ancre": None, "unites": len(keys), "magie": None,
                       "jeteur_de_sorts": None})
    return armies


def grouped_by_side(placement: Mapping[str, str]) -> dict[str, str]:
    """Orders a placement side by side - alliance, darkness, then the neutrals - for the file.

    Args:
        placement: "q,r,s" -> piece key, in any order.

    Returns:
        The same entries, each side's together, the order within a side kept.
    """
    grouped: dict[str, str] = {}
    for side in (ALLIANCE, DARKNESS, NEUTRAL):
        grouped.update((square, key) for square, key in placement.items()
                       if CATALOGUE[key].side == side)
    return grouped


def compose(name: str, placement: Mapping[str, str], max_turns: Optional[int] = None,
            source: str = "") -> dict[str, Any]:
    """Assembles the values of a new scenario file from a placement.

    The armies are derived from the pieces placed (`armies_of`), and the number is the next free
    one. Nothing is written: the caller gets the values in the file's vocabulary and decides
    where they go.

    Args:
        name: The scenario's title.
        placement: "q,r,s" -> piece key, one piece per square.
        max_turns: The number of turns the game lasts, `None` for an undetermined one.
        source: Where the scenario comes from, for the `source` field.

    Returns:
        The file's fields: `numero`, `nom`, `source`, `nombre_de_tours`, `armees`, `placement`.

    Raises:
        KeyError: If a piece key is unknown to the catalogue.
        ValueError: If a square is off the map, or if no unit of a side is placed - a turn needs
            a side to play it.
    """
    for square in placement:
        if not Hex.from_key(square).is_on_map:
            raise ValueError(f"square {square} is off the map")
    armies = armies_of(placement)
    if not armies:
        raise ValueError("a scenario needs at least one unit of a side: neutral pieces play no "
                         "turn")
    return {"numero": next_number(), "nom": name, "source": source,
            "nombre_de_tours": max_turns, "armees": armies,
            "placement": grouped_by_side(placement)}
