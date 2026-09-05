"""The end of a game: the side left without a single unit has lost, and nothing is played after.

"Object of the game: to crush the opponent by annihilating their troops" - the booklet's first
victory condition, and the only one transcribed. A combat that empties a side closes the game: the
sentence goes into the log, the phase says so in place of the phase, and the three routes that play
the game - the move, the combat, the phase change - refuse everything afterwards. `POST /game/new`
is the way out, and the way out on purpose.

The figures are built on the map rather than hard-coded, a corner of bare plain so that no terrain
weighs on the combat. The game is a **real** one - the scenario laid out first - because a board
somebody placed two counters on is not a game and cannot be won (`A_GAME_IS_ON`).
"""

import pytest

from tenebrae.application import current_game
from tenebrae.application.logs.battle_log import log_lines
from tenebrae.engine.piece import piece

from tests.engine.plains import ring_of, well_surrounded_plain

DWARF = "nains-01-5-infanteries"    # alliance, strength 12
ARCHER = "yzent-03-8-archers"       # darkness, strength 2 - against the dwarf, the 6-1 column
A_DEFENDER_ELIMINATED = 1           # the die that reads `DE` there
AN_EXCHANGE = 6                     # and the one that reads `EX`


@pytest.fixture
def the_last_two_units(client, monkeypatch):
    """A game under way, reduced to one unit a side, the archer within the dwarf's reach.

    The scenario is laid out first - that is what puts a game on the board - and the board is then
    emptied down to the two counters the combat needs. The turn is set to the Alliance's combat
    phase, which is the dwarf's to play.
    """
    client.post("/game/new")
    plain = well_surrounded_plain()
    dwarf, *_ = ring_of(plain)
    current_game.BOARD.clear()
    current_game.BOARD.place(plain, piece(ARCHER))
    current_game.BOARD.place(dwarf, piece(DWARF))
    current_game.TURN.restart().advance()          # alliance, combat phase
    current_game.REGISTER.reset()
    monkeypatch.setattr(current_game, "roll_the_die", lambda: A_DEFENDER_ELIMINATED)
    return plain, dwarf


def attack(client, target, attackers):
    """Resolves the combat as the browser asks for it."""
    return client.post("/combat", json={"target": target.to_dict(),
                                        "attackers": [square.to_dict() for square in attackers]})


# --- The game closes ---

def test_the_combat_that_empties_a_side_closes_the_game(client, the_last_two_units):
    archer, dwarf = the_last_two_units
    assert attack(client, archer, [dwarf]).json["resolved"]

    assert current_game.GAME_IS_OVER
    assert current_game.WINNER == "alliance"


def test_the_end_is_written_in_the_log(client, the_last_two_units):
    """What the player reads: the army that won, and why the game stopped."""
    archer, dwarf = the_last_two_units
    attack(client, archer, [dwarf])

    assert any("Nains l'emporte" in line["text"] for line in log_lines()), log_lines()


def test_the_phase_says_the_game_is_over_in_place_of_the_phase(client, the_last_two_units):
    archer, dwarf = the_last_two_units
    attack(client, archer, [dwarf])

    phase = client.get("/phase").get_json()
    assert phase["over"] is True
    assert phase["winner"] == "Nains"
    assert phase["label"] == "Partie terminée — Nains l'emporte"


def test_a_game_still_being_played_says_nothing_of_the_kind(client, the_last_two_units):
    phase = client.get("/phase").get_json()
    assert phase["over"] is False
    assert phase["winner"] is None
    assert phase["label"].startswith("Phase de")


# --- Nothing is played afterwards ---

@pytest.fixture
def a_won_game(client, the_last_two_units):
    """The same game, the combat fought and won."""
    archer, dwarf = the_last_two_units
    attack(client, archer, [dwarf])
    return archer, dwarf


def test_no_move_is_taken_on_a_game_that_is_over(client, a_won_game):
    _, dwarf = a_won_game
    answer = client.post("/move", json={"from": dwarf.to_dict(),
                                        "to": dwarf.neighbours()[0].to_dict()})

    assert answer.status_code == 403
    assert answer.json == {"allowed": False, "message": "La partie est terminée."}


