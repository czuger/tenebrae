"""The landing page: the games already saved, and what opening one does to the server.

"/" was the map, and loading it laid a scenario out on an empty base - so every arrival, an
anonymous visitor's included, opened a game. It is the list of games now, and it creates nothing:
what creates is "/game", which is asked for a game to play, and `POST /game/new`, which is asked
for a new one. The first test of this file is that regression and nothing else.

The rest is what the list has to get right - the cards, whose game is whose - and what having
several addresses for one process forces: **a save must land in the game being played**, not in the
most recent document, or one player's moves would be written into another's game.
"""

import re

import pytest

from tenebrae.application import current_game
from tenebrae.application.discord_client import DEFAULT_IDENTITY
from tenebrae.engine import ai
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.models.game import Game
from tenebrae.engine.piece import CATALOGUE

from tests.application.test_server import read_hidden_field, the_board

ALLIANCE, DARKNESS = "alliance", "tenebres"
DWARF = "nains-01-5-infanteries"

# A second Discord account, to hold the side the test player does not.
GRISHNAK = DEFAULT_IDENTITY | {"discord_id": "100000000000000002", "nickname": "Grishnak"}


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map and the first phase, and leaves them so: the board
    and the turn are shared by the whole session."""


def listed(client):
    """The cards the landing page carries, as the browser receives them."""
    return read_hidden_field(client.get("/").get_data(as_text=True), "games")


def record(application):
    """Saves the game as a route would.

    `save_the_game` reaches the repository through the application, and these tests change the
    board and the seats directly rather than through a request.
    """
    with application.app_context():
        current_game.save_the_game()


def a_game(client, side=ALLIANCE, against_ai=False):
    """Opens a game through the route the landing form posts to, and returns its identifier."""
    answer = client.post("/game/new", json={"side": side, "against_ai": against_ai})
    assert answer.status_code == 200, answer.get_json()
    return answer.get_json()["id"]


# --- What the list is, and what it is not --------------------------------------------------------


def test_the_list_is_public(anonymous_client):
    assert anonymous_client.get("/").status_code == 200


def test_reading_the_list_opens_no_game(anonymous_client):
    """The regression the landing page exists to avoid: "/" laid a scenario out on an empty base,
    so every passer-by left a game behind them."""
    anonymous_client.get("/")
    assert Game.objects.count() == 0
    assert listed(anonymous_client) == []


def test_every_saved_game_is_listed_most_recent_first(client):
    first, second = a_game(client), a_game(client)
    assert [card["id"] for card in listed(client)] == [second, first]


def test_a_card_carries_where_its_game_stands(client):
    a_game(client)
    card, = listed(client)

    assert card["scenario"] == current_game.SCENARIO_NUMBER
    assert card["scenario_name"] == current_game.SCENARIO.name
    assert card["turn"] == 1
    assert card["phase"] == "Phase de mouvement"
    assert card["army"] == current_game.TURN.active_army
    assert card["units"] == len(current_game.SCENARIO)
    assert card["over"] is False and card["end"] is None


def test_a_card_names_the_occupant_of_each_side(client, application):
    a_game(client, side=ALLIANCE)
    current_game.SEATS.seat(DARKNESS, GRISHNAK["discord_id"])
    record(application)
    application.extensions["player_repository"].record(GRISHNAK)

    sides = {side["side"]: side for side in listed(client)[0]["sides"]}
    assert sides[ALLIANCE]["occupant"] == DEFAULT_IDENTITY["nickname"]
    assert sides[DARKNESS]["occupant"] == GRISHNAK["nickname"]
    assert sides[ALLIANCE]["army"] == current_game.TURN.army_of(ALLIANCE)


def test_a_free_side_has_no_occupant_and_the_machine_has_its_name(client, application):
    a_game(client, side=ALLIANCE, against_ai=True)
    against_the_machine = {side["side"]: side for side in listed(client)[0]["sides"]}
    assert against_the_machine[DARKNESS]["occupant"] == ai.AI_NAME

    current_game.SEATS.free(DARKNESS)
    record(application)
    left_free = {side["side"]: side for side in listed(client)[0]["sides"]}
    assert left_free[DARKNESS]["occupant"] is None


def test_the_games_one_holds_a_side_in_are_marked(client, application):
    """And the others are not: the mark is what tells one's own games out of the whole history."""
    mine = a_game(client, side=ALLIANCE)
    someone_elses = a_game(client, side=ALLIANCE)
    current_game.SEATS.restore({ALLIANCE: GRISHNAK["discord_id"]})
    record(application)

    marked = {card["id"]: card["mine"] for card in listed(client)}
    assert marked == {mine: True, someone_elses: False}


def test_an_anonymous_visitor_holds_nothing(client, anonymous_client):
    a_game(client, side=ALLIANCE)
    assert [card["mine"] for card in listed(anonymous_client)] == [False]


def test_a_finished_game_says_how_it_ended(client, application):
    a_game(client, side=ALLIANCE)
    current_game.GAME_IS_OVER, current_game.WINNER = True, ALLIANCE
    record(application)

    card, = listed(client)
    assert card["over"] is True
    assert card["end"] == f"Partie terminée — {current_game.TURN.army_of(ALLIANCE)} l'emporte"


