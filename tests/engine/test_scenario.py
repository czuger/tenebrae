"""The scenarios fixed in `tenebrae/scenarios/`: what they contain, and the board they yield.

These engine keep the placement consistent with the map: a terrain fix that would put a unit in a
lake would show up here, and not mid-game.
"""

import json

import pytest

from tenebrae.engine import scenario as engine_scenario
from tenebrae.engine.hexagon import MAP, UNINHABITABLE, Hex
from tenebrae.engine.phase import Turn
from tenebrae.engine.piece import ALLIANCE, CATALOGUE, DARKNESS
from tenebrae.engine.scenario import (BOOKLET_SCENARIOS, SCENARIOS, Scenario, available_scenarios,
                                      compose, enabled_scenarios, next_number, path_for, read,
                                      recompose, scenario, slug)

from tests.engine.plains import well_surrounded_plain

WAR_OF_THE_DWARVES = 4
FORBIDDEN_TERRAINS = UNINHABITABLE | {"montagne"}

# The dwarf front line, as it was asked for: the infantry holds it at one end, the phalanxes extend
# it to the other. The engine redraw it rather than copy it out - it is the line that is the
# instruction, not the seven keys it crosses.
START_OF_THE_LINE = "50,-7,-43"
END_OF_THE_LINE = "45,-8,-37"


@pytest.fixture(scope="module")
def war_of_the_dwarves():
    return scenario(WAR_OF_THE_DWARVES)


class TestScenarioCatalogue:
    def test_the_directory_is_at_the_repository_root(self):
        assert SCENARIOS.is_dir()
        assert SCENARIOS.name == "scenarios"

    def test_only_the_scenarios_that_are_fixed_can_be_asked_for(self):
        """No. 4 is the one fixed to date; the booklet's others have no file yet."""
        assert WAR_OF_THE_DWARVES in available_scenarios()
        with pytest.raises(KeyError):
            scenario(99)

    def test_every_file_reads(self):
        for path in available_scenarios().values():
            assert isinstance(read(path), Scenario)


