"""The general log: the server's own trace, and what it must never write.

Three things are checked here, and they are not the same thing:

- what is **written**: every request with its answer in full, the whole of the connection flow,
  the games opened and saved - each line naming its variables and their contents;
- what is **never** written: an OAuth state, an authorization code, an access token, a database
  password - hidden by the name they travel under, wherever they sit;
- what stays **elsewhere**: none of this reaches the browser's column, which is the game log's, and
  a streamed answer is left untouched rather than read to be logged.

The lines are read through `caplog` and not off the disk: `logs/general.log` is the same file for
the whole run, and a test that read it would be reading every other test's trace as well.
"""

import json
import logging

import pytest

from tenebrae.application import current_game
from tenebrae.application.app import where_the_base_is
from tenebrae.application.discord_client import DEFAULT_IDENTITY
from tenebrae.application.logs import general_log
from tenebrae.application.logs.battle_log import log_lines
from tenebrae.application.logs.general_log import (GENERAL_LOG, cut, hidden, is_a_secret, note,
                                                   readable, sanitised, shown, spell_out,
                                                   the_level, without_the_secrets)

LOGGER_NAME = "tenebrae.general"


@pytest.fixture(autouse=True)
def the_log_is_listened_to(caplog):
    """Captures the general log at DEBUG, whatever `LOG_LEVEL` the machine's `.env` carries.

    The level is a deliberate default and not an invariant of the suite: it is checked apart, on
    `the_level`, with the environment in hand.
    """
    caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
    previous = GENERAL_LOG.level
    GENERAL_LOG.setLevel(logging.DEBUG)
    yield caplog
    GENERAL_LOG.setLevel(previous)


def general_lines(caplog):
    """Every line the general log wrote, that one alone."""
    return [record.getMessage() for record in caplog.records if record.name == LOGGER_NAME]


def one_line(caplog, beginning):
    """The single line starting with `beginning`, or a failure naming what there was instead."""
    found = [line for line in general_lines(caplog) if line.startswith(beginning)]
    assert len(found) == 1, f"{len(found)} lines start with {beginning!r}: {found}"
    return found[0]


def lines_starting(caplog, beginning):
    """Every line starting with `beginning`, in the order they were written."""
    return [line for line in general_lines(caplog) if line.startswith(beginning)]


# --- The level -------------------------------------------------------------------------------


