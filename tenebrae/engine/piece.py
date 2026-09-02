"""The pieces of Ave Tenebrae: what is printed on them, and what movement takes from it.

`tenebrae/game_box/pions/pions.json` carries, for each of the 127 photographs in
`tenebrae/game_box/pions/`, the values read by eye off the counter - strength, movement, fire,
range, flight, special ability (see `tenebrae/game_box/pions/README.md`). The file is read once,
when the module is imported, and the result is held to be constant: the pieces were printed in 1986,
they do not change mid-game.

Its field names are in French, like every data file in the box, and they are read as such here;
only the code around them is English.

The engine currently uses just one of those values, movement, which replaces the flat 5 points
moves used to be computed on. The rest is loaded anyway: strength and fire will serve in combat.

The side, on the other hand, is not in `pions.json`: it is not printed on the counter. It comes
from the side breakdown in `tenebrae/game_box/pions/README.md`, held here in `SIDES`, and serves
to know who opposes whom - hence which zones of control are exerted against whom.
"""

import json
from pathlib import Path

BOX = Path(__file__).resolve().parent.parent / "game_box"
CATALOGUE_PATH = BOX / "pions" / "pions.json"

# Movement of a piece that carries none: a marker does not move by itself.
MOTIONLESS = 0

# The three sides. The neutral one is nobody's opponent: it neither exerts a zone of control nor
# suffers one. The values are those of the data files and of the saved game, and stay in French.
ALLIANCE, DARKNESS, NEUTRAL = "alliance", "tenebres", "neutre"

# The side of each faction, after the "Camps" section of `tenebrae/game_box/pions/README.md`.
# Directories with no units - record sheets, markers, overviews - are neutral for want of anything
# better: nothing in them fights.
SIDES = {
    "01-yzent": DARKNESS,             # the Magiocrat's ally of convenience
    "02-reissland": ALLIANCE,
    "03-empire": ALLIANCE,
    "04-templiers": ALLIANCE,
    "05-population": ALLIANCE,
    "06-empire-de-lynn": ALLIANCE,    # scenario 3
    "07-chaos": DARKNESS,
    "08-non-humains": DARKNESS,
    "09-elfes": ALLIANCE,
    "10-nains": ALLIANCE,             # scenario 4
    "11-orques": DARKNESS,
    "12-sahuaguins": DARKNESS,
    "13-dragons": ALLIANCE,
    "14-morts-vivants": DARKNESS,
    "15-demons": DARKNESS,
    "16-volants": NEUTRAL,            # scenario 5
    "17-conjurations": NEUTRAL,
    "18-machines-de-siege": DARKNESS,  # the Juggernaut
    "19-magiciens": NEUTRAL,
    "20-marqueurs": NEUTRAL,
    "21-vues-d-ensemble": NEUTRAL,
}

# Who opposes whom. The neutral side does not appear: it has no opponent.
OPPONENTS = {ALLIANCE: DARKNESS, DARKNESS: ALLIANCE}


class Piece:
    """A piece from the box, designated by the name of its photograph without directory or
    extension.

    Values absent from the counter - or illegible on the photograph - are `None`; `remarks` then
    says what is missing. Only `movement_points` commits, because movement needs a number.
    """

    __slots__ = ("key", "image", "faction", "strength", "movement", "fire", "range",
                 "flight_movement", "special_abilities", "symbol", "remarks")

    def __init__(self, key, values):
        self.key = key
        self.image = values["image"]
        self.faction = values["faction"]
        self.strength = values["force"]
        self.movement = values["mouvement"]
        self.fire = values["tir"]
        self.range = values["portee"]
        self.flight_movement = values["mouvement_vol"]
        self.special_abilities = values["facultes_speciales"]
        self.symbol = values["symbole"]
        self.remarks = values["remarques"]

    @property
    def is_a_unit(self):
        """Says whether the piece is a unit, and not a marker or a photograph that is not a piece.

        A unit carries at least one numeric value: the markers (`PA`, `D`, flames, mist, ruins,
        breach), the two record sheets and the four overviews carry none.
        """
        return any(value is not None
                   for value in (self.strength, self.movement, self.flight_movement))

    @property
    def movement_points(self):
        """The piece's movement budget, in points.

        The ground movement read off the counter, with two exceptions: a piece that only has a
        flight movement moves by that number for want of anything better - flight is not a rule of
        its own yet - and whatever carries no value at all does not move.
        """
        if self.movement is not None:
            return self.movement
        if self.flight_movement is not None:
            return self.flight_movement
        return MOTIONLESS

    @property
    def side(self):
        """The side of its faction: `ALLIANCE`, `DARKNESS` or `NEUTRAL` (see `SIDES`)."""
        return SIDES[self.faction]

    @property
    def exerts_a_zone_of_control(self):
        """Says whether the piece holds the six squares surrounding it under its control.

        Every unit of a side does. Markers exert nothing since they are not units, and neutrals
        do not either for want of an opponent. The booklet further exempts leaders, spellcasters,
        demons and ordinary undead: those exceptions are not applied, they are recorded in
        `tenebrae/engine/README.md`.
        """
        return self.is_a_unit and self.side != NEUTRAL

    def to_dict(self):
        """The piece in a form directly convertible to JSON for the browser."""
        return {"key": self.key, "image": self.image, "faction": self.faction,
                "side": self.side,
                "strength": self.strength, "movement": self.movement, "fire": self.fire,
                "range": self.range, "flight_movement": self.flight_movement,
                "special_abilities": self.special_abilities, "symbol": self.symbol,
                "remarks": self.remarks,
                "movement_points": self.movement_points}

    def __repr__(self):
        return f"Piece({self.key!r}, {self.movement_points} MP)"


def read_catalogue(path=CATALOGUE_PATH):
    """Returns "key -> Piece" for everything `pions.json` carries, markers and overviews included."""
    with Path(path).open(encoding="utf-8") as source:
        return {key: Piece(key, values) for key, values in json.load(source).items()}


# Every piece in the box, including what is not one: sorting is up to the caller, through
# `is_a_unit`.
CATALOGUE = read_catalogue()


def piece(key):
    """The piece with key `key`; `KeyError` if the box does not know it."""
    return CATALOGUE[key]