class TestWarOfTheDwarves:
    def test_it_introduces_itself(self, war_of_the_dwarves):
        assert war_of_the_dwarves.number == WAR_OF_THE_DWARVES
        assert war_of_the_dwarves.name == "La guerre des nains"
        assert "ave_tenebrae_regles_fr.md" in war_of_the_dwarves.source

    def test_it_lasts_until_one_side_is_exterminated(self, war_of_the_dwarves):
        """The booklet sets no number of turns: the file carries none."""
        assert war_of_the_dwarves.max_turns is None

    def test_two_armies_face_to_face(self, war_of_the_dwarves):
        assert [army["armee"] for army in war_of_the_dwarves.armies] == ["Nains", "Orques"]
        assert war_of_the_dwarves.sides == (ALLIANCE, DARKNESS)
        assert [army["joueur"] for army in war_of_the_dwarves.armies] == [1, 2]

    def test_the_announced_numbers_are_those_actually_placed(self, war_of_the_dwarves):
        """18 dwarves, 30 orcs: both armies minus what the engine cannot play."""
        placed = list(war_of_the_dwarves.placement.values())
        for army in war_of_the_dwarves.armies:
            faction = "10-nains" if army["armee"] == "Nains" else "11-orques"
            counted = sum(1 for key in placed if CATALOGUE[key].faction == faction)
            assert counted == army["unites"]
        assert [army["unites"] for army in war_of_the_dwarves.armies] == [18, 30]
        assert len(war_of_the_dwarves) == 48

    def test_the_dwarf_army_is_there_without_its_leaders_or_its_mage(self, war_of_the_dwarves):
        """5 infantry, 4 crossbowmen, 4 heavy crossbowmen, 5 phalanxes - fighting units only."""
        assert count(war_of_the_dwarves, "10-nains") == {
            "nains-01-5-infanteries": 5,
            "nains-02-4-arbaletriers": 4,
            "nains-03-4-arbaletriers-lourds": 4,
            "nains-04-5-phalanges": 5,
        }

    def test_the_orc_army_is_there_without_its_reinforcements_or_its_leader(self,
                                                                            war_of_the_dwarves):
        """"Ignore the reinforcements": the three reinforcement photographs stay in the box."""
        assert count(war_of_the_dwarves, "11-orques") == {
            "orques-01-15-infanteries": 15,
            "orques-02-5-cavaleries": 5,
            "orques-03-5-archers": 5,
            "orques-04-5-archers-montes-a-cheval": 5,
        }

    def test_neither_leader_nor_spellcaster_is_placed(self, war_of_the_dwarves):
        """Only the units the engine can play are placed.

        Both sides' leaders and the mage Vorgtd stay in the box: the engine gives them no effect -
        neither command nor spell - and a unit that does nothing more than another clutters the
        battle line. Both sides therefore fight on equal terms, by counter and by terrain.
        """
        placed = set(war_of_the_dwarves.placement.values())
        assert not [key for key in placed if "leader" in key or "mage" in key]
        assert all(army["jeteur_de_sorts"] is None for army in war_of_the_dwarves.armies)

    def test_no_other_faction_comes_into_play(self, war_of_the_dwarves):
        factions = {CATALOGUE[key].faction for key in war_of_the_dwarves.placement.values()}
        assert factions == {"10-nains", "11-orques"}

    def test_each_sides_magic_potential_is_noted(self, war_of_the_dwarves):
        """"The mage Vorgtd (45)" and "a minor necromancer (20 magic points)".

        Both numbers stay noted even though no spellcaster is placed any more: they come from the
        booklet, and they are what will have to be spent the day magic is played.
        """
        assert [army["magie"] for army in war_of_the_dwarves.armies] == [45, 20]

    def test_each_anchor_is_held(self, war_of_the_dwarves):
        """The anchor is no longer the centre of a circle but the starting point of the
        deployment: the first hexagon of the dwarf line, and the Orcreich fort for the orcs. Both
        are occupied - an army does not deploy from an empty square."""
        anchors = [army["ancre"] for army in war_of_the_dwarves.armies]
        assert anchors == [START_OF_THE_LINE, "51,-13,-38"]
        assert war_of_the_dwarves.placement[START_OF_THE_LINE] == "nains-01-5-infanteries"
        assert war_of_the_dwarves.placement["51,-13,-38"] == "orques-01-15-infanteries"
        assert MAP["51,-13,-38"][0] == "fort"

    def test_the_dwarf_infantry_holds_the_requested_line(self, war_of_the_dwarves):
        """The instruction: a line from (50,-7,-43) to (45,-8,-37), infantry first, phalanxes
        next. The five infantry units hold it from the first end, the two phalanxes extend it to
        the second - the line is occupied end to end, with no gap."""
        segment = cube_line(Hex.from_key(START_OF_THE_LINE), Hex.from_key(END_OF_THE_LINE))
        placed = [war_of_the_dwarves.placement.get(square.key) for square in segment]
        assert placed == ["nains-01-5-infanteries"] * 5 + ["nains-04-5-phalanges"] * 2

    def test_the_dwarf_crossbowmen_are_behind(self, war_of_the_dwarves):
        """"Crossbowmen behind": not one of them is as close to the orcs as the least contact unit
        - the missile arm stays under cover behind the infantry and the phalanxes."""
        orcs = squares_of(war_of_the_dwarves, "11-orques")
        contact = distances(war_of_the_dwarves, orcs, "nains-01", "nains-04")
        rear = distances(war_of_the_dwarves, orcs, "nains-02", "nains-03")
        assert len(contact) == 10 and len(rear) == 8
        assert min(rear) > max(contact)

    def test_the_orc_infantry_faces_the_dwarves(self, war_of_the_dwarves):
        """"The infantry faces the dwarves": everything the dwarves have in front of them is
        infantry - neither archer nor cavalryman is placed closer than it."""
        dwarves = squares_of(war_of_the_dwarves, "10-nains")
        for square, key in war_of_the_dwarves.placement.items():
            if CATALOGUE[key].faction != "11-orques":
                continue
            if min(Hex.from_key(square).distance(dwarf) for dwarf in dwarves) <= 4:
                assert "infanteries" in key, square

    def test_the_orc_archers_are_grouped_behind(self, war_of_the_dwarves):
        """"The archers grouped behind": the ten of them - on foot and mounted - form a single
        block, and not one of them is ahead of the infantry."""
        dwarves = squares_of(war_of_the_dwarves, "10-nains")
        archers = [Hex.from_key(square) for square, key in war_of_the_dwarves.placement.items()
                   if "archers" in key]
        assert len(archers) == 10
        assert in_one_block(archers)
        infantry = distances(war_of_the_dwarves, dwarves, "orques-01")
        assert min(square.distance(dwarf) for square in archers for dwarf in dwarves) \
            >= min(infantry)

    def test_all_the_orc_cavalry_is_on_the_lake_shore(self, war_of_the_dwarves):
        """"The cavalry, all at the top near the lake": the five of them border the water, and are
        alone in bordering it - that is what tells them apart from the mounted archers just behind
        them."""
        lake = [Hex.from_key(square) for square, elements in MAP.items()
                if elements[0] == "lac"]
        on_the_shore = {square for square, key in war_of_the_dwarves.placement.items()
                        if min(Hex.from_key(square).distance(water) for water in lake) == 1}
        assert on_the_shore == {square for square, key in war_of_the_dwarves.placement.items()
                                if key == "orques-02-5-cavaleries"}
        assert len(on_the_shore) == 5

    def test_each_army_is_in_one_block(self, war_of_the_dwarves):
        """A massed army: each unit touches at least one other of its side."""
        for faction in ("10-nains", "11-orques"):
            assert in_one_block(squares_of(war_of_the_dwarves, faction)), faction

    def test_the_two_armies_are_not_yet_in_contact(self, war_of_the_dwarves):
        """They face each other a few squares apart: the first turn is for marching, not
        fighting."""
        dwarves = squares_of(war_of_the_dwarves, "10-nains")
        orcs = squares_of(war_of_the_dwarves, "11-orques")
        assert min(dwarf.distance(orc) for dwarf in dwarves for orc in orcs) == 3


