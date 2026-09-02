"""The Hex class: coordinates, neighbourhood, terrain costs and moves."""

import json
from fractions import Fraction

import pytest

from tenebrae.engine import hexagon as engine_hexagon
from tenebrae.engine.hexagon import (DEFAULT_MOVEMENT, MAP, TRANSCRIBED_MAP, Hex, apply_fixes,
                                     read_fixes)

# Reference hexagons, read off the game map - the fixed transcription. If a future fix changes one
# of them, these engine will say so: another one must then be chosen, not the fix undone.
PLAIN = Hex(1, 26, -27)           # surrounded by six plains
WOODS = Hex(0, 11, -11)           # borders a plain
LAKE = Hex(4, 35, -39)
RIFT = Hex(9, -2, -7)
ROAD = Hex(2, 20, -22)            # of "route" terrain, and adjacent to another road
HILL = Hex(5, -2, -3)             # borders a massif
BARE_MOUNTAIN = Hex(4, -1, -3)    # with no road or path, adjacent to a plain
NORTH_WEST_CORNER = Hex(0, 0, 0)


def neighbour_such_that(hexagon, predicate):
    """Returns the first neighbour of `hexagon` that satisfies `predicate`."""
    for neighbour in hexagon.neighbours():
        if predicate(neighbour):
            return neighbour
    raise AssertionError(f"no neighbour of {hexagon} will do")


class TestConstruction:
    def test_the_three_coordinates(self):
        assert (Hex(3, -1, -2).q, Hex(3, -1, -2).r, Hex(3, -1, -2).s) == (3, -1, -2)

    def test_two_coordinates_are_enough(self):
        assert Hex(3, -1) == Hex(3, -1, -2)

    def test_an_empty_hexagon(self):
        empty = Hex()
        assert empty.is_empty
        assert repr(empty) == "Hex()"

    def test_inconsistent_coordinates_are_refused(self):
        with pytest.raises(ValueError, match="inconsistent"):
            Hex(3, -1, 5)

    def test_a_single_coordinate_is_refused(self):
        with pytest.raises(ValueError):
            Hex(3)

    def test_round_trip_through_the_key(self):
        assert Hex.from_key("13,-4,-9") == Hex(13, -4, -9)
        assert Hex(13, -4, -9).key == "13,-4,-9"

    def test_an_empty_hexagon_has_no_position(self):
        for operation in (lambda: Hex().key, lambda: Hex().neighbours(), lambda: Hex().terrain):
            with pytest.raises(ValueError, match="empty"):
                operation()

    def test_hexagons_serve_as_dictionary_keys(self):
        assert {Hex(1, 2, -3): "here"}[Hex(1, 2)] == "here"
        assert Hex(1, 2, -3) != Hex(2, 1, -3)
        assert Hex(1, 2, -3) != "1,2,-3"


class TestMap:
    def test_the_map_is_read_in_full(self):
        assert len(MAP) == 2280

    def test_the_game_map_has_the_transcription_hexagons(self):
        """A fix changes a terrain; it neither adds nor removes a hexagon."""
        assert MAP.keys() == TRANSCRIBED_MAP.keys()

    def test_the_terrain_leads_the_elements(self):
        assert WOODS.terrain == "bois"
        assert WOODS.elements[0] == WOODS.terrain

    def test_a_hexagon_off_the_map_has_no_terrain(self):
        outside = Hex(99, 0, -99)
        assert not outside.is_on_map
        assert outside.terrain is None
        assert outside.elements == ()

    def test_six_neighbours_at_the_centre_of_the_map(self):
        assert len(PLAIN.neighbours()) == 6

    def test_fewer_neighbours_at_the_edge(self):
        assert len(NORTH_WEST_CORNER.neighbours()) == 2

    def test_the_neighbours_are_all_on_the_map(self):
        for neighbour in PLAIN.neighbours():
            assert neighbour.is_on_map

    def test_neighbourhood_is_reciprocal(self):
        for neighbour in PLAIN.neighbours():
            assert PLAIN in neighbour.neighbours()


