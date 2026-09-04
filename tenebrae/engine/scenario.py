"""The scenarios: a fixed set-up, read from `tenebrae/scenarios/`.

The booklet describes each scenario in a sentence - "the dwarf army masses south of the volcano of
Toth" - without saying which piece goes on which square. The step from the sentence to the
hexagons was taken once and for all, and the result lives in `tenebrae/scenarios/*.json` (see
`tenebrae/scenarios/README.md`): the engine only reads it.

Those files are data, and their field names stay in French like the rest of the box; they are read
as such here.

A scenario yields a `Board` ready to play, with each side already in place.

A file may be **withdrawn** from the scenarios a new game can be opened on by setting `"enabled":
false` in it by hand - `enabled_scenarios()` is what the application offers. The field is absent
from every file written before it existed, and read as `True` there.

The engine also **composes** a scenario from a placement (`compose`): the values of a new file, its
armies derived from the pieces placed. It **recomposes** an existing one the same way
(`recompose`), keeping its number and what was written into it by hand. Writing the file is left to
the caller - the application's `/admin/scenarios` page -, which is also where the placement is
checked.
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

# What an army entry carries that the map cannot give: written by hand, kept through a recompose.
HAND_WRITTEN = ("consigne", "ancre", "magie", "jeteur_de_sorts")

# What a scenario file whose `enabled` field is absent means: every file written before the field
# existed goes on being offered. `"enabled": false`, set by hand in the file, withdraws a scenario
# from the ones a new game can be opened on - a game already under way on it is not interrupted.
ENABLED_BY_DEFAULT = True


# Any: the raw JSON of a scenario file, in the French vocabulary of the box.
def is_enabled(values: Mapping[str, Any]) -> bool:
    """Says whether a scenario's values offer it for a new game.

    Args:
        values: The file's fields.

    Returns:
        The `enabled` field as a boolean, `ENABLED_BY_DEFAULT` where the file carries none.
    """
    return bool(values.get("enabled", ENABLED_BY_DEFAULT))


class Scenario:
    """A set-up: the armies present, and the piece placed on each square."""

    __slots__ = ("number", "name", "source", "max_turns", "enabled", "armies", "placement")

    number: int
    name: str
    source: str
    max_turns: Optional[int]
    enabled: bool
    armies: tuple[dict[str, str], ...]
    placement: dict[str, str]

    # Any: the raw JSON of a scenario file, in the French vocabulary of the box.
    def __init__(self, values: Mapping[str, Any]) -> None:
        """Reads a scenario from its JSON values.

        Args:
            values: The file's fields: `numero`, `nom`, `source`, `armees`, `placement`,
                `nombre_de_tours` - absent or `null` for a game "with an undetermined number of
                turns", as the booklet puts it - and `enabled`, absent in every file written
                before the field existed and read as `True` there (`ENABLED_BY_DEFAULT`).
        """
        self.number = values["numero"]
        self.name = values["nom"]
        self.source = values["source"]
        self.max_turns = values.get("nombre_de_tours")
        self.enabled = is_enabled(values)
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


def enabled_scenarios() -> dict[int, Scenario]:
    """Reads the scenarios a new game can be opened on: the files, minus those disabled by hand.

    Every file is read from disk at each call - nothing is kept between two - so that an `enabled`
    just set to `false` in a file is honoured without restarting the server.

    Returns:
        Number -> scenario, in numeric order.
    """
    read_files = {number: read(path) for number, path in available_scenarios().items()}
    return {number: found for number, found in read_files.items() if found.enabled}


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


def checked_armies(placement: Mapping[str, str]) -> list[dict[str, Any]]:
    """Derives the armies of a placement fit to be a scenario.

    Args:
        placement: "q,r,s" -> piece key, one piece per square.

    Returns:
        What `armies_of` gives.

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
    return armies


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
    armies = checked_armies(placement)
    return {"numero": next_number(), "nom": name, "source": source,
            "nombre_de_tours": max_turns, "enabled": ENABLED_BY_DEFAULT, "armees": armies,
            "placement": grouped_by_side(placement)}


def recompose(existing: Scenario, name: str, placement: Mapping[str, str],
              max_turns: Optional[int] = None) -> dict[str, Any]:
    """Assembles the values of an existing scenario's file from a new placement.

    The number and the `source` stay those of the scenario. The armies are derived again from the
    pieces placed - a side that left the map loses its entry, a side that arrived gets a fresh one
    -, and what an entry carried that the map cannot give (`HAND_WRITTEN`: the instruction, the
    anchor, the magic potential, the spellcaster) is kept for every side still present.

    Args:
        existing: The scenario as read from its file.
        name: The new title.
        placement: "q,r,s" -> piece key, one piece per square.
        max_turns: The number of turns the game lasts, `None` for an undetermined one.

    Returns:
        The file's fields, as `compose` gives them.

    Raises:
        KeyError: If a piece key is unknown to the catalogue.
        ValueError: If a square is off the map, or if no unit of a side is placed.
    """
    kept = {army["camp"]: army for army in existing.armies}
    armies = checked_armies(placement)
    for army in armies:
        if army["camp"] in kept:
            army.update((field, kept[army["camp"]].get(field)) for field in HAND_WRITTEN)
    return {"numero": existing.number, "nom": name, "source": existing.source,
            "nombre_de_tours": max_turns, "enabled": existing.enabled, "armees": armies,
            "placement": grouped_by_side(placement)}