class TestPlacementOnTheMap:
    def test_every_unit_stands_on_a_square_it_can_stand_on(self, war_of_the_dwarves):
        """On the map, and not in a lake, a river, the rift or a mountain.

        That no two units share a square needs no test: the placement is a dictionary keyed by
        square, so stacking is impossible by construction.
        """
        for square in war_of_the_dwarves.placement:
            assert square in MAP
            assert MAP[square][0] not in FORBIDDEN_TERRAINS, square

    def test_every_piece_exists_in_the_box(self, war_of_the_dwarves):
        for key in war_of_the_dwarves.placement.values():
            assert key in CATALOGUE
            assert CATALOGUE[key].is_a_unit


class TestScenarioBoard:
    def test_the_board_carries_every_unit_on_its_square(self, war_of_the_dwarves):
        board = war_of_the_dwarves.board()
        assert len(board) == len(war_of_the_dwarves)
        for square, key in war_of_the_dwarves.placement.items():
            assert board.piece_on(Hex.from_key(square)).key == key

    def test_the_sides_oppose_each_other_on_the_board(self, war_of_the_dwarves):
        board = war_of_the_dwarves.board()
        assert len(board.squares_held_by(ALLIANCE)) == 18
        assert len(board.opponents_of(ALLIANCE)) == 30

    def test_each_board_is_fresh(self, war_of_the_dwarves):
        """Two games do not share their pieces: moving one does not move the other."""
        first, second = war_of_the_dwarves.board(), war_of_the_dwarves.board()
        square = Hex.from_key(next(iter(war_of_the_dwarves.placement)))
        first.remove(square)
        assert second.piece_on(square) is not None

    def test_the_whole_army_can_march(self, war_of_the_dwarves):
        """No unit is placed in a dead end: each has at least one square to go to."""
        board = war_of_the_dwarves.board()
        for square in war_of_the_dwarves.placement:
            assert board.moves(Hex.from_key(square)), square


def squares_of(read_scenario, faction):
    """The squares occupied by this faction."""
    return [Hex.from_key(square) for square, key in read_scenario.placement.items()
            if CATALOGUE[key].faction == faction]