class TestDistance:
    """The distance as the crow flies, which says nothing about the cost of the trip."""

    def test_a_hexagon_is_at_zero_from_itself(self):
        assert PLAIN.distance(PLAIN) == 0

    def test_the_neighbours_are_one_square_away(self):
        for neighbour in PLAIN.neighbours():
            assert PLAIN.distance(neighbour) == 1

    def test_it_is_symmetric(self):
        assert PLAIN.distance(LAKE) == LAKE.distance(PLAIN)

    def test_it_ignores_the_terrain(self):
        """The lake is impassable; it is no further away for all that."""
        assert LAKE.distance(PLAIN) == max(abs(LAKE.q - PLAIN.q), abs(LAKE.r - PLAIN.r),
                                           abs(LAKE.s - PLAIN.s))

    def test_it_holds_off_the_map(self):
        assert NORTH_WEST_CORNER.distance(Hex(99, 0, -99)) == 99

    def test_an_empty_hexagon_has_no_distance(self):
        with pytest.raises(ValueError):
            PLAIN.distance(Hex())


class TestCosts:
    def test_the_plain_costs_one_point(self):
        assert PLAIN.cost_from(neighbour_such_that(PLAIN, lambda n: True)) == 1

    def test_the_woods_cost_two_points(self):
        assert WOODS.cost_from(neighbour_such_that(WOODS, lambda n: n.terrain == "plaine")) == 2

    def test_following_a_road_costs_a_third_of_a_point(self):
        other = neighbour_such_that(ROAD, lambda n: "route" in n.elements)
        assert other.cost_from(ROAD) == Fraction(1, 3)

    def test_joining_a_road_is_paid_at_the_terrain_rate(self):
        """The booklet: the unit first pays for the terrain separating it from the road."""
        off_road = neighbour_such_that(ROAD, lambda n: "route" not in n.elements)
        assert ROAD.cost_from(off_road) == 1

    def test_the_lake_and_the_rift_are_impassable(self):
        for forbidden in (LAKE, RIFT):
            assert forbidden.cost_from(neighbour_such_that(forbidden, lambda n: True)) is None

    def test_the_mountain_refuses_entry_from_the_plain(self):
        plain = neighbour_such_that(BARE_MOUNTAIN, lambda n: n.terrain == "plaine")
        assert BARE_MOUNTAIN.cost_from(plain) is None

    def test_the_mountain_is_entered_from_the_hill(self):
        mountain = neighbour_such_that(HILL, lambda n: n.terrain == "montagne")
        assert mountain.cost_from(HILL) == 1

    def test_a_hexagon_off_the_map_has_no_cost(self):
        assert Hex(99, 0, -99).cost_from(PLAIN) is None
        assert PLAIN.cost_from(Hex(99, 0, -99)) is None


class TestMoves:
    def test_a_single_point_leads_to_the_passable_neighbours(self):
        reached = PLAIN.moves(1)
        assert set(reached) == set(PLAIN.neighbours())

    def test_the_woods_are_out_of_reach_with_one_point(self):
        origin = neighbour_such_that(WOODS, lambda n: n.terrain == "plaine")
        assert WOODS not in origin.moves(1)
        assert WOODS in origin.moves(2)

    def test_the_origin_is_not_in_the_result(self):
        assert PLAIN not in PLAIN.moves()

    def test_no_impassable_terrain_is_reached(self):
        for hexagon in PLAIN.moves():
            assert hexagon.terrain not in {"lac", "riviere", "faille", "fort", "chateau"}

    def test_one_does_not_move_from_uninhabitable_terrain(self):
        """A ground unit stands neither in a lake, nor in a river, nor in the rift."""
        assert LAKE.moves() == []
        assert RIFT.moves() == []

    def test_every_reached_square_really_is_within_reach(self):
        """A step-by-step path must link the origin to each returned square."""
        budget = Fraction(DEFAULT_MOVEMENT)
        reached = {hexagon: None for hexagon in PLAIN.moves()}
        spent = {PLAIN: Fraction(0)}
        pending = [PLAIN]
        while pending:
            current = pending.pop()
            for neighbour in current.neighbours():
                cost = neighbour.cost_from(current)
                if cost is None:
                    continue
                total = spent[current] + cost
                if total <= budget and total < spent.get(neighbour, budget + 1):
                    spent[neighbour] = total
                    pending.append(neighbour)
        del spent[PLAIN]
        assert set(reached) == set(spent)

    def test_the_road_carries_further_than_the_plain(self):
        assert len(ROAD.moves()) > len(PLAIN.moves())

    def test_the_returned_hexagons_are_unique_and_on_the_map(self):
        reached = PLAIN.moves()
        assert len(set(reached)) == len(reached)
        assert all(hexagon.is_on_map for hexagon in reached)

    def test_the_default_movement_is_five(self):
        assert DEFAULT_MOVEMENT == 5
        assert PLAIN.moves() == PLAIN.moves(5)

    def test_a_zero_movement_leads_nowhere(self):
        assert PLAIN.moves(0) == []


