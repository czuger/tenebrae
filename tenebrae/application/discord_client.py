"""Where a player's identity comes from: from Discord, or from a fake client for the engine.

The OAuth2 protocol fits in two round trips: a form POST to `/oauth2/token`, which exchanges the
single-use code for an access token, then a GET bearing that token to `/users/@me`. `urllib.request`
does both perfectly well. **We therefore add nothing to `pyproject.toml`**: this is the same
stance as `tenebrae/application/extensions.py`, which rewrote Flask-MongoEngine's interface rather
than install a dead extension. `requests` is indeed lying around in the virtualenv, but pulled in by
Playwright - and the server cannot depend at runtime on a testing tool.

The file is not called `discord.py`: it is `tenebrae.application.discord_client`, and a module
named `discord` inside the package would read, at every call site, like the Discord library it is
not.

Two implementations, chosen by `AUTHENTICATION` and hooked onto `application.extensions` as the
repository already is: the real one, and a fake one that closes the flow on our own return route.
The fake one short-circuits nothing - the `state`, the code exchange and the identity read all
really happen -, it merely avoids leaving the machine.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import url_for

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
ME_URL = "https://discord.com/api/users/@me"
CDN = "https://cdn.discordapp.com"

# Without it, `urlopen` would wait indefinitely: an unreachable Discord would freeze the request.
TIMEOUT = 10

# Cloudflare, in front of the Discord API, turns away with a 403 the `Python-urllib/3.x` that
# `urllib` would send by default: one has to introduce oneself, any honest name will do.
USER_AGENT = "AveTenebrae/1.0"

# Everything the game needs: an identifier, a nickname, an avatar. Not "email" - the game would do
# nothing with it, and one scope fewer is one consent fewer to ask for and one personal detail
# fewer to keep. The model's `email` field waits, just in case.
SCOPE = "identify"


class DiscordError(Exception):
    """Discord did not answer, or answered something other than what was expected."""


class DiscordClient:
    """The three exchanges of the OAuth2 flow: the authorization URL, the token, the account.

    The application secret never leaves this file: it goes out in the body of a POST to Discord,
    and nothing else in the project reads it.
    """

    def __init__(self, identifier, secret, redirect_uri):
        self._identifier = identifier
        self._secret = secret
        self._redirect_uri = redirect_uri

    def authorization_url(self, state):
        """Where to send the browser so that it asks for the player's authorization."""
        parameters = {"client_id": self._identifier, "redirect_uri": self._redirect_uri,
                      "response_type": "code", "scope": SCOPE, "state": state}
        return f"{AUTHORIZE_URL}?{urlencode(parameters)}"

    def exchange_code(self, code):
        """The single-use code brought back by the browser, against an access token."""
        body = urlencode({"client_id": self._identifier, "client_secret": self._secret,
                          "grant_type": "authorization_code", "code": code,
                          "redirect_uri": self._redirect_uri}).encode()
        answer = self._call(TOKEN_URL, body=body)
        try:
            return answer["access_token"]
        except (KeyError, TypeError) as trouble:
            raise DiscordError("Discord returned no access token") from trouble

    def identity(self, token):
        """"/users/@me", brought back to the game's vocabulary."""
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
    def avatar_url(me):
        """The account's avatar, or the one Discord assigns by default to accounts without one."""
        if me.get("avatar"):
            return f"{CDN}/avatars/{me['id']}/{me['avatar']}.png?size=64"
        return f"{CDN}/embed/avatars/{(int(me['id']) >> 22) % 6}.png"

    @staticmethod
    def _call(url, body=None, headers=None):
        request = Request(url, data=body,
                          headers={"Accept": "application/json", "User-Agent": USER_AGENT,
                                   **(headers or {})})
        try:
            with urlopen(request, timeout=TIMEOUT) as answer:
                return json.load(answer)
        except HTTPError as trouble:
            # The detail is in the body - `{"error": "invalid_grant", "error_description": ...}` -
            # which `str(trouble)` does not show: we read it before losing it.
            body = trouble.read().decode("utf-8", "replace")
            raise DiscordError(
                f"Discord answered {trouble.code} {trouble.reason} to {url}: {body}") from trouble
        except (URLError, ValueError, TimeoutError) as trouble:
            raise DiscordError(f"Discord did not answer {url}: {trouble!r}") from trouble


# The account the fake client serves, failing another. The identifier is the one `TestingConfig`
# declares as administrator and that `tenebrae/engine/conftest.py` seats at the table.
DEFAULT_IDENTITY = {"discord_id": "100000000000000001", "nickname": "Joueuse d'essai",
                    "display_name": None, "avatar": None, "email": None}


class FakeDiscordClient:
    """Discord without Discord: the same protocol, without leaving the process.

    Everything is in `authorization_url`, which redirects not to discord.com but to **our own
    return route**. The browser - Playwright's as well as that of a developer with no declared
    application - follows the redirect, comes back with a code and a state, and the return route
    then runs the real code: state check, code exchange, identity read, session opening. The flow
    is exercised, not bypassed.

    `served_identity` can be replaced during a test to bring in a second player - that is how two
    browsers each sit down at their own side.
    """

    def __init__(self, identity=None):
        self.served_identity = dict(identity or DEFAULT_IDENTITY)
        self.exchanged_codes = []

    def authorization_url(self, state):
        return url_for("game.login_return", code="fake-code", state=state)

    def exchange_code(self, code):
        self.exchanged_codes.append(code)
        return f"token-for-{code}"

    def identity(self, token):
        return dict(self.served_identity)