def count(read_scenario, faction):
    """"piece key -> number of copies placed" for this faction."""
    counts = {}
    for key in read_scenario.placement.values():
        if CATALOGUE[key].faction == faction:
            counts[key] = counts.get(key, 0) + 1
    return counts


def distances(read_scenario, targets, *fragments):
    """The distances to `targets` of the units whose key contains one of the `fragments`.

    The fragments are given prefixed with their faction ("nains-01" and not "infanteries"): both
    sides have infantry, and too short a fragment would catch the other side's.
    """
    return [min(Hex.from_key(square).distance(target) for target in targets)
            for square, key in read_scenario.placement.items()
            if any(fragment in key for fragment in fragments)]


def in_one_block(squares):
    """Says whether these hexagons form a single block: they are walked step by step."""
    reached, pending = {squares[0]}, [squares[0]]
    while pending:
        square = pending.pop()
        for neighbour in squares:
            if neighbour not in reached and square.distance(neighbour) == 1:
                reached.add(neighbour)
                pending.append(neighbour)
    return len(reached) == len(squares)


def cube_line(origin, destination):
    """The hexagons crossed going from `origin` to `destination` in a straight line.

    The interpolation is done on the three cube coordinates, then rounding restores `q + r + s = 0`
    by correcting whichever drifted most - the usual line drawing on a hexagonal grid. Here it
    serves to reread the deployment instruction: we were only given the two ends, and it is the
    line between them that has to be recovered.
    """
    steps = origin.distance(destination)
    drawn = []
    for step in range(steps + 1):
        t = step / steps
        floating = [start + (end - start) * t for start, end
                    in ((origin.q, destination.q), (origin.r, destination.r),
                        (origin.s, destination.s))]
        rounded = [round(value) for value in floating]
        drifts = [abs(rounded_value - floating_value)
                  for rounded_value, floating_value in zip(rounded, floating)]
        drifted = drifts.index(max(drifts))
        rounded[drifted] = -sum(rounded[index] for index in range(3) if index != drifted)
        drawn.append(Hex(*rounded))
    return drawn


# --- Composing a scenario -------------------------------------------------------------------------
#
# The engine assembles the values of a new file from a placement (`compose`): the armies derived
# from the pieces placed, the next free number, the file named as `available_scenarios` reads it.
# The directory is diverted to an empty temporary one: nothing here touches `tenebrae/scenarios/`.


INFANTRY, CROSSBOWMEN = "nains-01-5-infanteries", "nains-02-4-arbaletriers"
ORC_INFANTRY = "orques-01-15-infanteries"
ELF_INFANTRY = "elfes-01-5-infanteries"
FIRE_MARKER = "marqueurs-01-feu-mur-de-flammes"


@pytest.fixture
def scenarios_directory(tmp_path, monkeypatch):
    """Diverts the scenarios directory to an empty temporary one, and returns it."""
    monkeypatch.setattr(engine_scenario, "SCENARIOS", tmp_path)
    return tmp_path


@pytest.fixture
def plain_squares():
    """Three squares of bare plain, side by side: a centre and two of its neighbours."""
    centre = well_surrounded_plain()
    first, second = centre.neighbours()[:2]
    return centre.key, first.key, second.key


class TestNumberingAndNaming:
    def test_the_number_comes_after_the_booklets_and_the_files_present(self, scenarios_directory):
        """The booklet's five stay reserved even when their files do not exist yet."""
        assert next_number() == BOOKLET_SCENARIOS + 1
        (scenarios_directory / "scenario-07-essai.json").write_text("{}")
        assert next_number() == 8

    def test_the_real_directory_gives_a_free_number(self):
        assert next_number() > BOOKLET_SCENARIOS
        assert next_number() not in available_scenarios()

    def test_the_slug_drops_accents_and_apostrophes(self):
        assert slug("La guerre des nains") == "la-guerre-des-nains"
        assert slug("L'aube des Ténèbres !") == "l-aube-des-tenebres"
        assert slug("???") == ""

    def test_the_file_is_named_as_the_catalogue_reads_it(self, scenarios_directory):
        path = path_for(6, "L'aube des Ténèbres")
        assert path == scenarios_directory / "scenario-06-l-aube-des-tenebres.json"
        path.write_text("{}")
        assert available_scenarios() == {6: path}

    def test_a_title_without_a_slug_still_names_a_file(self, scenarios_directory):
        assert path_for(7, "???").name == "scenario-07-sans-titre.json"


