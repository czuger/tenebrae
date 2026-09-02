"""What `DiscordClient` makes of Discord's answers - without leaving the machine.

`urlopen` is replaced in the module: the flow's three HTTP calls go nowhere, and we look at what
the client returns, or what it raises, depending on what we make it receive.
"""

import io
import json
from urllib.error import HTTPError, URLError

import pytest

from tenebrae.application import discord_client
from tenebrae.application.discord_client import DiscordClient, DiscordError


@pytest.fixture
def client():
    return DiscordClient("identifier", "secret", "http://127.0.0.1:5000/login/return")


def answer_with(monkeypatch, body):
    """Makes `urlopen` return `body` (a dict), as a 200 answer."""
    class Answer(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *_):
            self.close()

    monkeypatch.setattr(discord_client, "urlopen",
                        lambda request, timeout: Answer(json.dumps(body).encode()))


def fail_with(monkeypatch, trouble):
    def raiser(request, timeout):
        raise trouble
    monkeypatch.setattr(discord_client, "urlopen", raiser)


def test_the_token_is_read_from_the_answer(client, monkeypatch):
    answer_with(monkeypatch, {"access_token": "token", "token_type": "Bearer"})
    assert client.exchange_code("code") == "token"


def test_an_http_error_carries_discords_status_and_body(client, monkeypatch):
    """It is in the body that Discord says *why* - `invalid_grant`, `invalid_client` - and
    `str(HTTPError)` does not show it: the error message must repeat it."""
    body = json.dumps({"error": "invalid_grant",
                       "error_description": "Invalid \"code\" in request."}).encode()
    fail_with(monkeypatch, HTTPError(discord_client.TOKEN_URL, 400, "Bad Request", {},
                                     io.BytesIO(body)))
    with pytest.raises(DiscordError) as raised:
        client.exchange_code("code")
    message = str(raised.value)
    assert "400 Bad Request" in message
    assert discord_client.TOKEN_URL in message
    assert "invalid_grant" in message
    assert 'Invalid \\"code\\" in request.' in message
    assert isinstance(raised.value.__cause__, HTTPError)


def test_an_unreachable_discord_says_which_and_why(client, monkeypatch):
    fail_with(monkeypatch, URLError("Connection refused"))
    with pytest.raises(DiscordError, match="Connection refused") as raised:
        client.identity("token")
    assert discord_client.ME_URL in str(raised.value)


def test_an_answer_without_a_token_is_an_error(client, monkeypatch):
    answer_with(monkeypatch, {"token_type": "Bearer"})
    with pytest.raises(DiscordError, match="token"):
        client.exchange_code("code")
