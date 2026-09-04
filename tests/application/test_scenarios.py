"""The admin routes that compose and edit a scenario, without a browser.

No test writes into `tenebrae/scenarios/`: the `scenarios_directory` fixture diverts the engine's
directory to an empty temporary one, so that every scenario saved here is the sixth - the first
after the booklet's five. The scenario edited is one `fixed_scenario` writes there beforehand.
"""

import json
import re

import pytest

from tenebrae.application.grid import GRID_MATRIX, GRID_ORIGIN, PIECE_SIZE
from tenebrae.application.pieces import PIECE_CATALOGUE
from tenebrae.engine import scenario as engine_scenario
from tenebrae.engine.hexagon import MAP, UNINHABITABLE, Hex
from tenebrae.engine.piece import ALLIANCE, DARKNESS
from tenebrae.engine.scenario import BOOKLET_SCENARIOS

from tests.application.test_board_browser import expected_centre
from tests.application.test_connection import OTHER_PLAYER
from tests.application.test_server import read_hidden_field

INFANTRY, ORC_INFANTRY = "nains-01-5-infanteries", "orques-01-15-infanteries"
CROSSBOWMEN = "nains-02-4-arbaletriers"
FIRE_MARKER = "marqueurs-01-feu-mur-de-flammes"
FIRST_NUMBER = BOOKLET_SCENARIOS + 1

# The scenario `fixed_scenario` writes: a booklet-like file, with fields written by hand.
FIXED_NUMBER = 7
FIXED_FILE = f"scenario-{FIXED_NUMBER:02d}-la-guerre-des-nains.json"

# The middle of map.jpg (6173 x 5102), in its pixels: squares near it are far from the toolbar and
# from the palette, where a click in the browser would not reach the map.
MAP_CENTRE = (3086, 2551)


@pytest.fixture
def scenarios_directory(tmp_path, monkeypatch):
    """Diverts the scenarios directory to an empty temporary one, and returns it."""
    monkeypatch.setattr(engine_scenario, "SCENARIOS", tmp_path)
    return tmp_path


def distance_to_the_centre(key):
    """How far a square's centre is from the middle of the map, in map.jpg pixels."""
    hexagon = Hex.from_key(key)
    x, y = expected_centre(hexagon.q, hexagon.r)
    return (x - MAP_CENTRE[0]) ** 2 + (y - MAP_CENTRE[1]) ** 2


def nearest_the_centre(terrain):
    """The square of a given main terrain closest to the middle of the map."""
    return min((key for key, elements in MAP.items() if elements[0] == terrain),
               key=distance_to_the_centre)


@pytest.fixture
def plain_squares():
    """Three squares of bare plain near the middle of the map: a centre and two neighbours."""
    centre = min((key for key, elements in MAP.items() if elements == ("plaine",)),
                 key=distance_to_the_centre)
    neighbours = [neighbour.key for neighbour in Hex.from_key(centre).neighbours()
                  if MAP[neighbour.key] == ("plaine",)]
    assert len(neighbours) >= 2, "no bare plain around the middle of the map"
    return centre, neighbours[0], neighbours[1]


def a_lake():
    """A lake square near the middle of the map."""
    return nearest_the_centre("lac")


