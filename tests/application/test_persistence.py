"""The saved game: what MongoDB keeps, and what "/" resumes of it.

These engine run on mongomock - an in-memory MongoDB -, no server is required. They are the only
ones in the repository to plug in persistence: everywhere else the test configuration installs the
null repository, and the application behaves as before.
"""

import os

import pytest

mongomock = pytest.importorskip("mongomock")

import mongoengine  # noqa: E402

from tenebrae.application import app  # noqa: E402
from tenebrae.application.config import TestingConfig  # noqa: E402
from tenebrae.application.discord_client import DEFAULT_IDENTITY  # noqa: E402
from tenebrae.engine.hexagon import Hex  # noqa: E402
from tenebrae.engine.phase import COMBAT, MOVEMENT  # noqa: E402
from tenebrae.engine.piece import CATALOGUE  # noqa: E402

from tests.application.test_server import read_hidden_field  # noqa: E402

# The same squares and the same counters as test_server.py: two neighbouring plains, a dwarf of
# strength 12 and an orc of strength 8 - enough to fight a combat leaving nothing to chance.
PLAIN = {"q": 1, "r": 26, "s": -27}
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}
DWARF = "nains-01-5-infanteries"
ORC = "orques-01-15-infanteries"

# Two made-up Discord identifiers, to seat someone at each side.
DWARF_PLAYER = "100000000000000001"
ORC_PLAYER = "100000000000000002"


class MongomockConfig(TestingConfig):
    """The test configuration, but with persistence plugged into an in-memory Mongo.

    The "mongomock://" URI scheme is no longer recognised by mongoengine: we pass it the client
    class, which is the supported way.
    """

    PERSISTENCE = "mongo"
    MONGODB_SETTINGS = {"db": "tenebrae_test", "mongo_client_class": mongomock.MongoClient}


@pytest.fixture
def mongo_application():
    """An application whose repository writes into mongomock, which starts from a known state and
    leaves nothing behind.

    Mongoengine keeps a global registry of connections: we must disconnect on the way out, without
    which the other test files would inherit this one. `app`'s module globals are shared by the
    whole session, and are reset the same way - **on the way in as well as on the way out**. Only
    cleaning up on the way out is not enough: the first test of this file would then inherit the
    board and, above all, the phase left by whatever file ran before it, and a `/move` played
    outside the movement phase comes back refused - which showed as an occasional failure of
    `test_a_move_writes_the_new_tilt`, depending on the order the files were collected in.
    """
    application = app.create_app(MongomockConfig)
    from tenebrae.engine.models.game import Game
    from tenebrae.engine.models.player import Player
    from tenebrae.application.models.view import View
    Game.objects.delete()
    Player.objects.delete()
    View.objects.delete()
    app.BOARD.clear()
    app.TURN.restart()
    app.REGISTER.reset()
    app.SEATS.clear()
    yield application
    Game.objects.delete()
    Player.objects.delete()
    View.objects.delete()
    mongoengine.disconnect_all()
    app.BOARD.clear()
    app.TURN.restart()
    app.REGISTER.reset()
    app.SEATS.clear()


@pytest.fixture
def mongo_client(mongo_application, seat_the_player):
    """Logged in and seated at both sides, like the conftest's `client`: the routes that save the
    game now require a seat."""
    client = mongo_application.test_client()
    seat_the_player(mongo_application, client)
    return client


@pytest.fixture
def games():
    """The model, imported once the connection is open."""
    from tenebrae.engine.models.game import Game
    return Game


def place(hexagon, key):
    app.BOARD.place(Hex(**hexagon), CATALOGUE[key])


class TestOpeningTheGame:
    def test_the_first_load_writes_the_set_up_and_the_next_resumes_it(self, mongo_client, games):
        mongo_client.get("/")
        assert games.objects.count() == 1
        game = games.objects.first()
        assert game.scenario == app.SCENARIO_NUMBER
        assert dict(game.placement) == app.SCENARIO.placement
        assert (game.active_side, game.phase_type) == (app.TURN.active_side, MOVEMENT)
        assert game.turn_number == 1
        assert game.engaged_attackers == [] and game.engaged_targets == []
        assert game.created_at is not None and game.updated_at is not None

        # And loading again resumes that one rather than opening a second.
        mongo_client.get("/")
        assert games.objects.count() == 1


