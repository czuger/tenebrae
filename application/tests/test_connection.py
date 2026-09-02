"""Logging in through Discord, taking a seat, and what the server refuses to the rest of the world.

None of these tests leaves the machine: the test configuration plugs in the fake Discord client,
whose authorization URL redirects to **our own return route**. The flow therefore really unfolds -
the anti-CSRF state, the code exchange, the identity read - without a single packet leaving for
discord.com.
"""

from urllib.parse import parse_qs, urlparse

import pytest

import app
from config import TestingConfig
from discord_client import DEFAULT_IDENTITY, DiscordError

# A second account, to seat someone opposite. Its identifier is not in
# `TestingConfig.ADMINISTRATORS`: it is the ordinary player of the administration tests.
OTHER_PLAYER = {"discord_id": "100000000000000002", "nickname": "Grishnak",
                "display_name": None, "avatar": None, "email": None}

ALLIANCE, DARKNESS = "alliance", "tenebres"

# A square of the scenario and one of its neighbours: enough to form a well-formed move request,
# which only the authorization refusal must stop.
PLAIN = {"q": 1, "r": 26, "s": -27}
NEIGHBOUR = {"q": 2, "r": 26, "s": -28}


@pytest.fixture(autouse=True)
def empty_table(deserted_map, application):
    """Every test starts from a lifted table, a deserted board and a fake client wiped clean.

    The fake Discord client is carried by the application, of session scope: a test that made it
    serve another account would leave it that way for everyone.
    """
    app.SEATS.clear()
    application.extensions["discord"].served_identity = dict(DEFAULT_IDENTITY)
    yield
    app.SEATS.clear()
    application.extensions["discord"].served_identity = dict(DEFAULT_IDENTITY)


@pytest.fixture
def log():
    """The log queue, emptied before and after: the test reads only what it caused."""
    app.LOG_MEMORY.lines.clear()
    yield app.LOG_MEMORY.lines
    app.LOG_MEMORY.lines.clear()


def log_in(client):
    """Unrolls the whole flow, as a browser would: /login then the return."""
    departure = client.get("/login")
    return client.get(departure.headers["Location"])


def state_of(answer):
    """The state the redirect carries in its URL."""
    return parse_qs(urlparse(answer.headers["Location"]).query)["state"][0]


# --- The OAuth2 flow -----------------------------------------------------------------------------


def test_logging_in_redirects_with_a_state(anonymous_client):
    answer = anonymous_client.get("/login")
    assert answer.status_code == 302
    assert state_of(answer)


def test_two_logins_do_not_draw_the_same_state(anonymous_client):
    first = state_of(anonymous_client.get("/login"))
    second = state_of(anonymous_client.get("/login"))
    assert first != second


def test_the_return_opens_the_session_and_records_the_player(anonymous_client, application):
    answer = log_in(anonymous_client)
    assert answer.status_code == 302
    with anonymous_client.session_transaction() as session:
        assert session["joueur"] == DEFAULT_IDENTITY["discord_id"]
    player = application.extensions["player_repository"].by_discord_id(
        DEFAULT_IDENTITY["discord_id"])
    assert player["nickname"] == DEFAULT_IDENTITY["nickname"]


def test_a_second_login_updates_the_nickname(anonymous_client, application):
    log_in(anonymous_client)
    application.extensions["discord"].served_identity |= {"nickname": "Joueuse d'essai, deuxième"}
    log_in(anonymous_client)
    player = application.extensions["player_repository"].by_discord_id(
        DEFAULT_IDENTITY["discord_id"])
    assert player["nickname"] == "Joueuse d'essai, deuxième"


def test_a_return_without_a_state_is_refused(anonymous_client):
    assert anonymous_client.get("/login/return?code=x").status_code == 400


def test_a_state_that_does_not_match_is_refused(anonymous_client):
    anonymous_client.get("/login")
    answer = anonymous_client.get("/login/return?code=x&state=an-invented-state")
    assert answer.status_code == 400
    with anonymous_client.session_transaction() as session:
        assert "joueur" not in session


def test_the_state_serves_only_once(anonymous_client):
    """Replaying the return must find nothing left to compare the state against."""
    departure = anonymous_client.get("/login")
    return_url = departure.headers["Location"]
    assert anonymous_client.get(return_url).status_code == 302
    assert anonymous_client.get(return_url).status_code == 400


def test_a_return_without_a_code_is_refused(anonymous_client):
    departure = anonymous_client.get("/login")
    answer = anonymous_client.get(f"/login/return?state={state_of(departure)}")
    assert answer.status_code == 400


def test_a_refusal_on_discords_page_brings_back_to_the_map(anonymous_client):
    """"Cancel" at Discord: we come back to the board, with no session and no error."""
    anonymous_client.get("/login")
    answer = anonymous_client.get("/login/return?error=access_denied")
    assert answer.status_code == 302
    with anonymous_client.session_transaction() as session:
        assert "joueur" not in session


