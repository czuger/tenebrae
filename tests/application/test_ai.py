"""The game against the AI: its creation, the seat it holds, and its turn played by the server.

The AI has neither a session nor a Discord account: it occupies its seat under the `ai.AI_PLAYER`
sentinel, and it is the server that plays its turn - in the request that hands it play, never over
HTTP. The die is fixed by `monkeypatch` on `current_game.roll_the_die`, as in the combat engine:
at equal die, the AI replays the same game.
"""

import time

import pytest

from tenebrae.application import current_game
from tenebrae.application.discord_client import DEFAULT_IDENTITY
from tenebrae.engine import ai
from tenebrae.engine.piece import CATALOGUE
from tests.engine.plains import ring_of, well_surrounded_plain

ELF = "elfes-01-5-infanteries"             # alliance, strength 7, movement 4
ORC = "orques-01-15-infanteries"           # darkness, strength 8, movement 4

# What the test that holds the pause puts in place of the half second the AI waits in play: long
# enough to be measured, short enough not to be felt in the suite.
A_SHORT_PAUSE = 0.05

# A second human player, to exercise sides that are already held.
GRISHNAK = DEFAULT_IDENTITY | {"discord_id": "100000000000000002", "nickname": "Grishnak"}


@pytest.fixture
def alliance_client(application, seat_the_player):
    """A logged-in client holding only the Alliance - the player of a game against the AI."""
    client = application.test_client()
    seat_the_player(application, client, sides=["alliance"])
    return client


@pytest.fixture
def darkness_client(application, seat_the_player):
    """The same, seated at the Darkness: the AI will get the Alliance, which opens the scenario."""
    client = application.test_client()
    seat_the_player(application, client, sides=["tenebres"])
    return client


@pytest.fixture
def seatless_client(application, seat_the_player):
    """Logged in, but standing: enough to exercise `seat_required`."""
    client = application.test_client()
    seat_the_player(application, client, sides=[])
    return client


class TestNewGameAgainstTheAI:
    def test_the_anonymous_visitor_is_refused(self, anonymous_client, deserted_map):
        assert anonymous_client.post("/game/new", json={"against_ai": True}).status_code == 401

    def test_without_a_seat_it_is_refused(self, seatless_client, deserted_map):
        answer = seatless_client.post("/game/new", json={"against_ai": True})
        assert answer.status_code == 403

    def test_a_side_held_by_a_human_is_not_given_away(self, alliance_client, deserted_map):
        current_game.SEATS.seat("tenebres", GRISHNAK["discord_id"])
        answer = alliance_client.post("/game/new", json={"against_ai": True})
        assert answer.status_code == 409
        assert answer.json["message"] == "Ce camp est déjà tenu."
        # Refused means left as it was: the set-up has not been rebuilt.
        assert len(current_game.BOARD) == 0
        assert current_game.SEATS.occupant("tenebres") == GRISHNAK["discord_id"]

    def test_the_game_is_created_and_the_ai_seated(self, alliance_client, deserted_map):
        answer = alliance_client.post("/game/new", json={"against_ai": True})
        assert answer.status_code == 200
        assert current_game.SEATS.occupant("tenebres") == ai.AI_PLAYER
        assert answer.json["seats"]["tenebres"] == ai.AI_NAME
        # The Alliance - the human player - opens the scenario: the AI has played nothing.
        assert answer.json["phase"]["side"] == "alliance"
        assert current_game.BOARD.to_dict() == current_game.SCENARIO.placement

    def test_the_ai_plays_immediately_when_it_opens(self, darkness_client, deserted_map,
                                                    monkeypatch):
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        answer = darkness_client.post("/game/new", json={"against_ai": True})
        assert answer.status_code == 200
        assert current_game.SEATS.occupant("alliance") == ai.AI_PLAYER
        # The AI played its opening turn straight away: play is with the Darkness, and the pieces
        # in the answer are those it left, not those of the set-up.
        assert answer.json["phase"]["side"] == "tenebres"
        assert answer.json["phase"]["type"] == "mouvement"
        assert current_game.BOARD.to_dict() != current_game.SCENARIO.placement

    def test_starting_again_against_the_ai_stays_allowed(self, alliance_client, deserted_map):
        alliance_client.post("/game/new", json={"against_ai": True})
        answer = alliance_client.post("/game/new", json={"against_ai": True})
        assert answer.status_code == 200
        assert current_game.SEATS.occupant("tenebres") == ai.AI_PLAYER

    def test_without_the_flag_nothing_changes(self, client, deserted_map):
        answer = client.post("/game/new")
        assert answer.status_code == 200
        assert ai.AI_PLAYER not in (current_game.SEATS.occupant(side)
                                    for side in current_game.SCENARIO.sides)