class TestResumingTheGame:
    def test_a_move_is_resumed_after_a_restart(self, mongo_client, games):
        """The heart of persistence: the piece is found at its destination, not at its origin."""
        mongo_client.get("/")
        origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
        destination = app.BOARD.moves(origin)[0]
        answer = mongo_client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": app.BOARD.piece_on(origin).key})
        assert answer.json["allowed"] is True

        # The server restarts: memory is empty, only the base knows where the game stood.
        app.BOARD.clear()
        app.TURN.restart()
        mongo_client.get("/")

        assert app.BOARD.piece_on(origin) is None
        assert app.BOARD.piece_on(destination) is not None
        assert dict(games.objects.first().placement)[destination.key] is not None

    def test_a_refused_move_does_not_touch_the_saved_game(self, mongo_client, games):
        mongo_client.get("/")
        before = dict(games.objects.first().placement)
        origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
        # A square at the other end of the map: out of reach, the move is refused.
        distant = {"q": 30, "r": 2, "s": -32}
        answer = mongo_client.post("/move", json={
            "origin": origin.to_dict(), "destination": distant,
            "piece": app.BOARD.piece_on(origin).key})
        assert answer.json["allowed"] is False
        assert dict(games.objects.first().placement) == before

    def test_the_phase_is_resumed(self, mongo_client, games):
        mongo_client.get("/")
        mongo_client.post("/phase/next")
        assert games.objects.first().phase_type == COMBAT

        app.TURN.restart()
        mongo_client.get("/")
        assert app.TURN.phase_type == COMBAT

    def test_a_saved_game_of_another_scenario_is_discarded(self, mongo_client, games):
        """Changing scenario does not resume a game that no longer relates to it."""
        mongo_client.get("/")
        games.objects.update(set__scenario=99)
        mongo_client.get("/")
        assert games.objects.count() == 2
        assert games.objects.first().scenario == app.SCENARIO_NUMBER


class TestPersistedCombat:
    def test_an_eliminated_unit_does_not_come_back(self, mongo_client, games, monkeypatch):
        monkeypatch.setattr(app, "roll_the_die", lambda: 1)
        mongo_client.get("/")
        app.BOARD.clear()
        place(PLAIN, DWARF)      # strength 12
        place(NEIGHBOUR, ORC)    # strength 8
        mongo_client.post("/phase/next")  # the Alliance's combat phase
        # A ratio of 6 against 1: the target is eliminated for certain.
        app.BOARD.remove(Hex(**NEIGHBOUR))
        place(NEIGHBOUR, "yzent-03-8-archers")  # strength 2
        answer = mongo_client.post("/combat",
                                   json={"target": NEIGHBOUR, "attackers": [PLAIN]}).json
        assert answer["resolved"] is True

        saved = dict(games.objects.first().placement)
        assert Hex(**NEIGHBOUR).key not in saved
        assert saved[Hex(**PLAIN).key] == DWARF

    def test_the_phase_register_is_saved_and_resumed(self, mongo_client, games, monkeypatch):
        monkeypatch.setattr(app, "roll_the_die", lambda: 1)
        mongo_client.get("/")
        app.BOARD.clear()
        place(PLAIN, DWARF)
        place(NEIGHBOUR, ORC)   # ratio 1-1, die 1 -> a retreat: nobody is eliminated
        mongo_client.post("/phase/next")
        assert mongo_client.post("/combat",
                                 json={"target": NEIGHBOUR,
                                       "attackers": [PLAIN]}).json["resolved"]

        game = games.objects.first()
        assert game.engaged_attackers == [Hex(**PLAIN).key]
        assert game.engaged_targets == [Hex(**NEIGHBOUR).key]

        app.REGISTER.reset()
        mongo_client.get("/")
        assert not app.REGISTER.can_attack(Hex(**PLAIN).key)
        assert not app.REGISTER.can_be_targeted(Hex(**NEIGHBOUR).key)

    def test_changing_phase_empties_the_register_in_base(self, mongo_client, games, monkeypatch):
        monkeypatch.setattr(app, "roll_the_die", lambda: 1)
        mongo_client.get("/")
        app.BOARD.clear()
        place(PLAIN, DWARF)
        place(NEIGHBOUR, ORC)
        mongo_client.post("/phase/next")
        mongo_client.post("/combat", json={"target": NEIGHBOUR, "attackers": [PLAIN]})
        mongo_client.post("/phase/next")
        game = games.objects.first()
        assert game.engaged_attackers == [] and game.engaged_targets == []