@pytest.fixture
def fixed_scenario(scenarios_directory, plain_squares):
    """Writes a scenario no. 7 in the diverted directory - a dwarf and an orc, an instruction, an
    anchor and a magic potential in each army - and returns its values."""
    first, second, _ = plain_squares
    values = {
        "numero": FIXED_NUMBER, "nom": "La guerre des nains", "source": "le livret",
        "nombre_de_tours": 10,
        "armees": [
            {"joueur": 1, "camp": ALLIANCE, "armee": "Nains", "consigne": "Au sud du volcan.",
             "ancre": first, "unites": 1, "magie": 45, "jeteur_de_sorts": None},
            {"joueur": 2, "camp": DARKNESS, "armee": "Orques", "consigne": "Dans l'Orcreich.",
             "ancre": second, "unites": 1, "magie": 20, "jeteur_de_sorts": None}],
        "placement": {first: INFANTRY, second: ORC_INFANTRY}}
    (scenarios_directory / FIXED_FILE).write_text(
        json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return values


def update(client, placement, number=FIXED_NUMBER, name="La guerre des nains", max_turns=10):
    return client.post(f"/admin/scenarios/{number}/edit",
                       json={"name": name, "max_turns": max_turns, "placement": placement})


def save(client, placement, name="Essai", max_turns=None):
    return client.post("/admin/scenarios",
                       json={"name": name, "max_turns": max_turns, "placement": placement})


def files_in(directory):
    return sorted(path.name for path in directory.glob("*.json"))


def read_back(directory, filename):
    return json.loads((directory / filename).read_text(encoding="utf-8"))


# --- The page ---


def test_the_page_offers_every_piece_of_the_box(client, scenarios_directory):
    """The display catalogue - not the overviews -, in the shape of the board's placed units."""
    pieces = read_hidden_field(client.get("/admin/scenarios").get_data(as_text=True), "pieces")
    assert [piece["key"] for piece in pieces] == [piece["key"] for piece in PIECE_CATALOGUE]
    assert all("image" in piece and "path" not in piece for piece in pieces)
    assert pieces[0]["image"] == PIECE_CATALOGUE[0]["path"]
    assert {"name", "side", "faction"} <= set(pieces[0])


def test_the_page_carries_the_grid_alignment_and_the_piece_size(client, scenarios_directory):
    grid = read_hidden_field(client.get("/admin/scenarios").get_data(as_text=True), "grid")
    assert grid == {"origin": GRID_ORIGIN, "matrix": GRID_MATRIX, "piece_size": PIECE_SIZE}


def test_the_page_carries_the_fixed_map_and_its_forbidden_squares(client, scenarios_directory):
    """The map the game is played on, fixes applied, and the squares no unit can occupy."""
    page = client.get("/admin/scenarios").get_data(as_text=True)
    hexagons = read_hidden_field(page, "hexagons")
    forbidden = read_hidden_field(page, "forbidden")
    assert hexagons == {key: elements[0] for key, elements in MAP.items()}
    assert set(forbidden) == {key for key, elements in MAP.items()
                              if elements[0] in UNINHABITABLE}
    assert forbidden


# --- Who may ---


def test_the_page_is_refused_to_an_ordinary_player(application, seat_the_player,
                                                   scenarios_directory):
    client = application.test_client()
    seat_the_player(application, client, identity=OTHER_PLAYER, sides=[DARKNESS])

    assert client.get("/admin/scenarios").status_code == 403
    answer = client.post("/admin/scenarios", json={})
    assert answer.status_code == 403
    assert "ADMIN_DISCORD_IDS" in answer.json["message"]
    assert files_in(scenarios_directory) == []


def test_the_page_is_open_to_an_administrator(client, scenarios_directory):
    assert client.get("/admin/scenarios").status_code == 200


# --- Saving ---


def test_saving_writes_a_new_file_in_the_engines_format(client, scenarios_directory,
                                                        plain_squares):
    first, second, _ = plain_squares
    answer = save(client, {first: INFANTRY, second: ORC_INFANTRY}, name="L'essai", max_turns=12)

    assert answer.status_code == 200
    assert answer.get_json() == {"saved": True, "number": FIRST_NUMBER, "name": "L'essai",
                                 "file": f"scenario-{FIRST_NUMBER:02d}-l-essai.json",
                                 "units": 2}
    assert files_in(scenarios_directory) == [f"scenario-{FIRST_NUMBER:02d}-l-essai.json"]

    values = read_back(scenarios_directory, answer.get_json()["file"])
    assert values["numero"] == FIRST_NUMBER
    assert values["nom"] == "L'essai"
    assert "/admin/scenarios" in values["source"]
    assert values["nombre_de_tours"] == 12
    assert [army["camp"] for army in values["armees"]] == [ALLIANCE, DARKNESS]
    assert values["placement"] == {first: INFANTRY, second: ORC_INFANTRY}
    # `tir` is absent on both infantry counters: it contributes zero beside their `force`.
    assert values["total_points_alliance"] == 12
    assert values["total_points_tenebres"] == 8


def test_attack_totals_add_strength_and_fire_and_default_an_absent_side_to_zero(
        client, scenarios_directory, plain_squares):
    first, second, _ = plain_squares
    answer = save(client, {first: INFANTRY, second: CROSSBOWMEN})

    values = read_back(scenarios_directory, answer.get_json()["file"])
    # Dwarf infantry has force 12 and no ranged attack; crossbowmen have force 6 and tir 4.
    assert values["total_points_alliance"] == 12 + 6 + 4
    assert values["total_points_tenebres"] == 0


def test_the_saved_scenario_is_one_the_engine_plays(client, scenarios_directory, plain_squares):
    first, second, _ = plain_squares
    save(client, {first: INFANTRY, second: ORC_INFANTRY}, max_turns=12)

    composed = engine_scenario.scenario(FIRST_NUMBER)
    assert composed.max_turns == 12
    assert composed.sides == (ALLIANCE, DARKNESS)
    assert len(composed.board()) == 2


def test_the_file_is_laid_out_like_the_fixed_ones(client, scenarios_directory, plain_squares):
    """Two-space indent, accents kept, a final newline: the same as the files fixed by hand."""
    first, _, _ = plain_squares
    save(client, {first: INFANTRY}, name="Ténèbres")

    text = (scenarios_directory / files_in(scenarios_directory)[0]).read_text(encoding="utf-8")
    assert text.endswith("}\n")
    assert '\n  "nom": "Ténèbres",\n' in text


def test_each_save_is_a_new_scenario(client, scenarios_directory, plain_squares):
    first, _, _ = plain_squares
    save(client, {first: INFANTRY}, name="Un")
    answer = save(client, {first: INFANTRY}, name="Un")

    assert answer.get_json()["number"] == FIRST_NUMBER + 1
    assert files_in(scenarios_directory) == [f"scenario-{FIRST_NUMBER:02d}-un.json",
                                             f"scenario-{FIRST_NUMBER + 1:02d}-un.json"]


def test_an_undetermined_number_of_turns_is_null(client, scenarios_directory, plain_squares):
    """`null`, an empty string or nothing at all: the file says `null` for each."""
    first, _, _ = plain_squares
    save(client, {first: INFANTRY}, max_turns=None)
    save(client, {first: INFANTRY}, max_turns="")
    client.post("/admin/scenarios", json={"name": "Essai", "placement": {first: INFANTRY}})

    assert [read_back(scenarios_directory, name)["nombre_de_tours"]
            for name in files_in(scenarios_directory)] == [None, None, None]


def test_the_squares_are_normalised(client, scenarios_directory, plain_squares):
    """A key given by `q` and `r` alone is written with its `s`."""
    first, _, _ = plain_squares
    q, r, _ = first.split(",")
    save(client, {f"{q},{r}": INFANTRY})
    assert read_back(scenarios_directory, files_in(scenarios_directory)[0])["placement"] == {
        first: INFANTRY}


# --- Refusals: a French message, and no file written ---


def refused(client, scenarios_directory, fragment, **body):
    answer = client.post("/admin/scenarios", json=body)
    assert answer.status_code == 400
    assert answer.get_json()["saved"] is False
    assert fragment in answer.get_json()["message"]
    assert files_in(scenarios_directory) == []


def test_a_scenario_needs_a_name(client, scenarios_directory, plain_squares):
    first, _, _ = plain_squares
    refused(client, scenarios_directory, "nom", placement={first: INFANTRY})
    refused(client, scenarios_directory, "nom", name="   ", placement={first: INFANTRY})


@pytest.mark.parametrize("turns", [0, -3, "douze", 2.5, True])
def test_the_number_of_turns_is_a_positive_integer(client, scenarios_directory, plain_squares,
                                                   turns):
    first, _, _ = plain_squares
    refused(client, scenarios_directory, "tours", name="Essai", max_turns=turns,
            placement={first: INFANTRY})


@pytest.mark.parametrize("placement", [{}, "rien", None])
def test_a_scenario_needs_a_placement(client, scenarios_directory, placement):
    refused(client, scenarios_directory, "au moins un pion", name="Essai", placement=placement)


def test_an_unknown_piece_is_refused(client, scenarios_directory, plain_squares):
    first, _, _ = plain_squares
    refused(client, scenarios_directory, "Pion inconnu", name="Essai",
            placement={first: "nains-99-inconnu"})
    refused(client, scenarios_directory, "Pion inconnu", name="Essai", placement={first: 12})


def test_an_overview_is_not_a_piece(client, scenarios_directory, plain_squares):
    """In the box's catalogue, but not on the palette: the page never offers it."""
    first, _, _ = plain_squares
    refused(client, scenarios_directory, "Pion inconnu", name="Essai",
            placement={first: "magiciens-01-pions-de-magiciens-vue-d-ensemble"})


def test_a_square_off_the_map_or_unreadable_is_refused(client, scenarios_directory):
    refused(client, scenarios_directory, "n'est pas sur la carte", name="Essai",
            placement={"999,0,-999": INFANTRY})
    refused(client, scenarios_directory, "illisible", name="Essai",
            placement={"a,b,c": INFANTRY})


def test_a_square_no_unit_can_occupy_is_refused(client, scenarios_directory):
    lake = a_lake()
    refused(client, scenarios_directory, f"{lake} (lac)", name="Essai",
            placement={lake: INFANTRY})


def test_a_placement_without_a_side_is_refused(client, scenarios_directory, plain_squares):
    """Markers alone make no scenario: a turn needs a side to play it."""
    first, _, _ = plain_squares
    refused(client, scenarios_directory, "Alliance", name="Essai",
            placement={first: FIRE_MARKER})


# --- Editing: the page opened on a scenario, and its file rewritten ---


def test_the_page_lists_the_scenarios_on_file(client, fixed_scenario):
    scenarios = read_hidden_field(client.get("/admin/scenarios").get_data(as_text=True),
                                  "scenarios")
    assert scenarios == [{"number": FIXED_NUMBER, "name": "La guerre des nains",
                          "file": FIXED_FILE, "enabled": True}]


def test_composing_carries_no_scenario_and_saves_as_a_new_file(client, scenarios_directory):
    page = client.get("/admin/scenarios").get_data(as_text=True)
    assert read_hidden_field(page, "scenarios") == []
    assert '<input type="hidden" id="scenario" value="">' in page
    assert 'data-url="/admin/scenarios"' in page
    assert "composer un scénario" in page


def test_the_edit_page_carries_the_scenario_and_saves_into_its_file(client, fixed_scenario):
    page = client.get(f"/admin/scenarios/{FIXED_NUMBER}/edit").get_data(as_text=True)
    assert read_hidden_field(page, "scenario") == {
        "number": FIXED_NUMBER, "name": "La guerre des nains", "max_turns": 10,
        "enabled": True, "placement": fixed_scenario["placement"]}
    assert f'data-url="/admin/scenarios/{FIXED_NUMBER}/edit"' in page
    assert f"modifier le scénario n° {FIXED_NUMBER}" in page
    # The same page, the same palette and map.
    assert read_hidden_field(page, "pieces") == read_hidden_field(
        client.get("/admin/scenarios").get_data(as_text=True), "pieces")
    assert re.search(r'<select id="chooser"', page)


def test_a_number_no_file_has_is_404(client, fixed_scenario, scenarios_directory, plain_squares):
    first, _, _ = plain_squares
    answer = client.get("/admin/scenarios/99/edit")
    assert answer.status_code == 404
    assert "n° 99" in answer.get_json()["message"]

    answer = update(client, {first: INFANTRY}, number=99)
    assert answer.status_code == 404
    assert answer.get_json()["saved"] is False
    assert files_in(scenarios_directory) == [FIXED_FILE]


def test_editing_is_refused_to_an_ordinary_player(application, seat_the_player, fixed_scenario,
                                                  scenarios_directory, plain_squares):
    first, _, _ = plain_squares
    client = application.test_client()
    seat_the_player(application, client, identity=OTHER_PLAYER, sides=[DARKNESS])

    assert client.get(f"/admin/scenarios/{FIXED_NUMBER}/edit").status_code == 403
    assert update(client, {first: CROSSBOWMEN}).status_code == 403
    assert read_back(scenarios_directory, FIXED_FILE) == fixed_scenario


def test_updating_rewrites_the_file_in_place(client, fixed_scenario, scenarios_directory,
                                             plain_squares):
    """The number and the source stay, the placement and the turns are replaced, the units
    recounted; what the armies carried by hand is kept."""
    first, second, third = plain_squares
    answer = update(client, {first: INFANTRY, third: CROSSBOWMEN, second: ORC_INFANTRY},
                    max_turns=20)

    assert answer.status_code == 200
    assert answer.get_json() == {"saved": True, "number": FIXED_NUMBER,
                                 "name": "La guerre des nains", "file": FIXED_FILE, "units": 3}
    assert files_in(scenarios_directory) == [FIXED_FILE]

    values = read_back(scenarios_directory, FIXED_FILE)
    assert values["numero"] == FIXED_NUMBER
    assert values["source"] == "le livret"
    assert values["nombre_de_tours"] == 20
    assert values["placement"] == {first: INFANTRY, third: CROSSBOWMEN, second: ORC_INFANTRY}
    assert values["total_points_alliance"] == 12 + 6 + 4
    assert values["total_points_tenebres"] == 8
    dwarves, orcs = values["armees"]
    assert dwarves["unites"] == 2
    assert dwarves["consigne"] == "Au sud du volcan."
    assert dwarves["ancre"] == first
    assert dwarves["magie"] == 45
    assert orcs["consigne"] == "Dans l'Orcreich."
    assert engine_scenario.scenario(FIXED_NUMBER).max_turns == 20


def test_a_new_title_renames_the_file(client, fixed_scenario, scenarios_directory,
                                      plain_squares):
    """The old file goes: two files with one number would be read as one."""
    first, second, _ = plain_squares
    answer = update(client, {first: INFANTRY, second: ORC_INFANTRY}, name="L'Orcreich")

    renamed = f"scenario-{FIXED_NUMBER:02d}-l-orcreich.json"
    assert answer.get_json()["file"] == renamed
    assert files_in(scenarios_directory) == [renamed]
    assert read_back(scenarios_directory, renamed)["nom"] == "L'Orcreich"
    assert engine_scenario.scenario(FIXED_NUMBER).name == "L'Orcreich"


def test_an_undetermined_number_of_turns_is_null_on_update(client, fixed_scenario,
                                                           scenarios_directory, plain_squares):
    first, _, _ = plain_squares
    update(client, {first: INFANTRY}, max_turns=None)
    assert read_back(scenarios_directory, FIXED_FILE)["nombre_de_tours"] is None


@pytest.mark.parametrize("body, fragment", [
    ({"name": "", "placement": {"first": INFANTRY}}, "nom"),
    ({"name": "Essai", "max_turns": 0, "placement": {"first": INFANTRY}}, "tours"),
    ({"name": "Essai", "placement": {}}, "au moins un pion"),
    ({"name": "Essai", "placement": {"first": "nains-99-inconnu"}}, "Pion inconnu"),
    ({"name": "Essai", "placement": {"999,0,-999": INFANTRY}}, "n'est pas sur la carte"),
    ({"name": "Essai", "placement": {"first": FIRE_MARKER}}, "Alliance"),
])
def test_a_refused_update_leaves_the_file_untouched(client, fixed_scenario, scenarios_directory,
                                                    plain_squares, body, fragment):
    """The same refusals as a save, in French, and the file as it was."""
    first, _, _ = plain_squares
    body["placement"] = {first if square == "first" else square: key
                         for square, key in body["placement"].items()}
    before = (scenarios_directory / FIXED_FILE).read_text(encoding="utf-8")

    answer = client.post(f"/admin/scenarios/{FIXED_NUMBER}/edit", json=body)
    assert answer.status_code == 400
    assert answer.get_json()["saved"] is False
    assert fragment in answer.get_json()["message"]
    assert files_in(scenarios_directory) == [FIXED_FILE]
    assert (scenarios_directory / FIXED_FILE).read_text(encoding="utf-8") == before
