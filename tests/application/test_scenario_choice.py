"""Choosing the scenario a new game opens on, and the `enabled` field that withdraws one.

`/game/scenarios` lists the set-ups on offer and `/game/new` accepts a number among them. The
number is checked again on the way in: the browser's chooser was filled when the table dialog
opened, and a file disabled in between must not be playable.

The scenarios directory is diverted to a temporary copy of the real one, so that no test writes
`"enabled": false` into `tenebrae/scenarios/`. The copies all start **offered**, whatever their
originals say - no. 4 is withdrawn in the repository as it stands: the list a test reads is then
the one it has itself composed, and a scenario set aside on file changes none of these tests. The
scenario being played is a module global, put back on the way out by the
`the_scenario_the_server_opens_on` fixture of `conftest.py`.
"""

import json
import shutil

import pytest

from tenebrae.application import current_game
from tenebrae.engine import ai
from tenebrae.engine import scenario as engine_scenario
from tenebrae.engine.models.game import Game
from tenebrae.engine.scenario import scenario

WAR_OF_THE_DWARVES = 4
REISSLAND = 6


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts and leaves the board deserted and the turn at its first phase.

    The board and the turn are shared by the whole session, and every test here lays a whole
    scenario out on them.
    """


@pytest.fixture
def alliance_client(application, seat_the_player):
    """A logged-in client holding only the Alliance: the other side is the AI's to take."""
    client = application.test_client()
    seat_the_player(application, client, sides=["alliance"])
    return client


@pytest.fixture
def scenarios_directory(tmp_path, monkeypatch):
    """Diverts the scenarios directory to a copy of the real one, every scenario offered."""
    for path in engine_scenario.SCENARIOS.glob("scenario-*.json"):
        copy = tmp_path / path.name
        shutil.copy(path, copy)
        write_the_field(copy, True)
    monkeypatch.setattr(engine_scenario, "SCENARIOS", tmp_path)
    return tmp_path


def disable(directory, number):
    """Writes `"enabled": false` into a scenario's file, as an administrator would by hand."""
    write_the_field(next(directory.glob(f"scenario-{number:02d}-*.json")), False)