class TestNewGame:
    def test_it_lays_the_scenario_out_again_and_opens_a_second_document(self, mongo_client, games):
        mongo_client.get("/")
        origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
        destination = app.BOARD.moves(origin)[0]
        mongo_client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": app.BOARD.piece_on(origin).key})

        answer = mongo_client.post("/game/new").json
        assert len(answer["pieces"]) == len(app.SCENARIO)
        assert answer["phase"]["type"] == MOVEMENT
        assert games.objects.count() == 2
        # The most recent is the one just opened, and "/" resumes that one.
        assert dict(games.objects.first().placement) == app.SCENARIO.placement
        mongo_client.get("/")
        assert app.BOARD.piece_on(origin) is not None

    def test_two_games_of_the_same_second_stay_in_order(self, mongo_client, games):
        """The date alone is not enough to break the tie: two writes may share it.

        Without the identifier as a second criterion, "start again" then reload could resume the
        game one had just abandoned.
        """
        mongo_client.get("/")
        origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
        destination = app.BOARD.moves(origin)[0]
        mongo_client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": app.BOARD.piece_on(origin).key})
        mongo_client.post("/game/new")

        # Both games are dated to the same second, as if everything had been played in one go.
        instant = games.objects.first().updated_at
        games.objects.update(set__updated_at=instant)

        assert games.objects.count() == 2
        assert dict(games.objects.first().placement) == app.SCENARIO.placement


class TestRepository:
    """The repository's round trip alone, without going through a route."""

    def test_snapshotting_then_restoring_lands_on_the_same_game(self, mongo_application):
        with mongo_application.test_request_context():
            app.BOARD.clear()
            place(PLAIN, DWARF)
            app.TURN.restore(app.TURN.active_side, COMBAT, 3)
            app.REGISTER.record([Hex(**PLAIN).key], Hex(**NEIGHBOUR).key)
            state = app.snapshot_the_game()

            app.BOARD.clear()
            app.TURN.restart()
            app.REGISTER.reset()
            app.restore_the_game(state)

            assert app.snapshot_the_game() == state

    def test_saving_then_loading_returns_the_same_state(self, mongo_application):
        with mongo_application.test_request_context():
            app.BOARD.clear()
            place(PLAIN, DWARF)
            state = app.snapshot_the_game()
            app.game_repository().save(state)
            assert app.game_repository().load() == state

    def test_loading_finds_nothing_in_an_empty_base(self, mongo_application):
        with mongo_application.test_request_context():
            assert app.game_repository().load() is None


class TestPersistedSeats:
    """Who holds which side is part of the game: a restart does not empty the table."""

    def test_the_seats_are_written_with_the_game_and_resumed_with_it(self, mongo_client, games):
        # The fixture seats the test player at both sides; we rebuild the table with two.
        app.SEATS.clear().seat("alliance", DWARF_PLAYER).seat("tenebres", ORC_PLAYER)
        mongo_client.get("/")
        assert dict(games.objects.first().seats) == {"alliance": DWARF_PLAYER,
                                                     "tenebres": ORC_PLAYER}

        # The server restarts: the table in memory is lifted, only the base knows it.
        app.SEATS.clear()
        mongo_client.get("/")

        assert app.SEATS.occupant("alliance") == DWARF_PLAYER
        assert app.SEATS.occupant("tenebres") == ORC_PLAYER

    def test_a_game_saved_without_seats_stays_resumable(self, mongo_client, games):
        """Games from before players existed have no `seats` field: the table is empty."""
        mongo_client.get("/")
        games.objects.update(unset__seats=1)
        app.SEATS.clear().seat("alliance", DWARF_PLAYER)

        mongo_client.get("/")

        assert app.SEATS.is_free("alliance")

    def test_the_recorded_players_are_found_again_and_no_others(self, mongo_application):
        with mongo_application.test_request_context():
            repository = app.player_repository()
            repository.record({"discord_id": DWARF_PLAYER, "nickname": "Vorgtd", "avatar": None})
            assert repository.by_discord_id(DWARF_PLAYER)["nickname"] == "Vorgtd"
            assert repository.by_discord_id("999") is None

    def test_a_second_login_updates_the_nickname_without_creating_a_player(self, mongo_application):
        with mongo_application.test_request_context():
            from tenebrae.engine.models.player import Player
            repository = app.player_repository()
            repository.record({"discord_id": DWARF_PLAYER, "nickname": "Vorgtd"})
            repository.record({"discord_id": DWARF_PLAYER, "nickname": "Vorgtd le Grand"})
            assert Player.objects.count() == 1
            assert repository.by_discord_id(DWARF_PLAYER)["nickname"] == "Vorgtd le Grand"