def test_a_game_whose_scenario_has_gone_is_listed_but_not_openable(client, monkeypatch):
    """The card still says who was playing it; it carries no name, and nothing links to it - the
    set-up cannot be laid out any more."""
    identifier = a_game(client, side=ALLIANCE)
    Game.objects(pk=identifier).update_one(set__scenario=999)

    card, = listed(client)
    assert card["scenario"] == 999
    assert card["scenario_name"] is None
    assert [side["side"] for side in card["sides"]] == [ALLIANCE]
    assert client.get(f"/game/{identifier}").status_code == 404


def test_the_date_carries_its_timezone(client):
    """MongoDB gives the time back naive, and a naive time reads as the browser's own: an offset
    is what stops a game played at 18:06 UTC being shown as 18:06 in Paris."""
    a_game(client)
    assert re.search(r"(\+00:00|Z)$", listed(client)[0]["played_at"])


def visitor(client):
    """Who the landing page says is looking at it."""
    return read_hidden_field(client.get("/").get_data(as_text=True), "visitor")


def test_the_visitor_is_named_to_a_player_and_not_to_a_stranger(client, anonymous_client):
    assert visitor(client)["nickname"] == DEFAULT_IDENTITY["nickname"]
    assert visitor(anonymous_client)["connected"] is False


def test_the_form_is_offered_the_sides_of_each_set_up(client):
    """What the side chooser is filled from: one picks a side before the game exists to sit at."""
    offered = read_hidden_field(client.get("/").get_data(as_text=True), "scenarios")
    assert offered
    for entry in offered:
        assert set(entry["armies"]) == {ALLIANCE, DARKNESS}


# --- One address per game ------------------------------------------------------------------------


def test_opening_a_game_by_its_address_takes_the_server_onto_it(client):
    first = a_game(client, side=ALLIANCE)
    second = a_game(client, side=DARKNESS)
    assert current_game.GAME_ID == second

    assert client.get(f"/game/{first}").status_code == 200
    assert current_game.GAME_ID == first
    assert current_game.SEATS.occupant(ALLIANCE) == DEFAULT_IDENTITY["discord_id"]
    assert current_game.SEATS.occupant(DARKNESS) is None


def test_an_unknown_game_is_a_refusal_in_french(client):
    answer = client.get("/game/60c72b2f9b1e8a3f4c000000")
    assert answer.status_code == 404
    assert answer.get_json()["message"] == "Cette partie n'existe pas."


def test_an_address_that_is_not_an_identifier_is_the_same_refusal(client):
    """Not a 500: a badly typed address is a game that is not there."""
    answer = client.get("/game/pas-un-identifiant")
    assert answer.status_code == 404
    assert answer.get_json()["message"] == "Cette partie n'existe pas."


def test_the_static_routes_keep_their_own_rules(client):
    """`/game/<id>` must not swallow its siblings: Werkzeug tries static segments first."""
    assert "scenarios" in client.get("/game/scenarios").get_json()
    assert "changed" in client.get("/game/state").get_json()


def test_the_board_without_an_identifier_sends_to_the_last_game_played(client):
    a_game(client)
    latest = a_game(client)
    answer = client.get("/game")
    assert answer.status_code == 302
    assert answer.headers["Location"] == f"/game/{latest}"


def test_the_board_without_an_identifier_opens_one_on_an_empty_base(client):
    assert Game.objects.count() == 0
    assert the_board(client).status_code == 200
    assert Game.objects.count() == 1


def test_the_query_string_survives_the_redirect(client):
    """"?debug=1" and "?icons=0" are read by the page: swallowed here, they would say nothing."""
    a_game(client)
    assert client.get("/game?debug=1").headers["Location"].endswith("?debug=1")


def test_the_page_names_the_game_it_was_served_for(client):
    identifier = a_game(client)
    page = client.get(f"/game/{identifier}").get_data(as_text=True)
    assert f'id="game" value="{identifier}"' in page


# --- Saving into the game being played -----------------------------------------------------------


def test_a_move_is_written_into_the_game_being_played_and_no_other(client):
    """The correctness of the whole change. `save` used to write into the most recent document,
    which was true while the server only ever played that one; opening an older game and playing it
    would have landed these moves in the newer one."""
    older = a_game(client, side=ALLIANCE)
    newer = a_game(client, side=ALLIANCE)
    untouched = dict(Game.objects(pk=newer).first().placement)

    client.get(f"/game/{older}")
    square = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
    destination = current_game.BOARD.moves(square)[0]
    moved = client.post("/move", json={"origin": square.to_dict(),
                                       "destination": destination.to_dict(),
                                       "piece": current_game.BOARD.piece_on(square).key})
    assert moved.get_json()["allowed"] is True

    assert dict(Game.objects(pk=newer).first().placement) == untouched
    assert destination.key in dict(Game.objects(pk=older).first().placement)


def test_a_board_carrying_no_game_opens_one_at_its_first_move(application, deserted_map):
    """What an empty base used to do, and what the tests that desert the map rely on."""
    assert current_game.GAME_ID is None
    current_game.BOARD.place(Hex(0, 26, -26), CATALOGUE[DWARF])
    record(application)
    assert current_game.GAME_ID is not None
    assert Game.objects.count() == 1
