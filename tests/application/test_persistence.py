"""The saved game: what MongoDB keeps, and what "/" resumes of it.

The whole suite runs on the test MongoDB that `make test` brings up, and `conftest.py` empties it
before every test. This file is the one that looks into the base - at the documents themselves -
and that plays the server's restart: memory emptied, only the base knows where the game stood.
"""

import pytest

from tenebrae.application import current_game, persistence
from tenebrae.application.discord_client import DEFAULT_IDENTITY
from tenebrae.application.models.view import View
from tenebrae.engine import ai
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.models.game import Game
from tenebrae.engine.models.player import Player
from tenebrae.engine.phase import COMBAT, MOVEMENT
from tenebrae.engine.piece import CATALOGUE

from tests.application.test_server import read_hidden_field, the_board

# The same squares and the same counters as test_server.py: two neighbouring plains, a dwarf of
# strength 12 and an orc of strength 8 - enough to fight a combat leaving nothing to chance.
PLAIN = {"q": 1, "r": 26, "s": -27}
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}
DWARF = "nains-01-5-infanteries"
ORC = "orques-01-15-infanteries"
ARCHER = "yzent-03-8-archers"      # darkness, strength 2: a dwarf eliminates it outright

# Two made-up Discord identifiers, to seat someone at each side.
DWARF_PLAYER = "100000000000000001"
ORC_PLAYER = "100000000000000002"


@pytest.fixture(autouse=True)
def isolated_board(deserted_map):
    """Every test starts from a deserted map and the first phase, and leaves them so.

    The board and the turn are shared by the whole session: a phase left advanced would have the
    next file's `/move` refused, which showed as an occasional failure depending on the order the
    files were collected in.
    """


def place(hexagon, key):
    current_game.BOARD.place(Hex(**hexagon), CATALOGUE[key])


class TestOpeningTheGame:
    def test_the_first_load_writes_the_set_up_and_the_next_resumes_it(self, client):
        the_board(client)
        assert Game.objects.count() == 1
        game = Game.objects.first()
        assert game.scenario == current_game.SCENARIO_NUMBER
        assert dict(game.placement) == current_game.SCENARIO.placement
        assert (game.active_side, game.phase_type) == (current_game.TURN.active_side, MOVEMENT)
        assert game.turn_number == 1
        assert game.engaged_attackers == [] and game.engaged_targets == []
        assert game.created_at is not None and game.updated_at is not None

        # And loading again resumes that one rather than opening a second.
        the_board(client)
        assert Game.objects.count() == 1


class TestResumingTheGame:
    def test_a_move_is_resumed_after_a_restart(self, client):
        """The heart of persistence: the piece is found at its destination, not at its origin."""
        the_board(client)
        origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
        destination = current_game.BOARD.moves(origin)[0]
        answer = client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": current_game.BOARD.piece_on(origin).key})
        assert answer.json["allowed"] is True

        # The server restarts: memory is empty, only the base knows where the game stood.
        current_game.BOARD.clear()
        current_game.TURN.restart()
        the_board(client)

        assert current_game.BOARD.piece_on(origin) is None
        assert current_game.BOARD.piece_on(destination) is not None
        assert dict(Game.objects.first().placement)[destination.key] is not None

    def test_a_refused_move_does_not_touch_the_saved_game(self, client):
        the_board(client)
        before = dict(Game.objects.first().placement)
        origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
        # A square at the other end of the map: out of reach, the move is refused.
        distant = {"q": 30, "r": 2, "s": -32}
        answer = client.post("/move", json={
            "origin": origin.to_dict(), "destination": distant,
            "piece": current_game.BOARD.piece_on(origin).key})
        assert answer.json["allowed"] is False
        assert dict(Game.objects.first().placement) == before

    def test_the_phase_is_resumed(self, client):
        the_board(client)
        client.post("/phase/next")
        assert Game.objects.first().phase_type == COMBAT

        current_game.TURN.restart()
        the_board(client)
        assert current_game.TURN.phase_type == COMBAT

    def test_a_saved_game_whose_scenario_has_no_file_is_discarded(self, client):
        """No file carries that number any more: there is nothing to lay out, so a game opens.

        A save on a scenario still on file is resumed on that scenario instead - the server puts
        itself back on it (see `test_scenario_choice.py`).
        """
        the_board(client)
        Game.objects.update(set__scenario=99)
        the_board(client)
        assert Game.objects.count() == 2
        assert Game.objects.first().scenario == current_game.SCENARIO_NUMBER