class TestPersistedTilts:
    """The angle each counter lies at is part of the saved game.

    Without it in base, it would be redrawn at every reread of the board, and the forty-eight
    pieces would spin at every page reload. It only changes on a move.
    """

    def test_the_tilts_are_written_with_the_game_and_resumed_with_it(self, mongo_client, games):
        mongo_client.get("/")
        tilts = dict(games.objects.first().tilts)
        assert set(tilts) == set(app.SCENARIO.placement)
        assert tilts == app.BOARD.tilts

        before = app.BOARD.tilts

        # The server restarts: memory is empty, only the base knows how the pieces were lying.
        app.BOARD.clear()
        app.TURN.restart()
        mongo_client.get("/")

        assert app.BOARD.tilts == before

    def test_polling_the_game_does_not_lay_the_pieces_down_again(self, mongo_client):
        """What the player sees: the page lays the scene out again and the pieces do not spin.

        It is the `/game/state` poll that gives the browser the pieces to lay out again; it is
        played here twice in a row, around a load of "/" that rereads the saved game.
        """
        mongo_client.get("/")
        first = mongo_client.get("/game/state").json["pieces"]
        mongo_client.get("/")
        second = mongo_client.get("/game/state").json["pieces"]
        assert [piece["tilt"] for piece in second] == [piece["tilt"] for piece in first]

    def test_a_move_writes_the_new_tilt(self, mongo_client, games):
        mongo_client.get("/")
        origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
        destination = app.BOARD.moves(origin)[0]
        before = app.BOARD.tilt_on(origin)

        answer = mongo_client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": app.BOARD.piece_on(origin).key})
        assert answer.json["allowed"] is True

        tilts = dict(games.objects.first().tilts)
        assert origin.key not in tilts
        assert tilts[destination.key] == answer.json["tilt"] != before

    def test_a_game_saved_without_tilts_stays_resumable(self, mongo_client, games):
        """Games from before we started keeping them do not have the field.

        They resume all the same: the board draws the angles it lacks, and the first move played
        writes them. They are fixed from then on.
        """
        mongo_client.get("/")
        games.objects.update(unset__tilts=1)
        app.BOARD.clear()

        mongo_client.get("/")
        resumed = app.BOARD.tilts
        assert set(resumed) == set(app.SCENARIO.placement)

        mongo_client.post("/phase/next")  # a move played, hence a save
        assert dict(games.objects.first().tilts) == resumed

        app.BOARD.clear()
        mongo_client.get("/")
        assert app.BOARD.tilts == resumed


class TestPersistedGameAgainstTheAI:
    """The AI's seat travels in the seats dict, under its sentinel: nothing more to save, nothing
    more to resume."""

    def test_the_ais_seat_is_written_with_the_game_and_resumed_with_it(self, mongo_application,
                                                                       seat_the_player, games):
        from tenebrae.engine import ai

        client = mongo_application.test_client()
        seat_the_player(mongo_application, client, sides=["alliance"])
        answer = client.post("/game/new", json={"against_ai": True})
        assert answer.status_code == 200
        assert dict(games.objects.first().seats)["tenebres"] == ai.AI_PLAYER

        # The server restarts: the table in memory is lifted, only the base knows it.
        app.SEATS.clear()
        app.BOARD.clear()
        app.TURN.restart()
        client.get("/")

        assert app.SEATS.occupant("tenebres") == ai.AI_PLAYER


class TestPersistedView:
    """The map view: the only document of the application that is not part of the game.

    Its model and its repository belong to the application (`models/view.py`,
    `repositories/view.py`) and not to the engine - the engine does not know that an image, pixels
    or a window exist.
    """

    VIEW = {"scale": 0.37, "x": 3086.5, "y": 2551.25, "fitted": False}

    def test_adjusting_ones_view_writes_it_to_base(self, mongo_client):
        mongo_client.post("/view", json=self.VIEW)
        from tenebrae.application.models.view import View
        stored = View.objects.first()
        assert stored.discord_id == DEFAULT_IDENTITY["discord_id"]
        assert (stored.scale, stored.x, stored.y, stored.fitted) \
            == (self.VIEW["scale"], self.VIEW["x"], self.VIEW["y"], False)
        assert stored.updated_at is not None

    def test_the_view_is_resumed_after_a_restart(self, mongo_client):
        """That is the requirement: only the base knows where the player was."""
        mongo_client.post("/view", json=self.VIEW)
        assert read_hidden_field(mongo_client.get("/").get_data(as_text=True),
                                 "view") == self.VIEW

    def test_a_second_adjustment_does_not_create_a_second_document(self, mongo_client):
        """No zoom history is kept: one document per player."""
        mongo_client.post("/view", json=self.VIEW)
        mongo_client.post("/view", json={**self.VIEW, "scale": 1.0})
        from tenebrae.application.models.view import View
        assert View.objects.count() == 1
        assert View.objects.first().scale == 1.0