class TestConversion:
    def test_the_dict_describes_the_hexagon(self):
        assert PLAIN.to_dict() == {"q": 1, "r": 26, "s": -27, "terrain": "plaine"}

    def test_the_dict_of_an_empty_hexagon(self):
        assert Hex().to_dict() == {"q": None, "r": None, "s": None, "terrain": None}

    def test_the_dict_goes_through_json(self):
        rendered = json.dumps([hexagon.to_dict() for hexagon in PLAIN.moves()])
        assert json.loads(rendered)[0]["terrain"]


class TestFixes:
    """The overlay of `tenebrae/game_box/map_fix.json` onto the transcription."""

    TRANSCRIBED = {
        "0,0,0": ("plaine",),
        "1,0,-1": ("bois", "route"),
        "1,-1,0": ("plaine", "chemin"),
    }

    def test_a_fix_replaces_the_main_terrain(self):
        game_map = apply_fixes(self.TRANSCRIBED, {"0,0,0": "colline"})
        assert game_map["0,0,0"] == ("colline",)

    def test_the_secondary_elements_survive(self):
        """Fixing a wood on the black road must not cut the road it was hiding."""
        game_map = apply_fixes(self.TRANSCRIBED, {"1,0,-1": "colline"})
        assert game_map["1,0,-1"] == ("colline", "route")

    def test_the_fixed_terrain_does_not_appear_twice(self):
        """The path of a plain fixed into a path does not duplicate the main terrain."""
        game_map = apply_fixes(self.TRANSCRIBED, {"1,-1,0": "chemin"})
        assert game_map["1,-1,0"] == ("chemin",)

    def test_the_unfixed_hexagons_do_not_move(self):
        game_map = apply_fixes(self.TRANSCRIBED, {"0,0,0": "lac"})
        assert game_map["1,0,-1"] == self.TRANSCRIBED["1,0,-1"]

    def test_a_key_off_the_map_is_ignored(self):
        game_map = apply_fixes(self.TRANSCRIBED, {"99,0,-99": "lac"})
        assert game_map.keys() == self.TRANSCRIBED.keys()

    def test_the_transcription_is_not_modified(self):
        apply_fixes(self.TRANSCRIBED, {"0,0,0": "lac"})
        assert self.TRANSCRIBED["0,0,0"] == ("plaine",)

    def test_a_map_without_fixes_is_the_transcription(self):
        assert apply_fixes(self.TRANSCRIBED, {}) == self.TRANSCRIBED

    def test_the_fix_acts_on_movement(self, monkeypatch):
        """A plain fixed into a lake becomes impassable."""
        neighbour = neighbour_such_that(PLAIN, lambda hexagon: hexagon.terrain == "plaine")
        assert neighbour in PLAIN.moves()

        monkeypatch.setitem(engine_hexagon.MAP, neighbour.key, ("lac",))
        assert neighbour not in PLAIN.moves()

    def test_a_missing_file_fixes_nothing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(engine_hexagon, "FIXES_PATH", tmp_path / "map_fix.json")
        assert read_fixes() == {}

    def test_the_fixes_are_read_from_the_file(self, tmp_path, monkeypatch):
        path = tmp_path / "map_fix.json"
        path.write_text(json.dumps({"1,26,-27": "lac"}), encoding="utf-8")
        monkeypatch.setattr(engine_hexagon, "FIXES_PATH", path)

        game_map = apply_fixes(TRANSCRIBED_MAP, read_fixes())
        assert game_map["1,26,-27"][0] == "lac"
        assert TRANSCRIBED_MAP["1,26,-27"][0] == "plaine"
