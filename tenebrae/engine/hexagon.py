"""The hexagon grid of Ave Tenebrae and the moves it allows.

The game map is the transcription of the scan (`tenebrae/game_box/carte_details.json`) overlaid with
the fixes recorded by eye (`tenebrae/game_box/map_fix.json`). Both files are read once, when the
module is imported, and the result is held to be constant: the board was printed in 1986, it does
not change mid-game. Fixing the map therefore requires restarting the program.

Movement cost follows the booklet's *Terrain table*; the interpretation caveats are recorded in
`tenebrae/engine/README.md`. The movement budget itself comes from the piece:
`tenebrae.engine.piece` reads it off the counter, and `moves()` receives it as an argument. At this
stage every unit is a ground unit: no flight, no powers, no stacking beyond one piece per square.

Terrain names stay in French (`plaine`, `bois`, `montagne`, …): they are the vocabulary of the
transcribed data files, which are the source of truth and are not translated. Only the code around
them is English.
"""

import heapq
import json
from collections.abc import Collection, Iterable, Mapping
from fractions import Fraction
from pathlib import Path
from typing import Optional

BOX = Path(__file__).resolve().parent.parent / "game_box"

# `carte_details.json` rather than `carte.json`: same main terrain at the head of each list, but it
# alone keeps the roads and paths hidden under a wood or a massif by the map's priority rule.
with (BOX / "carte_details.json").open(encoding="utf-8") as source:
    TRANSCRIBED_MAP: dict[str, tuple[str, ...]] = {
        key: tuple(elements) for key, elements in json.load(source).items()}

# The fixes recorded by eye on /admin/map_fix: "q,r,s" -> main terrain.
FIXES_PATH = BOX / "map_fix.json"


