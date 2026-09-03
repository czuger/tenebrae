"""The scenarios: a fixed set-up, read from `tenebrae/scenarios/`.

The booklet describes each scenario in a sentence - "the dwarf army masses south of the volcano of
Toth" - without saying which piece goes on which square. The step from the sentence to the
hexagons was taken once and for all, and the result lives in `tenebrae/scenarios/*.json` (see
`tenebrae/scenarios/README.md`): the engine only reads it.

Those files are data, and their field names stay in French like the rest of the box; they are read
as such here.

A scenario yields a `Board` ready to play, with each side already in place.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from tenebrae.engine.board import Board
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import CATALOGUE

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"


class Scenario:
    """A set-up: the armies present, and the piece placed on each square."""

    __slots__ = ("number", "name", "source", "armies", "placement")

    number: int
    name: str
    source: str
    armies: tuple[dict[str, str], ...]
    placement: dict[str, str]

    # Any: the raw JSON of a scenario file, in the French vocabulary of the box.
    def __init__(self, values: Mapping[str, Any]) -> None:
        """Reads a scenario from its JSON values.

        Args:
            values: The file's fields: `numero`, `nom`, `source`, `armees`, `placement`.
        """
        self.number = values["numero"]
        self.name = values["nom"]
        self.source = values["source"]
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