def test_discords_error_comes_back_up_whole(anonymous_client, application, monkeypatch):
    """No mute 502: the error comes back up as it is, message included, so it can be read."""
    def fail(_code):
        raise DiscordError("Discord answered 400 Bad Request: invalid_grant")

    monkeypatch.setattr(application.extensions["discord"], "exchange_code", fail)
    departure = anonymous_client.get("/login")
    with pytest.raises(DiscordError, match="invalid_grant"):
        anonymous_client.get(departure.headers["Location"])


# The host `DISCORD_REDIRECT_URI` expects under the test configuration, and another one.
EXPECTED_HOST = "http://127.0.0.1:5000/"
OTHER_HOST = "http://localhost:5000/"


def test_a_departure_from_a_host_other_than_the_returns_is_logged(anonymous_client, log):
    """The case of the map opened on `localhost` when Discord redirects to `127.0.0.1`: two sites
    for the browser, and the cookie of one does not come back to the other. It is at departure that
    both hosts are known, so at departure that the log must say so."""
    anonymous_client.get("/login", base_url=OTHER_HOST)
    assert log[-1]["text"] == ("Connexion : départ depuis localhost:5000, mais Discord "
                              "renverra sur 127.0.0.1:5000 — le cookie de session posé "
                              "ici ne reviendra pas ; ouvrir la carte sur "
                              "http://127.0.0.1:5000/")


def test_a_departure_from_the_returns_host_says_nothing(anonymous_client, log):
    anonymous_client.get("/login", base_url=EXPECTED_HOST)
    assert not log


def test_a_state_absent_from_the_session_is_logged(anonymous_client, log):
    anonymous_client.get("/login/return?code=x&state=a-state")
    assert log[-1]["text"] == ("Connexion refusée : état d'authentification absent de la "
                              "session (hôte localhost, cookie de session absent)")


def test_a_cookie_signed_by_another_key_is_called_unreadable(anonymous_client, log):
    """The case of a changed SECRET_KEY: the cookie comes back, but the session it carries is
    lost - and the log must say so, rather than "absent", which would send one looking
    elsewhere."""
    anonymous_client.set_cookie("session", "a-cookie-signed-by-another-key")
    anonymous_client.get("/login/return?code=x&state=a-state")
    assert log[-1]["text"] == ("Connexion refusée : état d'authentification absent de la "
                              "session (hôte localhost, cookie de session présent mais "
                              "illisible — signé par une autre SECRET_KEY ?)")


def test_a_session_rewritten_meanwhile_shows_what_it_carries(anonymous_client, log):
    """The case of a cookie rewritten by another request: the session is readable, without a
    state, and the log lists its keys - here those of a logged-in player - to say where it comes
    from."""
    log_in(anonymous_client)
    anonymous_client.get("/login/return?code=x&state=a-state")
    assert log[-1]["text"] == ("Connexion refusée : état d'authentification absent de la "
                              "session (hôte localhost, cookie de session lisible, "
                              "session portant _permanent, joueur)")


def test_a_state_absent_from_the_request_is_logged(anonymous_client, log):
    anonymous_client.get("/login")
    anonymous_client.get("/login/return?code=x")
    assert log[-1]["text"] == ("Connexion refusée : état d'authentification absent de la "
                              "requête (hôte localhost, cookie de session lisible, "
                              "session vide)")


def test_a_different_state_is_logged(anonymous_client, log):
    anonymous_client.get("/login")
    anonymous_client.get("/login/return?code=x&state=an-invented-state")
    assert log[-1]["text"] == ("Connexion refusée : état d'authentification différent de "
                              "celui de la session (hôte localhost, cookie de session "
                              "lisible, session vide)")


def test_a_missing_code_is_logged(anonymous_client, log):
    departure = anonymous_client.get("/login")
    anonymous_client.get(f"/login/return?state={state_of(departure)}")
    assert log[-1]["text"] == "Connexion refusée : code d'autorisation absent de la requête"


def test_an_answer_that_does_not_touch_the_session_does_not_rewrite_the_cookie(anonymous_client):
    """The heart of the bug: a logged-in player has a permanent session, which Flask rewrote into
    the cookie at every response. A request that left with the old session before `/login` and
    answered afterwards then erased the OAuth2 state. Only responses that modify the session must
    set the cookie."""
    log_in(anonymous_client)
    for route in ("/", "/game/state", "/game/state?version=0"):
        assert "Set-Cookie" not in anonymous_client.get(route).headers, route


def test_setting_the_state_rewrites_the_cookie(anonymous_client):
    """The counterpart: `/login` modifies the session, and its cookie must go out."""
    log_in(anonymous_client)
    assert "Set-Cookie" in anonymous_client.get("/login").headers


