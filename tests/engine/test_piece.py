"""The piece catalogue: the values read off the counters, and the movement drawn from them."""

import json

import pytest

from tenebrae.engine.hexagon import Hex
from tenebrae.engine.piece import (ALLIANCE, BOX, CATALOGUE, DARKNESS, MOTIONLESS, NEUTRAL, SIDES, Piece,
                                   piece, read_catalogue)

RAM = "yzent-05-1-belier"                       # strength 10, movement 2
INFANTRY = "empire-01-26-infanteries"           # 4 and 4, the most common value
CAVALRY = "reissland-02-8-cavaleries"           # 8 points: cavalry goes far
BAT = "conjurations-01-6-chauves-souris"        # ground movement illegible, flight (2)
DRAGON = "dragons-01-pions-de-dragons-trois-couleurs"
MARKER = "marqueurs-03-paralysie"
SHEET = "magiciens-01-pions-de-magiciens-vue-d-ensemble"


class TestCatalogue:
    def test_the_hundred_and_twenty_seven_photographs_are_there(self):
        assert len(CATALOGUE) == 127

    def test_the_key_is_the_image_name(self):
        for key, read in CATALOGUE.items():
            assert read.image.endswith(f"{key}.jpg")

    def test_every_image_exists(self):
        """`image` is relative to the repository root: "game_box/pions/...`."""
        root = BOX.parent
        for read in CATALOGUE.values():
            assert (root / read.image).exists(), read

    def test_an_unknown_piece_does_not_pass(self):
        with pytest.raises(KeyError):
            piece("piece-that-does-not-exist")

    def test_the_catalogue_can_be_reread_on_demand(self):
        """Reading is a pure function: two calls give the same values."""
        reread = read_catalogue()
        assert reread.keys() == CATALOGUE.keys()
        assert reread[RAM].to_dict() == CATALOGUE[RAM].to_dict()


class TestValuesRead:
    def test_the_counter_values(self):
        infantry = piece(INFANTRY)
        assert (infantry.strength, infantry.movement) == (4, 4)
        assert (infantry.fire, infantry.range) == (None, None)
        assert infantry.symbol == "infanterie"

    def test_an_archer_carries_its_firing_values(self):
        archer = piece("elfes-02-4-archers")
        assert (archer.strength, archer.movement, archer.fire, archer.range) == (8, 4, 8, 3)

    def test_a_special_ability_is_a_letter(self):
        assert piece("empire-de-lynn-02-10-cavaleries-de-puissance-10").special_abilities == "P"
        assert piece(DRAGON).special_abilities == "s"

    def test_values_absent_from_the_counter_are_none(self):
        marker = piece(MARKER)
        assert (marker.strength, marker.movement, marker.fire) == (None, None, None)
        assert marker.special_abilities == "PA"

    def test_an_incomplete_reading_is_reported(self):
        """The bat's ground movement is not legible: `remarks` says so."""
        bat = piece(BAT)
        assert bat.movement is None
        assert "lisible" in bat.remarks


class TestUnits:
    def test_a_unit_carries_values(self):
        assert piece(INFANTRY).is_a_unit
        assert piece(BAT).is_a_unit

    def test_a_marker_is_not_a_unit(self):
        assert not piece(MARKER).is_a_unit
        assert not piece(SHEET).is_a_unit

    def test_the_box_holds_a_hundred_and_fifteen_units(self):
        """127 photographs, minus the 6 markers, the 2 record sheets and the 4 overviews."""
        assert sum(1 for read in CATALOGUE.values() if read.is_a_unit) == 115


class TestSides:
    """The side breakdown of `game_box/pions/README.md`, faction by faction."""

    def test_every_piece_has_a_side(self):
        for read in CATALOGUE.values():
            assert read.side in (ALLIANCE, DARKNESS, NEUTRAL), read

    def test_every_faction_in_the_box_is_filed(self):
        assert {read.faction for read in CATALOGUE.values()} <= SIDES.keys()

    def test_the_two_sides_of_the_game(self):
        assert piece("elfes-01-5-infanteries").side == ALLIANCE
        assert piece(INFANTRY).side == ALLIANCE          # Tharque Empire
        assert piece("orques-01-15-infanteries").side == DARKNESS
        assert piece(RAM).side == DARKNESS               # Yzent, ally of convenience
        assert piece("machines-de-siege-01-juggernaut").side == DARKNESS

    def test_the_neutrals(self):
        assert piece(BAT).side == NEUTRAL                # a conjuration
        assert piece("volants-01-5-infanteries").side == NEUTRAL
        assert piece(MARKER).side == NEUTRAL

    def test_the_breakdown_of_the_box(self):
        """56 Darkness pieces, 47 Alliance, 24 neutral - including the 12 that are not pieces."""
        sides = [read.side for read in CATALOGUE.values()]
        assert (sides.count(DARKNESS), sides.count(ALLIANCE), sides.count(NEUTRAL)) == (56, 47, 24)