def read_fixes() -> dict[str, str]:
    """Reads the recorded map fixes.

    Returns:
        "q,r,s" -> fixed main terrain; empty if the file does not exist.
    """
    try:
        with FIXES_PATH.open(encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        return {}


def apply_fixes(transcription: Mapping[str, tuple[str, ...]],
                fixes: Mapping[str, str]) -> dict[str, tuple[str, ...]]:
    """Overlays the fixes on the transcription, without modifying it.

    A fix only bears on the main terrain: the fixed terrain takes the lead and the secondary
    elements follow, so a wood fixed into a hill keeps the road it was hiding. A key unknown to
    the transcription is ignored: no hexagon is created off the map.

    Args:
        transcription: "q,r,s" -> elements of the hexagon, main terrain first.
        fixes: "q,r,s" -> main terrain to impose.

    Returns:
        A new "q,r,s" -> elements dict, fixes applied.
    """
    game_map = dict(transcription)
    for key, terrain in fixes.items():
        if key not in game_map:
            continue
        secondary = (element for element in game_map[key][1:] if element != terrain)
        game_map[key] = (terrain, *secondary)
    return game_map


# The fixes in force and the map the game is played on, both fixed at start-up.
APPLIED_FIXES = read_fixes()
MAP = apply_fixes(TRANSCRIBED_MAP, APPLIED_FIXES)

# The six neighbours of a hexagon, in cube coordinates.
DIRECTIONS = ((1, -1, 0), (1, 0, -1), (0, 1, -1), (0, -1, 1), (-1, 1, 0), (-1, 0, 1))

# Movement points spent to enter the square. Terrains not listed here cost 1 point.
ORDINARY_COST = Fraction(1)
COSTS = {
    "bois": Fraction(2),      # WOODS - 2 points except Elves
    "colline": Fraction(2),   # HILLS - 2 points except Earth elemental
    "ruines": Fraction(2),    # RUINS - x 2
}

# The rate for ways, when following them from one square to the next: ROADS x 3, PATHS x 2.
WAY_COSTS = {"route": Fraction(1, 3), "chemin": Fraction(1, 2)}

# Impassable to a ground unit: lakes and rivers (bridges are not recorded on the map), the Rift of
# Tsaroth, forts and castles (except by combat or through allies).
IMPASSABLE = frozenset({"lac", "riviere", "faille", "fort", "chateau"})

# A mountain can only be entered from a hill, another mountain, or a way crossing it.
MOUNTAIN_ACCESS = frozenset({"colline", "montagne"})

# Terrains a ground unit cannot occupy, and therefore never departs from. Forts and castles are
# not among them: they are not crossed, but they can be garrisoned.
UNINHABITABLE = frozenset({"lac", "riviere", "faille"})

# Flat movement rate, for callers that do not say which piece they mean (see
# `tenebrae.engine.piece`).
DEFAULT_MOVEMENT = 5


class Hex:
    """A hexagon of the map, in cube coordinates `q + r + s = 0`.

    Built from the three coordinates, from `q` and `r` alone - `s` follows - or from nothing at
    all: `Hex()` is an empty hexagon, with no position.
    """

    __slots__ = ("q", "r", "s")

    q: Optional[int]
    r: Optional[int]
    s: Optional[int]

    def __init__(self, q: Optional[int] = None, r: Optional[int] = None,
                 s: Optional[int] = None) -> None:
        """Builds a hexagon from its cube coordinates.

        Args:
            q: First cube coordinate; `None` with the others for an empty hexagon.
            r: Second cube coordinate.
            s: Third cube coordinate, derived from the other two when omitted.

        Raises:
            ValueError: If only one of `q` and `r` is given, or if the three do not sum to zero.
        """
        if q is None and r is None and s is None:
            self.q = self.r = self.s = None
            return
        if q is None or r is None:
            raise ValueError("a hexagon is given by q and r, or by q, r and s, or empty")
        if s is None:
            s = -q - r
        if q + r + s != 0:
            raise ValueError(f"inconsistent cube coordinates: {q} + {r} + {s} != 0")
        self.q, self.r, self.s = q, r, s

    @classmethod
    def from_key(cls, key: str) -> "Hex":
        """Builds a hexagon from a `carte.json` key.

        Args:
            key: The "q,r,s" key.

        Returns:
            The hexagon at those coordinates.
        """
        return cls(*(int(value) for value in key.split(",")))

    @property
    def is_empty(self) -> bool:
        """Whether the hexagon has no position."""
        return self.q is None

    @property
    def key(self) -> str:
        """The "q,r,s" key under which the map knows this hexagon."""
        q, r, s = self._position()
        return f"{q},{r},{s}"

    @property
    def is_on_map(self) -> bool:
        """Whether the hexagon has a position and the map knows it."""
        return not self.is_empty and self.key in MAP

    @property
    def elements(self) -> tuple[str, ...]:
        """Everything the hexagon carries, main terrain first; empty if it is off the map."""
        self._position()
        return MAP.get(self.key, ())

    @property
    def terrain(self) -> Optional[str]:
        """The main terrain of the hexagon, or `None` if it is off the map."""
        elements = self.elements
        return elements[0] if elements else None

    def neighbours(self) -> list["Hex"]:
        """Lists the adjacent hexagons that are on the map.

        Returns:
            At most six hexagons, in the order of `DIRECTIONS`.
        """
        q, r, s = self._position()
        neighbours = (Hex(q + dq, r + dr, s + ds) for dq, dr, ds in DIRECTIONS)
        return [neighbour for neighbour in neighbours if neighbour.is_on_map]

    def distance(self, other: "Hex") -> int:
        """Counts the squares between the two hexagons, as the crow flies.

        Args:
            other: The hexagon to measure to.

        Returns:
            The cube distance: it says nothing about the cost of the trip, only about the spacing.
        """
        q, r, s = self._position()
        other_q, other_r, other_s = other._position()
        return max(abs(q - other_q), abs(r - other_r), abs(s - other_s))

    def cost_from(self, origin: "Hex") -> Optional[Fraction]:
        """Computes the movement points a ground unit spends to enter this hexagon.

        Args:
            origin: The hexagon the unit comes from.

        Returns:
            The cost as an exact fraction, or `None` if the passage is forbidden.
        """
        if not self.is_on_map or not origin.is_on_map:
            return None

        # On the map, the elements always start with the main terrain.
        elements = self.elements
        terrain = elements[0]
        if terrain in IMPASSABLE:
            return None
        if terrain == "montagne" and origin.terrain not in MOUNTAIN_ACCESS:
            if not WAY_COSTS.keys() & set(elements):
                return None

        # A way is only followed when already on it: joining a road first pays for the terrain.
        origin_elements = set(origin.elements)
        for way, cost in WAY_COSTS.items():
            if way in elements and way in origin_elements:
                return cost

        return COSTS.get(terrain, ORDINARY_COST)

    def reach(self, movement: Fraction | int = DEFAULT_MOVEMENT,
              enemies: Collection[str] = (),
              under_control: Collection[str] = ()) -> dict[str, Fraction]:
        """Walks the map within `movement` points and says what each hexagon reached costs.

        A Dijkstra walk over terrain costs, in exact fractions: a road is worth a third of a point,
        and five thirds must not drift. A unit standing on terrain it cannot occupy goes nowhere.

        The cost is what the walk found to be the cheapest way there, and it is what a unit
        spending from a budget must be charged: `moves` is this, its keys only.

        Args:
            movement: The movement budget, in points. A fraction where a unit has already spent
                part of its allowance this phase (`tenebrae/engine/movement_register.py`).
            enemies: "q,r,s" keys of the squares held by the opponent, which are not entered.
            under_control: "q,r,s" keys covered by the opposing zones of control, entered at the
                terrain's rate but where the unit must stop.

        Returns:
            "q,r,s" -> the points spent getting there, this hexagon excepted.
        """
        q, r, _ = self._position()
        if not self.is_on_map or self.terrain in UNINHABITABLE:
            return {}

        budget = Fraction(movement)
        spent = {self.key: Fraction(0)}
        pending = [(Fraction(0), q, r, self)]
        while pending:
            cost_so_far, _, _, hexagon = heapq.heappop(pending)
            if cost_so_far > spent[hexagon.key]:
                continue
            # "It must stop as soon as it has entered": a controlled square is not left, except the
            # starting one, where the unit already stood.
            leaving_a_controlled_square = hexagon.key in under_control
            if leaving_a_controlled_square and hexagon != self:
                continue
            for neighbour in hexagon.neighbours():
                if neighbour.key in enemies:
                    continue
                # No passing from one zone of control to another without a free square between.
                if leaving_a_controlled_square and neighbour.key in under_control:
                    continue
                cost = neighbour.cost_from(hexagon)
                if cost is None:
                    continue
                total = cost_so_far + cost
                if total <= budget and total < spent.get(neighbour.key, budget + 1):
                    spent[neighbour.key] = total
                    neighbour_q, neighbour_r, _ = neighbour._position()
                    heapq.heappush(pending, (total, neighbour_q, neighbour_r, neighbour))

        del spent[self.key]
        return spent

    def moves(self, movement: Fraction | int = DEFAULT_MOVEMENT,
              enemies: Collection[str] = (),
              under_control: Collection[str] = ()) -> list["Hex"]:
        """Finds the hexagons reachable with `movement` points, this hexagon excepted.

        Args:
            movement: The movement budget, in points.
            enemies: "q,r,s" keys of the squares held by the opponent, which are not entered.
            under_control: "q,r,s" keys covered by the opposing zones of control, entered at the
                terrain's rate but where the unit must stop.

        Returns:
            The reachable hexagons, in no particular order.
        """
        return [Hex.from_key(key)
                for key in self.reach(movement, enemies, under_control)]

    def to_dict(self) -> dict[str, Optional[int] | Optional[str]]:
        """Serialises the hexagon for the browser's JSON.

        Returns:
            The three coordinates and the main terrain, all `None` for an empty hexagon.
        """
        if self.is_empty:
            return {"q": None, "r": None, "s": None, "terrain": None}
        return {"q": self.q, "r": self.r, "s": self.s, "terrain": self.terrain}

    def _position(self) -> tuple[int, int, int]:
        """Reads the coordinates where a position is needed, refusing an empty hexagon.

        Returns:
            `(q, r, s)`.

        Raises:
            ValueError: If the hexagon is empty.
        """
        if self.q is None or self.r is None or self.s is None:
            raise ValueError("this hexagon is empty: it has no position on the map")
        return self.q, self.r, self.s

    def __eq__(self, other: object) -> bool:
        """Two hexagons are equal when their coordinates are."""
        return isinstance(other, Hex) and (self.q, self.r, self.s) == (other.q, other.r, other.s)

    def __hash__(self) -> int:
        """Hashes on the coordinates, consistently with `__eq__`."""
        return hash((self.q, self.r, self.s))

    def __repr__(self) -> str:
        """The constructor call that rebuilds this hexagon."""
        if self.is_empty:
            return "Hex()"
        return f"Hex({self.q}, {self.r}, {self.s})"


def zone_of_control(hexagons: Iterable[Hex]) -> frozenset[str]:
    """Collects the squares these units hold under their control.

    "Each unit exerts a particular influence over the six squares surrounding the one it
    occupies." The occupied square itself is held, not controlled. Squares off the map are
    discarded; those another unit occupies are not, the caller already knows they cannot be
    entered.

    Args:
        hexagons: The squares occupied by the units exerting a zone of control.

    Returns:
        The controlled squares, as "q,r,s" keys.
    """
    controlled: set[str] = set()
    for hexagon in hexagons:
        controlled.update(neighbour.key for neighbour in hexagon.neighbours())
    return frozenset(controlled)