def test_the_access_token_never_goes_into_the_session(anonymous_client):
    """The session cookie is signed, not encrypted: nothing secret has its place there.

    `_permanent` is Flask's, which notes the requested lifetime that way; the rest must come down
    to the player's identifier.
    """
    log_in(anonymous_client)
    with anonymous_client.session_transaction() as session:
        assert set(session) == {"joueur", "_permanent"}


def test_logging_out_empties_the_session(client):
    assert client.post("/logout").json == {"connected": False}
    with client.session_transaction() as session:
        assert "joueur" not in session


def test_logging_out_does_not_give_up_the_seat(client):
    """One comes back to sit in it: leaving the table is a separate gesture."""
    client.post("/logout")
    assert app.SEATS.occupant(ALLIANCE) == DEFAULT_IDENTITY["discord_id"]


# --- What an anonymous visitor sees ---------------------------------------------------------------


def test_an_anonymous_visitor_sees_the_map(anonymous_client):
    assert anonymous_client.get("/").status_code == 200


def test_an_anonymous_visitor_consults_the_moves(anonymous_client):
    answer = anonymous_client.get("/moves", query_string=PLAIN)
    assert answer.status_code == 200


def test_an_anonymous_visitor_moves_nothing(anonymous_client, deserted_map):
    deserted_map.place(app.Hex(**PLAIN), app.CATALOGUE["nains-01-5-infanteries"])
    answer = anonymous_client.post("/move", json={
        "origin": PLAIN, "destination": NEIGHBOUR, "piece": "nains-01-5-infanteries"})
    assert answer.status_code == 401
    assert deserted_map.piece_on(app.Hex(**PLAIN)) is not None


def test_an_anonymous_visitor_does_not_change_the_phase(anonymous_client):
    assert anonymous_client.post("/phase/next").status_code == 401


def test_an_anonymous_visitor_does_not_restart_the_game(anonymous_client):
    assert anonymous_client.post("/game/new").status_code == 401


# --- Each to their own side ----------------------------------------------------------------------


def test_one_does_not_play_the_side_one_does_not_hold(application, seat_the_player, deserted_map):
    """The Darkness player moves nothing during the Alliance's phase."""
    client = application.test_client()
    seat_the_player(application, client, identity=OTHER_PLAYER, sides=[DARKNESS])
    deserted_map.place(app.Hex(**PLAIN), app.CATALOGUE["nains-01-5-infanteries"])

    answer = client.post("/move", json={
        "origin": PLAIN, "destination": NEIGHBOUR, "piece": "nains-01-5-infanteries"})

    assert answer.status_code == 403
    assert "de jouer" in answer.json["message"]
    assert deserted_map.piece_on(app.Hex(**PLAIN)) is not None


def test_a_logged_in_player_without_a_seat_does_not_play(application, seat_the_player):
    client = application.test_client()
    seat_the_player(application, client, sides=[])
    assert client.post("/phase/next").status_code == 403


def test_the_active_side_plays(client):
    """The counterpart of the previous test: seated at the right side, the route goes through."""
    assert client.post("/phase/next").status_code == 200


# --- Taking a seat -------------------------------------------------------------------------------


@pytest.fixture
def seatless_client(application, seat_the_player):
    """A logged-in player, but standing: nobody holds anything yet."""
    client = application.test_client()
    seat_the_player(application, client, sides=[])
    return client


def test_sitting_down_takes_the_side(seatless_client):
    answer = seatless_client.post("/game/seat", json={"side": ALLIANCE})
    assert answer.status_code == 200
    assert answer.json["seated"] is True
    assert answer.json["sides"] == [ALLIANCE]
    assert app.SEATS.occupant(ALLIANCE) == DEFAULT_IDENTITY["discord_id"]


def test_the_table_says_who_holds_what_by_their_nickname(seatless_client):
    """The browser receives nicknames, never Discord identifiers."""
    answer = seatless_client.post("/game/seat", json={"side": ALLIANCE})
    assert answer.json["seats"] == {ALLIANCE: DEFAULT_IDENTITY["nickname"], DARKNESS: None}
    assert DEFAULT_IDENTITY["discord_id"] not in answer.get_data(as_text=True)


def test_a_side_unknown_to_the_scenario_is_refused(seatless_client):
    assert seatless_client.post("/game/seat", json={"side": "dragons"}).status_code == 400


def test_a_second_side_is_refused_to_whoever_already_holds_one(seatless_client):
    seatless_client.post("/game/seat", json={"side": ALLIANCE})
    answer = seatless_client.post("/game/seat", json={"side": DARKNESS})
    assert answer.status_code == 409
    assert app.SEATS.is_free(DARKNESS)


def test_sitting_back_down_in_ones_own_seat_makes_no_fuss(seatless_client):
    seatless_client.post("/game/seat", json={"side": ALLIANCE})
    assert seatless_client.post("/game/seat", json={"side": ALLIANCE}).status_code == 200


