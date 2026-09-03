"""Where a player's identity comes from: from Discord, or from a fake client for the tests.

The OAuth2 protocol fits in two round trips: a form POST to `/oauth2/token`, which exchanges the
single-use code for an access token, then a GET bearing that token to `/users/@me`. `urllib.request`
does both, so nothing is added to `pyproject.toml`: the same stance as
`tenebrae/application/extensions.py`.

The file is not called `discord.py`: a module named `discord` inside the package would read, at
every call site, like the Discord library it is not.

Two implementations, chosen by `AUTHENTICATION` and hooked onto `application.extensions` as the
repositories are: the real one, and a fake one that closes the flow on our own return route. The
fake one short-circuits nothing - the `state`, the code exchange and the identity read all really
happen -, it merely avoids leaving the machine.
"""

import json
from collections.abc import Mapping
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import url_for

from tenebrae.engine.repositories.player import PlayerRecord

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
ME_URL = "https://discord.com/api/users/@me"
CDN = "https://cdn.discordapp.com"

# Without it, `urlopen` would wait indefinitely on an unreachable Discord.
TIMEOUT = 10

# Cloudflare, in front of the Discord API, turns away urllib's default `Python-urllib/3.x`.
USER_AGENT = "AveTenebrae/1.0"

# An identifier, a nickname, an avatar. Not "email": one scope fewer is one consent fewer to ask
# for and one personal detail fewer to keep.
SCOPE = "identify"


class DiscordError(Exception):
    """Discord did not answer, or answered something other than what was expected."""


class DiscordClient:
    """The three exchanges of the OAuth2 flow: the authorization URL, the token, the account.

    The application secret never leaves this file: it goes out in the body of a POST to Discord,
    and nothing else in the project reads it.
    """

    def __init__(self, identifier: str, secret: str, redirect_uri: str) -> None:
        """Keeps the application's credentials.

        Args:
            identifier: The Discord application's client id.
            secret: Its client secret.
            redirect_uri: Our return route, as declared in the Developer Portal.
        """
        self._identifier = identifier
        self._secret = secret
        self._redirect_uri = redirect_uri

    def authorization_url(self, state: str) -> str:
        """Builds the URL the browser is sent to for the player's authorization.

        Args:
            state: The single-use anti-CSRF state, sent back with the code.

        Returns:
            The Discord authorization URL, parameters included.
        """
        parameters = {"client_id": self._identifier, "redirect_uri": self._redirect_uri,
                      "response_type": "code", "scope": SCOPE, "state": state}
        return f"{AUTHORIZE_URL}?{urlencode(parameters)}"

    def exchange_code(self, code: str) -> str:
        """Exchanges the single-use code brought back by the browser for an access token.

        Args:
            code: The authorization code.

        Returns:
            The access token.

        Raises:
            DiscordError: If Discord does not answer, or returns no token.
        """
        body = urlencode({"client_id": self._identifier, "client_secret": self._secret,
                          "grant_type": "authorization_code", "code": code,
                          "redirect_uri": self._redirect_uri}).encode()
        answer = self._call(TOKEN_URL, body=body)
        try:
            return answer["access_token"]
        except (KeyError, TypeError) as trouble:
            raise DiscordError("Discord returned no access token") from trouble

    def identity(self, token: str) -> PlayerRecord:
        """Reads `/users/@me` and brings it back to the game's vocabulary.

        Args:
            token: The access token.

        Returns:
            `discord_id`, `nickname`, `display_name`, `avatar`, `email`.

        Raises:
            DiscordError: If Discord does not answer, or returns no readable account.
        """
        me = self._call(ME_URL, headers={"Authorization": f"Bearer {token}"})
        try:
            return {"discord_id": str(me["id"]),
                    "nickname": me.get("global_name") or me["username"],
                    "display_name": me.get("global_name"),
                    "avatar": self.avatar_url(me),
                    "email": me.get("email")}
        except (KeyError, TypeError) as trouble:
            raise DiscordError("Discord returned no readable account") from trouble

    @staticmethod
    def avatar_url(me: Mapping[str, Any]) -> str:  # Any: Discord's JSON, read as it comes
        """Builds the URL of the account's avatar.

        Args:
            me: Discord's `/users/@me` answer.

        Returns:
            The avatar's CDN URL, or the one Discord assigns by default to accounts without one.
        """
        if me.get("avatar"):
            return f"{CDN}/avatars/{me['id']}/{me['avatar']}.png?size=64"
        return f"{CDN}/embed/avatars/{(int(me['id']) >> 22) % 6}.png"

    @staticmethod
    def _call(url: str, body: Optional[bytes] = None,
              headers: Optional[Mapping[str, str]] = None) -> dict[str, Any]:
        """Calls Discord and decodes its JSON answer.

        Args:
            url: The endpoint.
            body: The form body of a POST; `None` for a GET.
            headers: Extra headers, e.g. the bearer token.

        Returns:
            The decoded answer. Any: Discord's JSON, read as it comes.

        Raises:
            DiscordError: On any HTTP error, network error or unreadable answer, with the status
                and body of Discord's answer in the message.
        """
        request = Request(url, data=body,
                          headers={"Accept": "application/json", "User-Agent": USER_AGENT,
                                   **(headers or {})})
        try:
            with urlopen(request, timeout=TIMEOUT) as answer:
                return json.load(answer)
        except HTTPError as trouble:
            # The detail (`invalid_grant`, ...) is in the body, which `str(trouble)` does not show.
            body = trouble.read().decode("utf-8", "replace")
            raise DiscordError(
                f"Discord answered {trouble.code} {trouble.reason} to {url}: {body}") from trouble
        except (URLError, ValueError, TimeoutError) as trouble:
            raise DiscordError(f"Discord did not answer {url}: {trouble!r}") from trouble


# The account the fake client serves, failing another: the identifier `TestingConfig` declares as
# administrator and that the test fixtures seat at the table.
DEFAULT_IDENTITY: PlayerRecord = {"discord_id": "100000000000000001",
                                  "nickname": "Joueuse d'essai",
                                  "display_name": None, "avatar": None, "email": None}


class FakeDiscordClient:
    """Discord without Discord: the same protocol, without leaving the process.

    `authorization_url` redirects not to discord.com but to **our own return route**. The browser
    follows the redirect, comes back with a code and a state, and the return route then runs the
    real code: state check, code exchange, identity read, session opening. `served_identity` can be
    replaced during a test to bring in a second player.
    """

    served_identity: PlayerRecord
    exchanged_codes: list[str]

    def __init__(self, identity: Optional[Mapping[str, Optional[str]]] = None) -> None:
        """Chooses the account the client will report.

        Args:
            identity: The account served; `DEFAULT_IDENTITY` when omitted.
        """
        self.served_identity = dict(identity or DEFAULT_IDENTITY)
        self.exchanged_codes = []

    def authorization_url(self, state: str) -> str:
        """Points straight at our return route, code and state included.

        Args:
            state: The single-use anti-CSRF state.

        Returns:
            The URL of `/login/return`.
        """
        return url_for("game.login_return", code="fake-code", state=state)

    def exchange_code(self, code: str) -> str:
        """Records the code and hands back a token derived from it.

        Args:
            code: The authorization code.

        Returns:
            `"token-for-<code>"`.
        """
        self.exchanged_codes.append(code)
        return f"token-for-{code}"

    def identity(self, token: str) -> PlayerRecord:
        """Reports the served account.

        Args:
            token: Ignored.

        Returns:
            A copy of `served_identity`.
        """
        return dict(self.served_identity)