def write_the_field(path, enabled):
    """Sets the `enabled` field of a scenario file, leaving the rest of it as it was."""
    values = json.loads(path.read_text(encoding="utf-8"))
    values["enabled"] = enabled
    path.write_text(json.dumps(values, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def offered(client):
    """The numbers `/game/scenarios` offers."""
    return [entry["number"] for entry in client.get("/game/scenarios").get_json()["scenarios"]]


# --- The list on offer ---


def test_the_list_carries_every_scenario_on_file(client, scenarios_directory):
    answer = client.get("/game/scenarios").get_json()

    assert answer["current"] == WAR_OF_THE_DWARVES
    assert [entry["number"] for entry in answer["scenarios"]] == [WAR_OF_THE_DWARVES, REISSLAND]
    dwarves = answer["scenarios"][0]
    assert dwarves["name"] == "La guerre des nains"
    assert dwarves["max_turns"] == 32
    assert dwarves["units"] == 48


def test_a_disabled_scenario_leaves_the_list(client, scenarios_directory):
    disable(scenarios_directory, REISSLAND)
    assert offered(client) == [WAR_OF_THE_DWARVES]


def test_the_list_is_read_again_at_every_request(client, scenarios_directory):
    """No restart, no reload: the file is what says whether a scenario is offered."""
    assert REISSLAND in offered(client)
    disable(scenarios_directory, REISSLAND)
    assert REISSLAND not in offered(client)


def test_an_anonymous_visitor_may_read_the_list(anonymous_client, scenarios_directory):
    """The chooser is filled whoever opens the table, like the map itself."""
    assert anonymous_client.get("/game/scenarios").status_code == 200


# --- Opening a new game on a chosen scenario ---


def test_a_new_game_opens_on_the_chosen_scenario(client, scenarios_directory):
    answer = client.post("/game/new", json={"scenario": REISSLAND})

    assert answer.status_code == 200
    assert current_game.SCENARIO_NUMBER == REISSLAND
    assert current_game.BOARD.to_dict() == scenario(REISSLAND).placement
    assert len(answer.get_json()["pieces"]) == len(scenario(REISSLAND))
    assert Game.objects.first().scenario == REISSLAND


def test_the_turn_follows_the_new_scenarios_armies(client, scenarios_directory):
    """The turn is the new set-up's: its sides, its army names, from the first phase."""
    armies = {army["camp"]: army["armee"] for army in scenario(REISSLAND).armies}

    phase = client.post("/game/new", json={"scenario": REISSLAND}).get_json()["phase"]
    assert phase["number"] == 1
    assert phase["side"] == scenario(REISSLAND).sides[0]
    assert phase["army"] == armies[phase["side"]]


def test_the_table_names_the_new_scenarios_armies(client, scenarios_directory):
    answer = client.post("/game/new", json={"scenario": REISSLAND}).get_json()
    assert answer["armies"] == {army["camp"]: army["armee"]
                                for army in scenario(REISSLAND).armies}


def test_no_scenario_asked_for_keeps_the_one_being_played(client, scenarios_directory):
    client.post("/game/new", json={"scenario": REISSLAND})
    client.post("/game/new")
    assert current_game.SCENARIO_NUMBER == REISSLAND

    client.post("/game/new", json={"scenario": None})
    assert current_game.SCENARIO_NUMBER == REISSLAND


def test_a_new_game_against_the_ai_opens_on_the_chosen_scenario(alliance_client,
                                                                scenarios_directory):
    answer = alliance_client.post("/game/new", json={"scenario": REISSLAND, "against_ai": True})

    assert answer.status_code == 200
    assert current_game.SCENARIO_NUMBER == REISSLAND
    assert current_game.SEATS.occupant("tenebres") == ai.AI_PLAYER


# --- What the server refuses ---


@pytest.mark.parametrize("asked", [99, "quatre", 4.5, True])
def test_a_number_no_offered_scenario_carries_is_refused(client, scenarios_directory, asked):
    answer = client.post("/game/new", json={"scenario": asked})

    assert answer.status_code == 409
    assert answer.get_json()["message"]
    assert current_game.SCENARIO_NUMBER == WAR_OF_THE_DWARVES


def test_a_disabled_scenario_is_refused(client, scenarios_directory):
    """The chooser no longer offers it, and the route does not take the browser's word for it."""
    disable(scenarios_directory, REISSLAND)
    answer = client.post("/game/new", json={"scenario": REISSLAND})

    assert answer.status_code == 409
    assert f"n° {REISSLAND}" in answer.get_json()["message"]
    assert current_game.SCENARIO_NUMBER == WAR_OF_THE_DWARVES


def test_a_scenario_disabled_since_the_chooser_was_filled_is_refused(client, scenarios_directory):
    """What the second reading is for: the browser holds a list that has just gone stale."""
    assert REISSLAND in offered(client)
    disable(scenarios_directory, REISSLAND)

    assert client.post("/game/new", json={"scenario": REISSLAND}).status_code == 409


def test_a_refused_new_game_leaves_the_game_where_it_was(client, scenarios_directory):
    client.post("/game/new", json={"scenario": REISSLAND})
    before = current_game.BOARD.to_dict()
    version = current_game.VERSION

    assert client.post("/game/new", json={"scenario": 99}).status_code == 409
    assert current_game.SCENARIO_NUMBER == REISSLAND
    assert current_game.BOARD.to_dict() == before
    assert current_game.VERSION == version


def test_a_refused_scenario_is_not_played_even_against_the_ai(alliance_client,
                                                              scenarios_directory):
    """The scenario is read before the seats are given away: nothing is half done."""
    disable(scenarios_directory, REISSLAND)

    answer = alliance_client.post("/game/new",
                                  json={"scenario": REISSLAND, "against_ai": True})
    assert answer.status_code == 409
    assert f"n° {REISSLAND}" in answer.get_json()["message"]
    assert current_game.SCENARIO_NUMBER == WAR_OF_THE_DWARVES
    assert current_game.SEATS.occupant("tenebres") is None


# --- The game under way ---


def test_the_saved_game_is_resumed_on_its_own_scenario(client, scenarios_directory):
    """The set-up being played follows the save, and not the one the server opened on."""
    client.post("/game/new", json={"scenario": REISSLAND})
    current_game.switch_to_the_scenario(scenario(WAR_OF_THE_DWARVES))

    assert client.get("/").status_code == 200
    assert current_game.SCENARIO_NUMBER == REISSLAND
    assert current_game.BOARD.to_dict() == scenario(REISSLAND).placement


def test_a_game_under_way_on_a_disabled_scenario_is_still_resumed(client, scenarios_directory):
    """Disabling withdraws a scenario from the new games, it does not interrupt the one played."""
    client.post("/game/new", json={"scenario": REISSLAND})
    disable(scenarios_directory, REISSLAND)

    assert client.get("/").status_code == 200
    assert current_game.SCENARIO_NUMBER == REISSLAND
    assert offered(client) == [WAR_OF_THE_DWARVES]


def test_a_saved_scenario_whose_file_has_gone_opens_a_new_game(client, scenarios_directory):
    """Nothing to read it back from: the set-up being played is laid out, and the save replaced."""
    client.post("/game/new", json={"scenario": REISSLAND})
    current_game.switch_to_the_scenario(scenario(WAR_OF_THE_DWARVES))
    next(scenarios_directory.glob(f"scenario-{REISSLAND:02d}-*.json")).unlink()

    assert client.get("/").status_code == 200
    assert current_game.SCENARIO_NUMBER == WAR_OF_THE_DWARVES
    assert Game.objects.first().scenario == WAR_OF_THE_DWARVES
    assert current_game.BOARD.to_dict() == scenario(WAR_OF_THE_DWARVES).placement