def test_an_occupied_seat_is_not_taken_over(application, seat_the_player, seatless_client):
    other = application.test_client()
    seat_the_player(application, other, identity=OTHER_PLAYER, sides=[ALLIANCE])

    answer = seatless_client.post("/game/seat", json={"side": ALLIANCE})

    assert answer.status_code == 409
    assert app.SEATS.occupant(ALLIANCE) == OTHER_PLAYER["discord_id"]


def test_both_sides_are_taken_by_two_players(application, seat_the_player, seatless_client):
    other = application.test_client()
    seat_the_player(application, other, identity=OTHER_PLAYER, sides=[])
    seatless_client.post("/game/seat", json={"side": ALLIANCE})

    answer = other.post("/game/seat", json={"side": DARKNESS})

    assert answer.status_code == 200
    assert answer.json["seats"] == {ALLIANCE: DEFAULT_IDENTITY["nickname"],
                                    DARKNESS: OTHER_PLAYER["nickname"]}


def test_leaving_gives_the_seat_back(client):
    answer = client.post("/game/seat/leave")
    assert answer.json["seated"] is False
    assert app.SEATS.is_free(ALLIANCE) and app.SEATS.is_free(DARKNESS)


def test_an_anonymous_visitor_does_not_take_a_seat(anonymous_client):
    assert anonymous_client.post("/game/seat", json={"side": ALLIANCE}).status_code == 401


def test_restarting_keeps_both_players_at_the_table(client):
    """Starting again from the set-up sends nobody away: they are the same two people."""
    client.post("/game/new")
    assert app.SEATS.sides_of(DEFAULT_IDENTITY["discord_id"]) == list(app.SCENARIO.sides)


# --- Fixing the map ------------------------------------------------------------------------------


def test_fixing_the_map_requires_being_logged_in(anonymous_client):
    assert anonymous_client.get("/admin/map_fix").status_code == 401
    assert anonymous_client.post("/admin/map_fix", json={}).status_code == 401


def test_fixing_the_map_is_refused_to_an_ordinary_player(application, seat_the_player):
    client = application.test_client()
    seat_the_player(application, client, identity=OTHER_PLAYER, sides=[DARKNESS])

    answer = client.get("/admin/map_fix")

    assert answer.status_code == 403
    assert "ADMIN_DISCORD_IDS" in answer.json["message"]


def test_fixing_the_map_is_open_to_an_administrator(client):
    assert client.get("/admin/map_fix").status_code == 200


# --- Building the application ---------------------------------------------------------------------
#
# The suite runs under `TestingConfig`, which plugs in the fake client: nothing would otherwise
# exercise the path the server really takes.


class GameConfig(TestingConfig):
    """The test configuration, but with the real Discord client - the one that speaks to the
    network.

    No test calls it: we only want to make sure that this path of `create_app` builds, and that the
    file that speaks to Discord imports.
    """

    AUTHENTICATION = "discord"
    DISCORD_CLIENT_ID = "000"
    DISCORD_CLIENT_SECRET = "worthless-secret"
    DISCORD_REDIRECT_URI = "http://127.0.0.1:5000/login/return"


def test_the_game_configuration_plugs_in_the_real_discord_client():
    from discord_client import DiscordClient
    application = app.create_app(GameConfig)
    assert isinstance(application.extensions["discord"], DiscordClient)


def test_the_real_client_really_sends_to_discord():
    """The authorization URL, the only thing that can be checked without calling Discord."""
    application = app.create_app(GameConfig)
    with application.test_request_context():
        url = application.extensions["discord"].authorization_url("a-state")
    assert url.startswith("https://discord.com/oauth2/authorize?")
    assert "state=a-state" in url and "scope=identify" in url
    assert "client_secret" not in url  # the secret never leaves in a URL


def test_the_real_client_introduces_itself_to_discord(monkeypatch):
    """Every outgoing call carries a User-Agent: Cloudflare turns `urllib`'s away with a 403."""
    import discord_client

    requests = []

    class FakeAnswer:
        def read(self):
            return b'{"access_token": "token"}'

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def fake_urlopen(request, timeout=None):
        requests.append(request)
        return FakeAnswer()

    monkeypatch.setattr(discord_client, "urlopen", fake_urlopen)
    client = discord_client.DiscordClient("000", "secret", "http://127.0.0.1:5000/return")
    client.exchange_code("a-code")
    assert requests and requests[0].get_header("User-agent") == discord_client.USER_AGENT


def test_without_a_secret_key_the_application_refuses_to_start():
    """Better a failure at start-up than an error at the first click on "se connecter"."""
    class WithoutAKey(TestingConfig):
        SECRET_KEY = None

    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        app.create_app(WithoutAKey)
