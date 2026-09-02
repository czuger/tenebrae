"""The hexagon grid of Ave Tenebrae and the moves it allows.

The game map is the transcription of the scan (`game_box/carte_details.json`) overlaid with the
fixes recorded by eye (`game_box/map_fix.json`). Both files are read once, when the module is
imported, and the result is held to be constant: the board was printed in 1986, it does not
change mid-game. Fixing the map therefore requires restarting the program.

Movement cost follows the booklet's *Terrain table*; the interpretation caveats are recorded in
`engine/README.md`. The movement budget itself comes from the piece: `engine.piece` reads it off
the counter, and `moves()` receives it as an argument. At this stage every unit is a ground unit:
no flight, no powers, no stacking beyond one piece per square.

Terrain names stay in French (`plaine`, `bois`, `montagne`, …): they are the vocabulary of the
transcribed data files, which are the source of truth and are not translated. Only the code around
them is English.
"""

import heapq
import json
from fractions import Fraction
from pathlib import Path

BOX = Path(__file__).resolve().parent.parent / "game_box"

# Every element of each hexagon, main terrain first. We read `carte_details.json` and not
# `carte.json`: the head of its list gives the same main terrain, but it alone keeps the 58 roads
# and paths that the map's priority rule hides under a wood or a massif.
with (BOX / "carte_details.json").open(encoding="utf-8") as source:
    TRANSCRIBED_MAP = {key: tuple(elements) for key, elements in json.load(source).items()}

# The fixes recorded by eye on /admin/map_fix: "q,r,s" -> main terrain. A separate file, kept by
# hand; the transcription itself comes out of the script and is never touched up.
FIXES_PATH = BOX / "map_fix.json"


def read_fixes():
    """The recorded fixes; an empty dict if the file does not exist."""
    try:
        with FIXES_PATH.open(encoding="utf-8") as source:
            return json.load(source)
    except FileNotFoundError:
        return {}


def apply_fixes(transcription, fixes):
    """The transcription overlaid with the fixes, without modifying it.

    A fix only bears on the main terrain: the fixed terrain takes the lead in place of the one the
    map's priority rule put there, and the secondary elements follow. That is what lets a wood
    fixed into a hill keep the road it was hiding. A key unknown to the transcription is ignored:
    we do not create hexagons off the map.
    """
    game_map = dict(transcription)
    for key, terrain in fixes.items():
        if key not in game_map:
            continue
        secondary = (element for element in game_map[key][1:] if element != terrain)
        game_map[key] = (terrain, *secondary)
    return game_map


# The fixes actually in force, and the map the game is played on. Recording one more fix does not
# change them: the program has to be restarted.
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

# Impassable to a ground unit: lakes and rivers (except bridges, not recorded on the map), the
# Rift of Tsaroth, forts and castles (except by combat or through allies).
IMPASSABLE = frozenset({"lac", "riviere", "faille", "fort", "chateau"})

# A mountain can only be entered from a hill, another mountain, or a way crossing it.
MOUNTAIN_ACCESS = frozenset({"colline", "montagne"})

# Terrains a ground unit cannot occupy, and therefore never departs from. Forts and castles are
# not among them: they are not crossed, but they can be garrisoned.
UNINHABITABLE = frozenset({"lac", "riviere", "faille"})

# Flat movement rate, for callers that do not say which piece they mean: counter values run from
# 1 to 20 points, and 5 is the value used before we started reading them (see `engine.piece`).
DEFAULT_MOVEMENT = 5