class TestZoneOfControlExerted:
    def test_a_unit_of_a_side_exerts_one(self):
        assert piece(INFANTRY).exerts_a_zone_of_control
        assert piece("orques-01-15-infanteries").exerts_a_zone_of_control

    def test_a_marker_exerts_none(self):
        assert not piece(MARKER).exerts_a_zone_of_control
        assert not piece(SHEET).exerts_a_zone_of_control

    def test_a_neutral_exerts_none(self):
        assert not piece(BAT).exerts_a_zone_of_control

    def test_the_booklet_exceptions_are_not_applied(self):
        """Leaders, demons and undead exert one here: see `engine/README.md`."""
        assert piece("elfes-06-1-leader").exerts_a_zone_of_control
        assert piece("demons-01-5-infanteries").exerts_a_zone_of_control
        assert piece("morts-vivants-01-20-unites-de-squelettes").exerts_a_zone_of_control


class TestMovementPoints:
    def test_the_movement_read_off_the_counter(self):
        assert piece(RAM).movement_points == 2
        assert piece(INFANTRY).movement_points == 4
        assert piece(CAVALRY).movement_points == 8

    def test_flight_serves_for_want_of_ground_movement(self):
        assert piece(BAT).movement_points == 2

    def test_ground_movement_prevails_over_flight(self):
        dragon = piece(DRAGON)
        assert (dragon.movement, dragon.flight_movement) == (5, 15)
        assert dragon.movement_points == 5

    def test_what_carries_no_value_does_not_move(self):
        assert piece(MARKER).movement_points == MOTIONLESS == 0
        assert piece(SHEET).movement_points == MOTIONLESS

    def test_every_unit_has_something_to_move_with(self):
        for read in CATALOGUE.values():
            if read.is_a_unit:
                assert read.movement_points > 0, read

    def test_no_far_fetched_movement(self):
        """The slowest does 1 point, the fastest 20: beyond that, it is a misreading."""
        for read in CATALOGUE.values():
            assert 0 <= read.movement_points <= 20, read


class TestMoves:
    """What the piece's movement changes about its reach, on the game map."""

    PLAIN = Hex(1, 26, -27)

    def test_the_slow_piece_goes_less_far_than_the_fast_one(self):
        slow = self.PLAIN.moves(piece(RAM).movement_points)
        fast = self.PLAIN.moves(piece(CAVALRY).movement_points)
        assert 0 < len(slow) < len(fast)

    def test_a_marker_goes_nowhere(self):
        assert self.PLAIN.moves(piece(MARKER).movement_points) == []


class TestRendering:
    def test_the_dict_goes_through_json(self):
        rendered = json.loads(json.dumps(piece(RAM).to_dict()))
        assert rendered["key"] == RAM
        assert rendered["movement_points"] == 2
        assert rendered["side"] == DARKNESS
        assert rendered["image"].startswith("game_box/pions/")

    def test_the_repr_states_the_movement(self):
        assert repr(piece(RAM)) == "Piece('yzent-05-1-belier', 2 MP)"

    def test_a_piece_is_built_from_values(self):
        """The constructor reads the French field names of `pions.json`."""
        values = {"image": CATALOGUE[RAM].image, "faction": CATALOGUE[RAM].faction,
                  "force": CATALOGUE[RAM].strength, "mouvement": CATALOGUE[RAM].movement,
                  "tir": CATALOGUE[RAM].fire, "portee": CATALOGUE[RAM].range,
                  "mouvement_vol": CATALOGUE[RAM].flight_movement,
                  "facultes_speciales": CATALOGUE[RAM].special_abilities,
                  "symbole": CATALOGUE[RAM].symbol, "remarques": CATALOGUE[RAM].remarks}
        assert Piece("trial", values).movement_points == 2