class TestPersistedCombat:
    def test_an_eliminated_unit_does_not_come_back(self, client, monkeypatch):
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        the_board(client)
        current_game.BOARD.clear()
        place(PLAIN, DWARF)      # strength 12
        place(NEIGHBOUR, ORC)    # strength 8
        client.post("/phase/next")  # the Alliance's combat phase
        # A ratio of 6 against 1: the target is eliminated for certain.
        current_game.BOARD.remove(Hex(**NEIGHBOUR))
        place(NEIGHBOUR, "yzent-03-8-archers")  # strength 2
        answer = client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
        assert answer["resolved"] is True

        saved = dict(Game.objects.first().placement)
        assert Hex(**NEIGHBOUR).key not in saved
        assert saved[Hex(**PLAIN).key] == DWARF

    def test_the_phase_register_is_saved_and_resumed(self, client, monkeypatch):
        """The target falls back: it is the square it **reached** that is saved as engaged, or it
        could be attacked again this phase from its new square."""
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        the_board(client)
        current_game.BOARD.clear()
        place(PLAIN, DWARF)
        place(NEIGHBOUR, ORC)   # ratio 1-1, die 1 -> DR: the orc falls back one square
        client.post("/phase/next")
        answer = client.post("/combat",
                             json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
        assert answer["resolved"] is True
        fallen_back = Hex(**{name: answer["retreats"][0]["to"][name] for name in ("q", "r", "s")})

        game = Game.objects.first()
        assert game.engaged_attackers == [Hex(**PLAIN).key]
        assert game.engaged_targets == [fallen_back.key]

        current_game.REGISTER.reset()
        the_board(client)
        assert not current_game.REGISTER.can_attack(Hex(**PLAIN).key)
        assert not current_game.REGISTER.can_be_targeted(fallen_back.key)

    def test_the_fallen_are_saved_and_resumed(self, client, monkeypatch):
        """The booklet counts the eliminated units at the end of the game: they must survive a
        restart, like the board and the turn."""
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        the_board(client)
        current_game.BOARD.clear()
        place(PLAIN, DWARF)       # strength 12
        place(NEIGHBOUR, ARCHER)  # strength 2 -> ratio 6-1, die 1 -> DE
        client.post("/phase/next")
        assert client.post("/combat",
                           json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json["resolved"]

        saved = Game.objects.first().casualties
        assert len(saved) == 1
        assert (saved[0].square, saved[0].piece) == (Hex(**NEIGHBOUR).key, ARCHER)
        assert (saved[0].side, saved[0].taken_by) == ("tenebres", "alliance")

        current_game.CASUALTIES.reset()
        the_board(client)
        assert current_game.CASUALTIES.points_taken_by("alliance") == 2

    def test_a_game_saved_before_the_fallen_were_kept_is_still_resumed(self, client):
        """The field did not exist: an old game reads back with an empty register."""
        the_board(client)
        game = Game.objects.first()
        game.casualties = []
        game.save()

        the_board(client)
        assert len(current_game.CASUALTIES) == 0

    def test_an_emptied_board_is_still_saved(self, client):
        """Nothing left standing is a game state like any other: the save must not refuse it."""
        the_board(client)
        current_game.BOARD.clear()
        assert client.post("/phase/next").status_code == 200
        assert dict(Game.objects.first().placement) == {}

        current_game.BOARD.clear()
        the_board(client)
        assert current_game.BOARD.pieces == {}

    def test_changing_phase_empties_the_register_in_base(self, client, monkeypatch):
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        the_board(client)
        current_game.BOARD.clear()
        place(PLAIN, DWARF)
        place(NEIGHBOUR, ORC)
        client.post("/phase/next")
        client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})
        client.post("/phase/next")
        game = Game.objects.first()
        assert game.engaged_attackers == [] and game.engaged_targets == []


class TestNewGame:
    def test_it_lays_the_scenario_out_again_and_opens_a_second_document(self, client):
        the_board(client)
        origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
        destination = current_game.BOARD.moves(origin)[0]
        client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": current_game.BOARD.piece_on(origin).key})

        answer = client.post("/game/new").json
        assert answer["url"] == f"/game/{answer['id']}"
        assert current_game.BOARD.to_dict() == current_game.SCENARIO.placement
        assert current_game.TURN.phase_type == MOVEMENT
        assert Game.objects.count() == 2
        # The most recent is the one just opened, and "/game" resumes that one.
        assert dict(Game.objects.first().placement) == current_game.SCENARIO.placement
        the_board(client)
        assert current_game.BOARD.piece_on(origin) is not None

    def test_two_games_of_the_same_second_stay_in_order(self, client):
        """The date alone is not enough to break the tie: two writes may share it.

        Without the identifier as a second criterion, "start again" then reload could resume the
        game one had just abandoned.
        """
        the_board(client)
        origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
        destination = current_game.BOARD.moves(origin)[0]
        client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": current_game.BOARD.piece_on(origin).key})
        client.post("/game/new")

        # Both games are dated to the same second, as if everything had been played in one go.
        instant = Game.objects.first().updated_at
        Game.objects.update(set__updated_at=instant)

        assert Game.objects.count() == 2
        assert dict(Game.objects.first().placement) == current_game.SCENARIO.placement


