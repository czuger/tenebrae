"""The scenarios: a fixed set-up, read from `scenarios/`.

The booklet describes each scenario in a sentence - "the dwarf army masses south of the volcano of
Toth" - without saying which piece goes on which square. The step from the sentence to the
hexagons was taken once and for all, and the result lives in `scenarios/*.json` (see
`scenarios/README.md`): the engine only reads it.

Those files are data, and their field names stay in French like the rest of the box; they are read
as such here.

A scenario yields a `Board` ready to play, with each side already in place.
"""

import json
from pathlib import Path

from engine.board import Board
from engine.hexagon import Hex
from engine.piece import CATALOGUE

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"


class Scenario:
    """A set-up: the armies present, and the piece placed on each square."""

    __slots__ = ("number", "name", "source", "armies", "placement")

    def __init__(self, values):
        self.number = values["numero"]
        self.name = values["nom"]
        self.source = values["source"]
        self.armies = tuple(values["armees"])
        self.placement = dict(values["placement"])

    @property
    def sides(self):
        """The sides present, in player order."""
        return tuple(army["camp"] for army in self.armies)

    def board(self):
        """A fresh `Board`, each piece on its square.

        A piece key unknown to the catalogue, or a square off the map, stops the read: better a
        refused scenario than an army quietly cut short.
        """
        return Board((Hex.from_key(square), CATALOGUE[key])
                     for square, key in self.placement.items())

    def __len__(self):
        return len(self.placement)

    def __repr__(self):
        return f"Scenario({self.number}, {self.name!r}, {len(self.placement)} units)"


def read(path):
    """Reads a scenario from its JSON file."""
    with Path(path).open(encoding="utf-8") as source:
        return Scenario(json.load(source))


def available_scenarios():
    """"number -> path" for every fixed scenario, in numeric order."""
    files = {}
    for path in sorted(SCENARIOS.glob("scenario-*.json")):
        files[int(path.stem.split("-")[1])] = path
    return files


def scenario(number):
    """The scenario with that number; `KeyError` if it has not been fixed yet."""
    return read(available_scenarios()[number])