class Hex:
    """A hexagon of the map, in cube coordinates `q + r + s = 0`.

    Built from the three coordinates, from `q` and `r` alone - `s` follows - or from nothing at
    all: `Hex()` is an empty hexagon, with no position.
    """

    __slots__ = ("q", "r", "s")

    def __init__(self, q=None, r=None, s=None):
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
    def from_key(cls, key):
        """Builds a hexagon from a `carte.json` key, of the form "q,r,s"."""
        return cls(*(int(value) for value in key.split(",")))

    @property
    def is_empty(self):
        return self.q is None

    @property
    def key(self):
        """The "q,r,s" key under which the map knows this hexagon."""
        self._require_a_position()
        return f"{self.q},{self.r},{self.s}"

    @property
    def is_on_map(self):
        return not self.is_empty and self.key in MAP

    @property
    def elements(self):
        """Everything the hexagon carries, main terrain first; empty if it is off the map."""
        self._require_a_position()
        return MAP.get(self.key, ())

    @property
    def terrain(self):
        """The main terrain of the hexagon, or `None` if it is off the map."""
        elements = self.elements
        return elements[0] if elements else None

    def neighbours(self):
        """The six adjacent hexagons, reduced to those that are on the map."""
        self._require_a_position()
        neighbours = (Hex(self.q + dq, self.r + dr, self.s + ds) for dq, dr, ds in DIRECTIONS)
        return [neighbour for neighbour in neighbours if neighbour.is_on_map]

    def distance(self, other):
        """The number of squares between the two hexagons, as the crow flies.

        Cube distance: it says nothing about the cost of the trip, only about the spacing.
        """
        self._require_a_position()
        other._require_a_position()
        return max(abs(self.q - other.q), abs(self.r - other.r), abs(self.s - other.s))

    def cost_from(self, origin):
        """Movement points to enter this hexagon coming from `origin`.

        Returns `None` if the passage is forbidden to a ground unit.
        """
        if not self.is_on_map or not origin.is_on_map:
            return None

        elements, terrain = self.elements, self.terrain
        if terrain in IMPASSABLE:
            return None
        if terrain == "montagne" and origin.terrain not in MOUNTAIN_ACCESS:
            if not WAY_COSTS.keys() & set(elements):
                return None

        # Following a way is only worth it when already on it: a unit joining the road first pays
        # for the terrain that separates it from the road.
        origin_elements = set(origin.elements)
        for way, cost in WAY_COSTS.items():
            if way in elements and way in origin_elements:
                return cost

        return COSTS.get(terrain, ORDINARY_COST)

    def moves(self, movement=DEFAULT_MOVEMENT, enemies=(), under_control=()):
        """The hexagons reachable with `movement` points, this hexagon excepted.

        A Dijkstra walk over terrain costs. Costs are exact fractions: a road is worth a third of
        a point, and five thirds must not drift. A unit standing on terrain it cannot occupy - a
        lake, a river, the rift - goes nowhere.

        `enemies` and `under_control` are sets of "q,r,s" keys: the squares held by the opponent,
        which are not entered, and those covered by its zones of control, which are entered at the
        terrain's rate but where the unit must stop. Without them the map is held to be free of
        opponents and the walk knows nothing but terrain.
        """
        self._require_a_position()
        if not self.is_on_map or self.terrain in UNINHABITABLE:
            return []

        budget = Fraction(movement)
        spent = {self.key: Fraction(0)}
        pending = [(Fraction(0), self.q, self.r, self)]
        while pending:
            cost_so_far, _, _, hexagon = heapq.heappop(pending)
            if cost_so_far > spent[hexagon.key]:
                continue
            # "It must stop as soon as it has entered": a unit does not leave a controlled square
            # - except the one it starts from, where it was already standing on the previous turn.
            leaving_a_controlled_square = hexagon.key in under_control
            if leaving_a_controlled_square and hexagon != self:
                continue
            for neighbour in hexagon.neighbours():
                if neighbour.key in enemies:
                    continue
                # "One cannot pass from one zone of control to another without having left the
                # first": leaving a controlled square requires a free square.
                if leaving_a_controlled_square and neighbour.key in under_control:
                    continue
                cost = neighbour.cost_from(hexagon)
                if cost is None:
                    continue
                total = cost_so_far + cost
                if total <= budget and total < spent.get(neighbour.key, budget + 1):
                    spent[neighbour.key] = total
                    heapq.heappush(pending, (total, neighbour.q, neighbour.r, neighbour))

        del spent[self.key]
        return [Hex.from_key(key) for key in spent]

    def to_dict(self):
        """The hexagon in a form directly convertible to JSON for the browser."""
        if self.is_empty:
            return {"q": None, "r": None, "s": None, "terrain": None}
        return {"q": self.q, "r": self.r, "s": self.s, "terrain": self.terrain}

    def _require_a_position(self):
        if self.is_empty:
            raise ValueError("this hexagon is empty: it has no position on the map")

    def __eq__(self, other):
        return isinstance(other, Hex) and (self.q, self.r, self.s) == (other.q, other.r, other.s)

    def __hash__(self):
        return hash((self.q, self.r, self.s))

    def __repr__(self):
        if self.is_empty:
            return "Hex()"
        return f"Hex({self.q}, {self.r}, {self.s})"


def zone_of_control(hexagons):
    """The squares these units hold under their control, as "q,r,s" keys.

    "Each unit exerts a particular influence over the six squares surrounding the one it
    occupies." The occupied square itself is not part of it: it is held, not controlled. Squares
    off the map are discarded; those another unit occupies are not, the caller already knows they
    cannot be entered.
    """
    controlled = set()
    for hexagon in hexagons:
        controlled.update(neighbour.key for neighbour in hexagon.neighbours())
    return frozenset(controlled)