class TestRepository:
    """The repository's round trip alone, without going through a route."""

    def test_snapshotting_then_restoring_lands_on_the_same_game(self, application):
        with application.test_request_context():
            place(PLAIN, DWARF)
            current_game.TURN.restore(current_game.TURN.active_side, COMBAT, 3)
            current_game.REGISTER.record([Hex(**PLAIN).key], Hex(**NEIGHBOUR).key)
            state = current_game.snapshot_the_game()

            current_game.BOARD.clear()
            current_game.TURN.restart()
            current_game.REGISTER.reset()
            current_game.restore_the_game("a-game-of-no-consequence-here", state)

            assert current_game.snapshot_the_game() == state

    def test_saving_then_loading_returns_the_same_state(self, application):
        with application.test_request_context():
            place(PLAIN, DWARF)
            state = current_game.snapshot_the_game()
            identifier = persistence.game_repository().save(None, state)
            assert persistence.game_repository().load(identifier) == state

    def test_loading_finds_nothing_in_an_empty_base(self, application):
        with application.test_request_context():
            assert persistence.game_repository().load() is None


class TestPersistedSeats:
    """Who holds which side is part of the game: a restart does not empty the table."""

    def test_the_seats_are_written_with_the_game_and_resumed_with_it(self, client):
        # The fixture seats the test player at both sides; we rebuild the table with two.
        current_game.SEATS.clear().seat("alliance", DWARF_PLAYER).seat("tenebres", ORC_PLAYER)
        the_board(client)
        assert dict(Game.objects.first().seats) == {"alliance": DWARF_PLAYER,
                                                    "tenebres": ORC_PLAYER}

        # The server restarts: the table in memory is lifted, only the base knows it.
        current_game.SEATS.clear()
        the_board(client)

        assert current_game.SEATS.occupant("alliance") == DWARF_PLAYER
        assert current_game.SEATS.occupant("tenebres") == ORC_PLAYER

    def test_a_game_saved_without_seats_stays_resumable(self, client):
        """Games from before players existed have no `seats` field: the table is empty."""
        the_board(client)
        Game.objects.update(unset__seats=1)
        current_game.SEATS.clear().seat("alliance", DWARF_PLAYER)

        the_board(client)

        assert current_game.SEATS.is_free("alliance")

    def test_the_recorded_players_are_found_again_and_no_others(self, application):
        with application.test_request_context():
            repository = persistence.player_repository()
            repository.record({"discord_id": DWARF_PLAYER, "nickname": "Vorgtd", "avatar": None})
            assert repository.by_discord_id(DWARF_PLAYER)["nickname"] == "Vorgtd"
            assert repository.by_discord_id("999") is None

    def test_a_second_login_updates_the_nickname_without_creating_a_player(self, application):
        with application.test_request_context():
            repository = persistence.player_repository()
            repository.record({"discord_id": DWARF_PLAYER, "nickname": "Vorgtd"})
            repository.record({"discord_id": DWARF_PLAYER, "nickname": "Vorgtd le Grand"})
            assert Player.objects.count() == 1
            assert repository.by_discord_id(DWARF_PLAYER)["nickname"] == "Vorgtd le Grand"