class TestComposingAScenario:
    def test_the_armies_are_derived_from_the_pieces_placed(self, scenarios_directory,
                                                           plain_squares):
        first, second, third = plain_squares
        values = compose("Essai", {first: ORC_INFANTRY, second: INFANTRY, third: CROSSBOWMEN},
                         max_turns=12, source="test")

        assert values["numero"] == BOOKLET_SCENARIOS + 1
        assert values["nom"] == "Essai"
        assert values["source"] == "test"
        assert values["nombre_de_tours"] == 12
        assert values["armees"] == [
            {"joueur": 1, "camp": ALLIANCE, "armee": "Nains", "consigne": None, "ancre": None,
             "unites": 2, "magie": None, "jeteur_de_sorts": None},
            {"joueur": 2, "camp": DARKNESS, "armee": "Orques", "consigne": None, "ancre": None,
             "unites": 1, "magie": None, "jeteur_de_sorts": None},
        ]

    def test_the_placement_is_written_side_by_side(self, scenarios_directory, plain_squares):
        """The alliance first, then the darkness, whatever the order of placing."""
        first, second, third = plain_squares
        values = compose("Essai", {first: ORC_INFANTRY, second: INFANTRY, third: CROSSBOWMEN})
        assert list(values["placement"].items()) == [(second, INFANTRY), (third, CROSSBOWMEN),
                                                     (first, ORC_INFANTRY)]

    def test_several_factions_on_a_side_name_the_army_together(self, scenarios_directory,
                                                               plain_squares):
        first, second, _ = plain_squares
        values = compose("Essai", {first: INFANTRY, second: ELF_INFANTRY})
        assert [army["armee"] for army in values["armees"]] == ["Elfes et Nains"]
        assert values["armees"][0]["unites"] == 2

    def test_neutral_pieces_are_placed_but_belong_to_no_army(self, scenarios_directory,
                                                             plain_squares):
        first, second, _ = plain_squares
        values = compose("Essai", {first: FIRE_MARKER, second: INFANTRY})
        assert [(army["camp"], army["unites"]) for army in values["armees"]] == [(ALLIANCE, 1)]
        assert list(values["placement"]) == [second, first]

    def test_no_turn_limit_unless_one_is_given(self, scenarios_directory, plain_squares):
        first, _, _ = plain_squares
        assert compose("Essai", {first: INFANTRY})["nombre_de_tours"] is None

    def test_a_placement_without_a_side_is_refused(self, scenarios_directory, plain_squares):
        """A turn needs a side to play it: markers alone make no scenario, nor does nothing."""
        first, _, _ = plain_squares
        with pytest.raises(ValueError):
            compose("Essai", {first: FIRE_MARKER})
        with pytest.raises(ValueError):
            compose("Essai", {})

    def test_a_square_off_the_map_is_refused(self, scenarios_directory):
        with pytest.raises(ValueError):
            compose("Essai", {"999,0,-999": INFANTRY})

    def test_an_unknown_piece_is_refused(self, scenarios_directory, plain_squares):
        first, _, _ = plain_squares
        with pytest.raises(KeyError):
            compose("Essai", {first: "nains-99-inconnu"})

    def test_the_composed_scenario_reads_back_and_plays(self, scenarios_directory, plain_squares):
        """Written as it is, the file is one the engine reads and lays out like the booklet's."""
        first, second, third = plain_squares
        values = compose("L'essai", {first: ORC_INFANTRY, second: INFANTRY, third: CROSSBOWMEN},
                         max_turns=12)
        path = path_for(values["numero"], values["nom"])
        path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")

        composed = scenario(values["numero"])
        assert composed.name == "L'essai"
        assert composed.max_turns == 12
        assert composed.sides == (ALLIANCE, DARKNESS)
        assert len(composed) == 3
        board = composed.board()
        assert len(board.squares_held_by(ALLIANCE)) == 2
        assert len(board.opponents_of(ALLIANCE)) == 1
        turn = Turn(composed.sides, {army["camp"]: army["armee"] for army in composed.armies})
        assert turn.label == "Phase de mouvement — Nains"