def test_no_combat_is_taken_on_a_game_that_is_over(client, a_won_game):
    _, dwarf = a_won_game
    answer = attack(client, dwarf.neighbours()[0], [dwarf])

    assert answer.status_code == 403
    assert answer.json["message"] == "La partie est terminée."


def test_the_phase_is_not_advanced_on_a_game_that_is_over(client, a_won_game):
    answer = client.post("/phase/next")

    assert answer.status_code == 403
    assert answer.json["message"] == "La partie est terminée."
    assert client.get("/phase").get_json()["over"] is True


def test_a_new_game_opens_the_board_again(client, a_won_game):
    """The way out, and the only one: the set-up is laid out and everything is playable again."""
    assert client.post("/game/new").status_code == 200

    assert current_game.GAME_IS_OVER is False
    assert current_game.WINNER is None
    assert client.get("/phase").get_json()["over"] is False
    assert client.post("/phase/next").status_code == 200


# --- The end outlives the run ---

def test_the_end_is_saved_and_resumed(client, application, a_won_game):
    """A won game reopened is still won: the browser that comes back finds it closed."""
    current_game.reopen_the_game()
    assert current_game.GAME_IS_OVER is False
    with application.app_context():
        saved = current_game.game_repository().load()

    current_game.restore_the_game(current_game.GAME_ID, saved)

    assert current_game.GAME_IS_OVER is True
    assert current_game.WINNER == "alliance"


def test_a_game_saved_before_an_end_could_be_recorded_resumes_playable(client, the_last_two_units):
    """Read with `.get`: a state without those two fields is a game still being played."""
    state = current_game.snapshot_the_game()
    del state["over"]
    del state["winner"]

    current_game.restore_the_game(current_game.GAME_ID, state)

    assert current_game.GAME_IS_OVER is False
    assert current_game.WINNER is None


# --- Two counters on a board are not a game ---

def test_a_board_carrying_no_game_is_not_won(client, deserted_map, monkeypatch):
    """A rule looked at on two counters is not a game that ends: the map is deserted, the combat
    is fought, and the board stays open to whatever the next request asks of it."""
    plain = well_surrounded_plain()
    dwarf, *_ = ring_of(plain)
    current_game.BOARD.place(plain, piece(ARCHER))
    current_game.BOARD.place(dwarf, piece(DWARF))
    current_game.TURN.restart().advance()
    monkeypatch.setattr(current_game, "roll_the_die", lambda: A_DEFENDER_ELIMINATED)

    assert attack(client, plain, [dwarf]).json["resolved"]

    assert current_game.GAME_IS_OVER is False
    assert client.post("/phase/next").status_code == 200


# --- Nobody left standing ---

def test_an_exchange_that_takes_the_last_of_both_leaves_no_winner(client, the_last_two_units,
                                                                  monkeypatch):
    """The dwarf totals the archer's strength on its own, so the exchange takes them both: the
    game is over and nobody won it."""
    archer, dwarf = the_last_two_units
    monkeypatch.setattr(current_game, "roll_the_die", lambda: AN_EXCHANGE)

    assert attack(client, archer, [dwarf]).json["outcome"] == "EX"

    assert current_game.GAME_IS_OVER is True
    assert current_game.WINNER is None
    assert client.get("/phase").get_json()["label"] == "Partie terminée — personne ne l'emporte"


# --- What the board shows of it ---
#
# These require Chromium (`make browser`).

def test_the_board_shows_the_end_and_closes_its_buttons(page, server, application,
                                                        seat_the_player, a_won_game):
    """The two buttons that play go with the phase: the server refuses them, and the bar says so
    beforehand rather than let the player find out by being refused."""
    seat_the_player(application)
    page.set_viewport_size({"width": 1400, "height": 900})
    page.goto(f"{server}/login")
    page.goto(f"{server}/game")
    page.wait_for_function("document.getElementById('scale').textContent !== '—'")

    label = page.locator("#phase-label")
    assert label.text_content() == "Partie terminée — Nains l'emporte"
    assert "over" in (label.get_attribute("class") or "")
    assert page.locator("#next-phase").is_disabled()
    assert page.locator("#attack").is_disabled()