class TestPersistedTilts:
    """The angle each counter lies at is part of the saved game.

    Without it in base, it would be redrawn at every reread of the board, and the forty-eight
    pieces would spin at every page reload. It only changes on a move.
    """

    def test_the_tilts_are_written_with_the_game_and_resumed_with_it(self, client):
        the_board(client)
        tilts = dict(Game.objects.first().tilts)
        assert set(tilts) == set(current_game.SCENARIO.placement)
        assert tilts == current_game.BOARD.tilts

        before = current_game.BOARD.tilts

        # The server restarts: memory is empty, only the base knows how the pieces were lying.
        current_game.BOARD.clear()
        current_game.TURN.restart()
        the_board(client)

        assert current_game.BOARD.tilts == before

    def test_polling_the_game_does_not_lay_the_pieces_down_again(self, client):
        """What the player sees: the page lays the scene out again and the pieces do not spin.

        It is the `/game/state` poll that gives the browser the pieces to lay out again; it is
        played here twice in a row, around a load of "/" that rereads the saved game.
        """
        the_board(client)
        first = client.get("/game/state").json["pieces"]
        the_board(client)
        second = client.get("/game/state").json["pieces"]
        assert [piece["tilt"] for piece in second] == [piece["tilt"] for piece in first]

    def test_a_move_writes_the_new_tilt(self, client):
        the_board(client)
        origin = Hex.from_key(next(iter(current_game.SCENARIO.placement)))
        destination = current_game.BOARD.moves(origin)[0]
        before = current_game.BOARD.tilt_on(origin)

        answer = client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": current_game.BOARD.piece_on(origin).key})
        assert answer.json["allowed"] is True

        tilts = dict(Game.objects.first().tilts)
        assert origin.key not in tilts
        assert tilts[destination.key] == answer.json["tilt"] != before

    def test_a_game_saved_without_tilts_stays_resumable(self, client):
        """Games from before we started keeping them do not have the field.

        They resume all the same: the board draws the angles it lacks, and the first move played
        writes them. They are fixed from then on.
        """
        the_board(client)
        Game.objects.update(unset__tilts=1)
        current_game.BOARD.clear()

        the_board(client)
        resumed = current_game.BOARD.tilts
        assert set(resumed) == set(current_game.SCENARIO.placement)

        client.post("/phase/next")  # a move played, hence a save
        assert dict(Game.objects.first().tilts) == resumed

        current_game.BOARD.clear()
        the_board(client)
        assert current_game.BOARD.tilts == resumed


class TestPersistedGameAgainstTheAI:
    """The AI's seat travels in the seats dict, under its sentinel: nothing more to save, nothing
    more to resume."""

    def test_the_ais_seat_is_written_with_the_game_and_resumed_with_it(self, application,
                                                                       seat_the_player):
        client = application.test_client()
        seat_the_player(application, client, sides=["alliance"])
        answer = client.post("/game/new", json={"against_ai": True})
        assert answer.status_code == 200
        assert dict(Game.objects.first().seats)["tenebres"] == ai.AI_PLAYER

        # The server restarts: the table in memory is lifted, only the base knows it.
        current_game.SEATS.clear()
        current_game.BOARD.clear()
        current_game.TURN.restart()
        the_board(client)

        assert current_game.SEATS.occupant("tenebres") == ai.AI_PLAYER


class TestPersistedView:
    """The map view: the only document of the application that is not part of the game.

    Its model and its repository belong to the application (`models/view.py`,
    `repositories/view.py`) and not to the engine - the engine does not know that an image, pixels
    or a window exist.
    """

    VIEW = {"scale": 0.37, "x": 3086.5, "y": 2551.25, "fitted": False}

    def test_adjusting_ones_view_writes_it_to_base(self, client):
        client.post("/view", json=self.VIEW)
        stored = View.objects.first()
        assert stored.discord_id == DEFAULT_IDENTITY["discord_id"]
        assert (stored.scale, stored.x, stored.y, stored.fitted) \
            == (self.VIEW["scale"], self.VIEW["x"], self.VIEW["y"], False)
        assert stored.updated_at is not None

    def test_the_view_is_resumed_after_a_restart(self, client):
        """That is the requirement: only the base knows where the player was."""
        client.post("/view", json=self.VIEW)
        assert read_hidden_field(the_board(client).get_data(as_text=True), "view") == self.VIEW

    def test_a_second_adjustment_does_not_create_a_second_document(self, client):
        """No zoom history is kept: one document per player."""
        client.post("/view", json=self.VIEW)
        client.post("/view", json={**self.VIEW, "scale": 1.0})
        assert View.objects.count() == 1
        assert View.objects.first().scale == 1.0


class TestWhatMongoStores:
    """What only a real base shows: the BSON encoding of the keys, and the round trip of dates."""

    def test_the_squares_pass_into_base_as_they_are(self, client):
        """The placement keys are Mongo document keys - "1,26,-27", commas and minus signs, where
        Mongo refuses a leading dot or dollar: they must be admitted there."""
        the_board(client)
        placement = dict(Game.objects.first().placement)
        assert placement == current_game.SCENARIO.placement
        assert all("," in square for square in placement)
        assert any(square.count("-") for square in placement)

    def test_the_dates_come_back_readable(self, client):
        the_board(client)
        game = Game.objects.first()
        assert game.created_at is not None
        assert game.updated_at >= game.created_at