# --- Recomposing a scenario -----------------------------------------------------------------------
#
# The engine assembles an existing scenario's values again from a new placement (`recompose`): the
# number and the source kept, the armies derived anew, what was written into them by hand carried
# over for every side still present.


def a_fixed_scenario(first, second):
    """A scenario as a booklet file fixes it: an instruction, an anchor and a magic potential in
    each army, a dwarf on `first`, an orc on `second`."""
    return Scenario({
        "numero": 7, "nom": "La guerre des nains", "source": "le livret", "nombre_de_tours": 10,
        "armees": [
            {"joueur": 1, "camp": ALLIANCE, "armee": "Nains", "consigne": "Au sud du volcan.",
             "ancre": first, "unites": 1, "magie": 45, "jeteur_de_sorts": None},
            {"joueur": 2, "camp": DARKNESS, "armee": "Orques", "consigne": "Dans l'Orcreich.",
             "ancre": second, "unites": 1, "magie": 20, "jeteur_de_sorts": "Vorgtd"}],
        "placement": {first: INFANTRY, second: ORC_INFANTRY}})


class TestRecompose:
    def test_the_number_and_the_source_are_kept(self, scenarios_directory, plain_squares):
        """Even when the directory would give another number: the scenario stays itself."""
        first, second, third = plain_squares
        values = recompose(a_fixed_scenario(first, second), "Autre titre",
                           {third: INFANTRY, second: ORC_INFANTRY}, 20)
        assert values["numero"] == 7
        assert values["source"] == "le livret"
        assert values["nom"] == "Autre titre"
        assert values["nombre_de_tours"] == 20
        assert values["placement"] == {third: INFANTRY, second: ORC_INFANTRY}

    def test_what_was_written_by_hand_is_kept_for_a_side_still_present(
            self, scenarios_directory, plain_squares):
        """The instruction, the anchor, the magic potential and the spellcaster: what the map
        cannot give; the count of units and the army's name: what it gives, derived anew."""
        first, second, third = plain_squares
        values = recompose(a_fixed_scenario(first, second), "Essai",
                           {first: INFANTRY, third: CROSSBOWMEN, second: ORC_INFANTRY})
        dwarves, orcs = values["armees"]
        assert dwarves == {
            "joueur": 1, "camp": ALLIANCE, "armee": "Nains", "consigne": "Au sud du volcan.",
            "ancre": first, "unites": 2, "magie": 45, "jeteur_de_sorts": None}
        assert orcs["consigne"] == "Dans l'Orcreich."
        assert orcs["jeteur_de_sorts"] == "Vorgtd"
        assert orcs["unites"] == 1

    def test_a_side_that_left_loses_its_entry(self, scenarios_directory, plain_squares):
        first, second, _ = plain_squares
        values = recompose(a_fixed_scenario(first, second), "Essai", {first: INFANTRY})
        assert [army["camp"] for army in values["armees"]] == [ALLIANCE]
        assert values["armees"][0]["joueur"] == 1

    def test_a_side_that_arrives_gets_a_fresh_entry(self, scenarios_directory, plain_squares):
        """Nothing written by hand for it: what the map cannot give stays `null`."""
        first, second, third = plain_squares
        existing = Scenario({"numero": 8, "nom": "Nains seuls", "source": "",
                             "armees": [{"joueur": 1, "camp": ALLIANCE, "armee": "Nains",
                                         "consigne": "Ici.", "ancre": first, "unites": 1,
                                         "magie": 45, "jeteur_de_sorts": None}],
                             "placement": {first: INFANTRY}})
        values = recompose(existing, "Essai", {first: INFANTRY, third: ORC_INFANTRY})
        dwarves, orcs = values["armees"]
        assert dwarves["consigne"] == "Ici."
        assert orcs == {
            "joueur": 2, "camp": DARKNESS, "armee": "Orques", "consigne": None, "ancre": None,
            "unites": 1, "magie": None, "jeteur_de_sorts": None}

    def test_the_placement_is_written_side_by_side(self, scenarios_directory, plain_squares):
        first, second, third = plain_squares
        values = recompose(a_fixed_scenario(first, second), "Essai",
                           {second: ORC_INFANTRY, third: FIRE_MARKER, first: INFANTRY})
        assert list(values["placement"]) == [first, second, third]

    def test_a_placement_without_a_side_is_refused(self, scenarios_directory, plain_squares):
        first, second, _ = plain_squares
        with pytest.raises(ValueError):
            recompose(a_fixed_scenario(first, second), "Essai", {first: FIRE_MARKER})
        with pytest.raises(ValueError):
            recompose(a_fixed_scenario(first, second), "Essai", {"999,0,-999": INFANTRY})