def test_the_level_is_debug_unless_the_environment_says_otherwise(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    assert the_level() == logging.DEBUG


def test_the_level_can_be_raised_from_the_environment(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "info")
    assert the_level() == logging.INFO


def test_an_unreadable_level_does_not_cost_a_start_up(monkeypatch):
    """A mistyped level falls back to DEBUG rather than raise while the module is being imported."""
    monkeypatch.setenv("LOG_LEVEL", "bavard")
    assert the_level() == logging.DEBUG


# --- What a line looks like ------------------------------------------------------------------


def test_a_line_names_its_variables_and_writes_their_contents():
    assert spell_out("Something happened", {"side": "alliance", "units": 12}) == (
        "Something happened — side='alliance', units=12")


def test_a_line_with_no_variable_is_the_message_alone():
    assert spell_out("Something happened", {}) == "Something happened"


def test_a_string_is_written_in_its_quotes():
    """An empty string, a trailing space and a stray newline are read in the quotes, not without."""
    assert shown("nickname", "") == "''"
    assert shown("nickname", "Nains ") == "'Nains '"


def test_a_structure_is_written_as_json_with_its_accents():
    assert shown("armies", {"camp": "ténèbres"}) == '{"camp": "ténèbres"}'


def test_what_json_refuses_is_written_all_the_same():
    assert shown("piece", object()).startswith("\"<object object at")


def test_a_secret_is_named_and_measured_but_never_written():
    assert shown("access_token", "sesame-1234") == "<hidden, 11 characters>"
    assert shown("oauth_state", None) == "<absent>"


def test_a_secret_inside_a_body_is_hidden_where_it_sits():
    """The `code` and the `state` of the return from Discord are fields, not variables."""
    written = shown("query", {"code": "fake-code", "state": "abcdef", "scenario": 4})
    assert "fake-code" not in written and "abcdef" not in written
    assert '"scenario": 4' in written
    assert "<hidden, 9 characters>" in written


def test_a_secret_nested_deeper_is_hidden_too():
    assert "sesame" not in json.dumps(sanitised({"answer": [{"access_token": "sesame"}]}))


def test_what_is_not_a_secret_is_left_alone():
    assert is_a_secret("scenario") is False
    assert is_a_secret("Authorization") is True
    assert readable(None) == "None" and readable(12) == "12"


def test_a_value_too_long_is_cut_and_says_by_how_much():
    written = cut("x" * (general_log.VALUE_LIMIT + 40))
    assert written.startswith("x" * general_log.VALUE_LIMIT)
    assert written.endswith(f"… (cut, {general_log.VALUE_LIMIT + 40} characters in all)")


def test_a_url_travels_without_the_credentials_in_it():
    written = without_the_secrets(
        "https://discord.com/oauth2/authorize?client_id=42&scope=identify&state=abcdef")
    assert "abcdef" not in written
    assert "client_id=42" in written and "scope=identify" in written
    assert without_the_secrets("/game/17") == "/game/17"


def test_the_redirect_to_discord_carries_no_state_into_the_log(anonymous_client, caplog):
    """The `Location` header is where the state travels: it is scrubbed like everything else."""
    anonymous_client.get("/login")
    with anonymous_client.session_transaction() as session:
        state = session["etat_oauth"]

    line = one_line(caplog, "Answer — method='GET', path='/login'")
    assert state not in line
    assert "state=<hidden, 43 characters>" in line


def test_a_database_uri_travels_without_its_password():
    assert where_the_base_is("mongodb://localhost:27017/tenebrae") == (
        "mongodb://localhost:27017/tenebrae")
    hidden_one = where_the_base_is("mongodb://player:sesame@cluster/tenebrae")
    assert "sesame" not in hidden_one and hidden_one.endswith("@cluster/tenebrae")


# --- Every request, and its answer in full -----------------------------------------------------


def test_a_request_writes_what_came_in(client, caplog):
    client.post("/game/new", json={"side": "alliance", "against_ai": False})

    line = one_line(caplog, "Request — method='POST', path='/game/new'")
    assert "endpoint='game.new_game'" in line
    assert '"side": "alliance"' in line
    assert '"against_ai": false' in line
    assert f"visitor='{DEFAULT_IDENTITY['discord_id']}'" in line


def test_the_answer_is_written_out(client, caplog):
    client.get("/game/state")

    line = one_line(caplog, "Answer — method='GET', path='/game/state'")
    assert "status=200" in line and "took=" in line
    assert 'body={"changed": true' in line


def test_an_answer_longer_than_the_cut_says_what_was_left_out(client, caplog):
    """A board snapshot is some twenty kilobytes; the line says so rather than carry them all."""
    client.get("/game/state")

    line = one_line(caplog, "Answer — method='GET', path='/game/state'")
    assert "characters in all)" in line
    assert len(line) < general_log.VALUE_LIMIT + 500


def test_the_cut_can_be_lifted_altogether(client, caplog, monkeypatch):
    """`LOG_VALUE_LIMIT=0`: every answer whole, however long."""
    monkeypatch.setattr(general_log, "VALUE_LIMIT", 0)
    answer = client.get("/game/state")

    line = one_line(caplog, "Answer — method='GET', path='/game/state'")
    assert f'"version": {answer.get_json()["version"]}' in line
    assert "characters in all)" not in line


def test_the_cut_is_read_from_the_environment(monkeypatch):
    monkeypatch.setenv("LOG_VALUE_LIMIT", "0")
    assert general_log.the_limit() == 0
    monkeypatch.setenv("LOG_VALUE_LIMIT", "long")
    assert general_log.the_limit() == general_log.DEFAULT_VALUE_LIMIT


def test_a_refusal_is_written_with_the_sentence_that_explains_it(anonymous_client, caplog):
    """From 400 up the body is the point of the line: it carries the refusal in French."""
    anonymous_client.post("/game/new", json={"side": "alliance"})

    line = one_line(caplog, "Answer — method='POST', path='/game/new'")
    assert "status=401" in line
    assert "connect" in line.lower()


def test_an_address_that_matches_no_route_is_traced_like_any_other(client, caplog):
    client.get("/nowhere")

    assert "endpoint=None" in one_line(caplog, "Request — method='GET', path='/nowhere'")
    answer = one_line(caplog, "Answer — method='GET', path='/nowhere'")
    assert "status=404" in answer
    # The router's 404 arrives as an iterable: a refusal is read all the same.
    assert "The requested URL was not found on the server" in answer


def test_how_long_the_request_took_is_written(client, caplog):
    client.get("/game/state")
    assert " ms" in one_line(caplog, "Answer — method='GET', path='/game/state'")


def test_an_image_is_named_rather_than_copied_into_the_log(client, caplog):
    """`send_file` hands the file over untouched: reading it to log it would load it in memory."""
    client.get("/map.jpg")

    line = one_line(caplog, "Answer — method='GET', path='/map.jpg'")
    assert "streamed, left untouched" in line


def test_a_page_is_described_and_not_copied(client, caplog):
    client.get("/")

    line = one_line(caplog, "Answer — method='GET', path='/'")
    assert "bytes of text/html" in line


def test_the_stream_is_left_untouched_and_goes_on_streaming(client, caplog):
    """Reading the stream to log it would consume the message the browser is waiting for."""
    answer = client.get("/stream", buffered=False)
    try:
        first = next(iter(answer.response)).decode("utf-8")
    finally:
        answer.close()

    assert first.startswith("id: ") or first.startswith(": ")
    assert "streamed, left untouched" in one_line(caplog, "Answer — method='GET', path='/stream'")


def test_the_two_ends_of_a_stream_are_written_and_not_its_heartbeats(client, caplog):
    """Who is following, and since when: the first question a board that does not refresh asks."""
    answer = client.get("/stream", buffered=False)
    try:
        next(iter(answer.response))
    finally:
        answer.close()

    assert "followers=1" in one_line(caplog, "Stream: a browser is following the game")
    assert one_line(caplog, "Stream: a browser has stopped following")
    assert not [line for line in general_lines(caplog) if "heartbeat" in line]


# --- The connection, step by step --------------------------------------------------------------


def test_every_step_of_the_connection_is_written(anonymous_client, caplog):
    anonymous_client.get("/login", follow_redirects=True)

    written = general_lines(caplog)
    for step in ("Login: departure asked for",
                 "Login: anti-CSRF state drawn and put in the session",
                 "Login: leaving for Discord",
                 "Login: back from Discord",
                 "Login: the anti-CSRF state compared",
                 "Login: exchanging the authorization code for a token",
                 "Login: account read from Discord",
                 "Login: session opened"):
        assert any(line.startswith(step) for line in written), f"{step!r} was not written"


def test_the_session_opened_names_who_opened_it(anonymous_client, caplog):
    anonymous_client.get("/login", follow_redirects=True)

    line = one_line(caplog, "Login: session opened")
    assert f"nickname={DEFAULT_IDENTITY['nickname']!r}" in line
    assert f"discord_id={DEFAULT_IDENTITY['discord_id']!r}" in line
    assert '"joueur"' in line and line.endswith("destination='/'")


def test_neither_the_state_nor_the_code_nor_the_token_is_ever_written(anonymous_client, caplog):
    """The three credentials of the flow, each in the log by its length and by nothing else."""
    anonymous_client.get("/login")
    with anonymous_client.session_transaction() as session:
        state = session["etat_oauth"]
    anonymous_client.get(f"/login/return?code=fake-code&state={state}")

    written = "\n".join(general_lines(caplog))
    assert state not in written
    assert "fake-code" not in written
    assert "token-for-fake-code" not in written
    assert "state=<hidden, 43 characters>" in written
    assert "code=<hidden, 9 characters>" in written


def test_a_refused_return_says_why_in_the_log(anonymous_client, caplog):
    anonymous_client.get("/login/return?code=fake-code&state=forged")

    line = one_line(caplog, "Login refused")
    assert "authentication state absent from the session" in line


def test_the_player_refusing_on_discord_s_page_is_written(anonymous_client, caplog):
    anonymous_client.get("/login/return?error=access_denied")

    assert "error='access_denied'" in one_line(
        caplog, "Login: the player refused on Discord's page")


def test_logging_out_is_written_with_who_was_there(client, caplog):
    client.post("/logout")

    assert f"nickname={DEFAULT_IDENTITY['nickname']!r}" in one_line(caplog, "Logout asked for")
    assert "session_keys=[]" in one_line(caplog, "Logout: session closed")


# --- The game's own life -----------------------------------------------------------------------


def test_opening_a_game_is_written_with_what_it_opened(client, caplog):
    answer = client.post("/game/new", json={"side": "alliance", "against_ai": False})

    line = one_line(caplog, "New game opened")
    assert f"game='{answer.get_json()['id']}'" in line
    assert f"scenario={current_game.SCENARIO_NUMBER}" in line
    assert f"units={len(current_game.BOARD)}" in line


def test_saving_and_publishing_a_move_are_both_written(client, caplog, seat_the_player):
    client.post("/game/new", json={"side": "alliance", "against_ai": False})
    seat_the_player(client.application, client)
    caplog.clear()
    client.post("/phase/next")

    assert lines_starting(caplog, "Move marked and pushed to those watching")
    saved = one_line(caplog, "Game saved")
    assert f"game='{current_game.GAME_ID}'" in saved
    assert f"turn={current_game.TURN.number}" in saved
    assert f"phase='{current_game.TURN.phase_type}'" in saved


# --- What must stay out of it ------------------------------------------------------------------


def test_none_of_this_reaches_the_column_the_player_reads(client, caplog):
    """The general log's handlers are its own: the browser's column is the game log's queue."""
    before = len(log_lines())
    client.get("/game/state")

    assert general_lines(caplog), "the request was not traced at all"
    assert len(log_lines()) == before
    assert not any("Request —" in line["text"] for line in log_lines())


def test_the_general_log_writes_into_a_file_of_its_own():
    assert general_log.GENERAL_LOG_PATH.name == "general.log"
    assert [type(handler).__name__ for handler in GENERAL_LOG.handlers] == \
        ["RotatingFileHandler"]


def test_a_step_written_by_hand_carries_its_variables(caplog):
    note("Anything at all", side="tenebres", units=3)
    assert general_lines(caplog)[-1] == "Anything at all — side='tenebres', units=3"


def test_the_hidden_form_says_a_length_and_nothing_else():
    assert hidden("abc") == "<hidden, 3 characters>"
    assert hidden(None) == "<absent>"