class TestTriggeringTheAI:
    @pytest.fixture
    def face_to_face(self, deserted_map):
        """An elf of the human player and an orc of the AI two squares apart."""
        a = well_surrounded_plain()
        *_, further = ring_of(a)
        current_game.BOARD.place(a, CATALOGUE[ELF])
        current_game.BOARD.place(further, CATALOGUE[ORC])
        current_game.SEATS.seat("tenebres", ai.AI_PLAYER)
        return a, further

    def test_the_ai_does_not_play_while_play_is_human(self, alliance_client, face_to_face):
        a, further = face_to_face
        # End of the Alliance's movement: its combat phase begins, the AI has nothing to play.
        answer = alliance_client.post("/phase/next")
        assert (answer.json["side"], answer.json["type"]) == ("alliance", "combat")
        assert current_game.BOARD.piece_on(further).key == ORC

    def test_the_ai_plays_its_turn_when_play_comes_to_it(self, alliance_client, face_to_face,
                                                         monkeypatch):
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        a, further = face_to_face
        alliance_client.post("/phase/next")
        version_before = current_game.VERSION
        # End of the Alliance's combat: play passes to the Darkness, hence to the AI, which plays
        # its whole turn - the orc marches into contact and engages the elf (8 against 7: 1-1,
        # die 1, `DR`: the elf falls back one square) - then hands play back.
        answer = alliance_client.post("/phase/next")
        assert (answer.json["side"], answer.json["type"]) == ("alliance", "mouvement")
        assert answer.json["number"] == 2
        assert current_game.BOARD.piece_on(further) is None
        assert any(neighbour for neighbour in a.neighbours()
                   if (placed := current_game.BOARD.piece_on(neighbour)) and placed.key == ORC)
        # The elf has given ground: it has left its square for one of those around it.
        assert current_game.BOARD.piece_on(a) is None
        assert any(neighbour for neighbour in a.neighbours()
                   if (placed := current_game.BOARD.piece_on(neighbour)) and placed.key == ELF)
        assert current_game.VERSION > version_before

    def test_each_action_of_the_ai_is_pushed_as_it_is_played(self, alliance_client, face_to_face,
                                                             monkeypatch):
        """The turn is played inside one request, and a single push would show the board the AI
        left behind rather than the turn it played: one per move, one per combat."""
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        pushed = []
        pushing = current_game.mark_a_move

        def counted():
            pushed.append(current_game.VERSION)
            return pushing()

        monkeypatch.setattr(current_game, "mark_a_move", counted)
        alliance_client.post("/phase/next")
        pushed.clear()
        alliance_client.post("/phase/next")

        # The phase change that hands play over, then the AI's move, then its combat, then the
        # save that ends its turn.
        assert len(pushed) == 4

    def test_the_ai_waits_between_two_of_its_actions(self, alliance_client, face_to_face,
                                                     monkeypatch):
        """Half a second in play, a fiftieth of one here. The pause goes **between** two actions:
        two actions are one pause, and a turn does not begin by waiting."""
        monkeypatch.setattr(current_game, "roll_the_die", lambda: 1)
        monkeypatch.setattr(current_game, "PAUSE_BETWEEN_AI_ACTIONS", A_SHORT_PAUSE)
        alliance_client.post("/phase/next")

        started = time.monotonic()
        alliance_client.post("/phase/next")
        waited = time.monotonic() - started

        # Its move and its combat: one pause between the two of them.
        assert waited >= A_SHORT_PAUSE

    def test_the_ais_side_cannot_be_taken(self, application, alliance_client, face_to_face,
                                          seat_the_player):
        second = application.test_client()
        seat_the_player(application, second, identity=GRISHNAK, sides=[])
        answer = second.post("/game/seat", json={"side": "tenebres"})
        assert answer.status_code == 409
        assert answer.json["message"] == "Ce camp est déjà tenu."


class TestTheTableWithTheAI:
    def test_the_ais_seat_is_shown_occupied(self, alliance_client, deserted_map):
        alliance_client.post("/game/new", json={"against_ai": True})
        table = alliance_client.get("/game/state").json["table"]
        assert table["seats"]["tenebres"] == ai.AI_NAME