# --- Against a real MongoDB -----------------------------------------------------------------------
#
# Mongomock imitates the API, not the storage: it exercises neither the BSON encoding of the
# placement keys - "1,26,-27", commas and minus signs, where Mongo refuses a leading dot or dollar
# - nor the round trip of dates. These engine do, when a base is reachable; otherwise they skip
# themselves, and the suite goes on running without a server.
#
#     docker run -d --name tenebrae-mongo -p 27017:27017 mongo:7
#
# `MONGODB_URI_TEST` allows targeting another - a port distinct from the game's, for instance.

TEST_URI = os.environ.get("MONGODB_URI_TEST", "mongodb://localhost:27017/tenebrae_test")


def mongodb_is_reachable():
    """Says whether a real MongoDB answers at `TEST_URI`, without waiting more than a second."""
    import pymongo
    try:
        client = pymongo.MongoClient(TEST_URI, serverSelectionTimeoutMS=1000)
        client.admin.command("ping")
        client.close()
        return True
    except Exception:
        return False


class RealMongoConfig(TestingConfig):
    PERSISTENCE = "mongo"
    MONGODB_SETTINGS = {"host": TEST_URI}


@pytest.fixture
def real_mongo_client(seat_the_player):
    """An application plugged into a real MongoDB, and a base left clean on the way out."""
    if not mongodb_is_reachable():
        pytest.skip(f"no MongoDB reachable at {TEST_URI}")
    application = app.create_app(RealMongoConfig)
    from tenebrae.engine.models.game import Game
    from tenebrae.engine.models.player import Player
    from tenebrae.application.models.view import View
    Game.objects.delete()
    Player.objects.delete()
    View.objects.delete()
    client = application.test_client()
    seat_the_player(application, client)
    yield client
    Game.objects.delete()
    Player.objects.delete()
    View.objects.delete()
    mongoengine.disconnect_all()
    app.BOARD.clear()
    app.TURN.restart()
    app.REGISTER.reset()
    app.SEATS.clear()


class TestAgainstARealMongo:
    def test_the_squares_pass_into_base_as_they_are(self, real_mongo_client):
        """The placement keys are Mongo document keys: they must be admitted there."""
        real_mongo_client.get("/")
        from tenebrae.engine.models.game import Game
        placement = dict(Game.objects.first().placement)
        assert placement == app.SCENARIO.placement
        assert all("," in square for square in placement)
        assert any(square.count("-") for square in placement)

    def test_the_game_is_resumed_after_a_restart(self, real_mongo_client):
        real_mongo_client.get("/")
        origin = Hex.from_key(next(iter(app.SCENARIO.placement)))
        destination = app.BOARD.moves(origin)[0]
        real_mongo_client.post("/move", json={
            "origin": origin.to_dict(), "destination": destination.to_dict(),
            "piece": app.BOARD.piece_on(origin).key})
        real_mongo_client.post("/phase/next")

        # The server restarts: only the base knows where the game stood.
        app.BOARD.clear()
        app.TURN.restart()
        real_mongo_client.get("/")

        assert app.BOARD.piece_on(origin) is None
        assert app.BOARD.piece_on(destination) is not None
        assert app.TURN.phase_type == COMBAT

    def test_the_dates_come_back_readable(self, real_mongo_client):
        real_mongo_client.get("/")
        from tenebrae.engine.models.game import Game
        game = Game.objects.first()
        assert game.created_at is not None
        assert game.updated_at >= game.created_at

    def test_the_view_passes_through_a_real_mongo(self, real_mongo_client):
        """Floats and a boolean: nothing exotic, but the table really is written."""
        view = {"scale": 0.37, "x": 3086.5, "y": 2551.25, "fitted": False}
        real_mongo_client.post("/view", json=view)
        assert read_hidden_field(real_mongo_client.get("/").get_data(as_text=True), "view") == view