# --- Enabled and disabled scenarios -------------------------------------------------------------
#
# `"enabled": false`, written by hand into a file, withdraws a scenario from the ones a new game
# can be opened on. The field is absent from every file written before it existed: absent means
# enabled, and nothing had to be added to the files already fixed.


def write_a_scenario(number, name="Essai", **fields):
    """Writes a minimal readable scenario file, with whatever fields the test adds to it."""
    values = {"numero": number, "nom": name, "source": "test", "nombre_de_tours": None,
              "armees": [{"joueur": 1, "camp": ALLIANCE, "armee": "Nains"}],
              "placement": {}, **fields}
    path = path_for(number, name)
    path.write_text(json.dumps(values, ensure_ascii=False), encoding="utf-8")
    return path


class TestTheEnabledField:
    def test_a_file_without_the_field_is_enabled(self, scenarios_directory):
        """Every scenario fixed before the field existed goes on being offered."""
        path = write_a_scenario(6)
        assert "enabled" not in json.loads(path.read_text(encoding="utf-8"))
        assert read(path).enabled is True

    @pytest.mark.parametrize("written, expected", [(True, True), (False, False)])
    def test_the_field_is_read_as_it_is_written(self, scenarios_directory, written, expected):
        path = write_a_scenario(6, enabled=written)
        assert read(path).enabled is expected

    def test_the_fixed_files_are_all_offered(self):
        """In the real directory: nothing is disabled in the repository as it stands."""
        assert enabled_scenarios().keys() == available_scenarios().keys()

    def test_only_the_enabled_ones_are_offered(self, scenarios_directory):
        write_a_scenario(6, name="Offert")
        write_a_scenario(7, name="Retire", enabled=False)

        assert list(available_scenarios()) == [6, 7]
        assert list(enabled_scenarios()) == [6]
        assert enabled_scenarios()[6].name == "Offert"

    def test_the_files_are_read_again_at_every_call(self, scenarios_directory):
        """Nothing is kept between two calls: a field just edited by hand is honoured."""
        write_a_scenario(6)
        assert list(enabled_scenarios()) == [6]

        write_a_scenario(6, enabled=False)
        assert list(enabled_scenarios()) == []


class TestTheEnabledFieldThroughAnEdit:
    def test_a_composed_scenario_is_enabled(self, scenarios_directory, plain_squares):
        first, _, _ = plain_squares
        assert compose("Essai", {first: INFANTRY})["enabled"] is True

    @pytest.mark.parametrize("written", [True, False])
    def test_recomposing_carries_the_field_through(self, scenarios_directory, plain_squares,
                                                   written):
        """A scenario disabled by hand and then edited on the map stays disabled."""
        first, second, _ = plain_squares
        path = write_a_scenario(6, enabled=written)

        values = recompose(read(path), "Essai", {first: INFANTRY, second: ORC_INFANTRY})
        assert values["enabled"] is written

    def test_a_file_without_the_field_gains_it_enabled_when_edited(self, scenarios_directory,
                                                                   plain_squares):
        first, _, _ = plain_squares
        path = write_a_scenario(6)
        assert recompose(read(path), "Essai", {first: INFANTRY})["enabled"] is True
