"""Logging in through Discord: the departure, the return, and closing the session.

The OAuth2 flow is in `discord_client.py`; these routes only drive it, with a single-use state
against CSRF kept in the session (`models/connection.py`). What goes wrong on the return - a
session cookie that did not come back, a state Discord did not return - is diagnosed in plain
words for the log, never with the states themselves.
"""

import secrets
from typing import Optional
from urllib.parse import urlparse

from flask import Blueprint, abort, current_app, redirect, request, session, url_for
from flask.sessions import SecureCookieSessionInterface
from flask.typing import ResponseReturnValue
from itsdangerous import BadSignature

from tenebrae.application.logs.battle_log import LOG
from tenebrae.application.players import discord_client, the_connection

blueprint = Blueprint("authentication", __name__)


def oauth_state_diagnosis(expected: Optional[str], received: Optional[str]) -> str:
    """Explains why the anti-CSRF state does not pass, in plain words for the log.

    Three cases, not cured the same way: a state absent from the **session** means the cookie set
    at departure did not come back (a different host between the outward and return trips, a
    "Secure" cookie over http, a session emptied meanwhile); a state absent from the **request**,
    that Discord did not return it; two different states, a replayed or forged return. The states
    themselves are never written.

    Args:
        expected: The state taken from the session.
        received: The state Discord sent back.

    Returns:
        The cause, the host requested and the session cookie's state.
    """
    if not expected:
        cause = "authentication state absent from the session"
    elif not received:
        cause = "authentication state absent from the request"
    else:
        cause = "authentication state different from the session's"
    return f"{cause} (host {request.host}, {session_cookie_state()})"


def warn_if_the_return_lands_on_another_host() -> None:
    """Logs **at departure** that the session cookie will not come back.

    The map opened on `localhost` while `DISCORD_REDIRECT_URI` names `127.0.0.1`: two sites for
    the browser, so the cookie set here is not sent there. Both hosts are known here, so the trap
    is stated before it closes, with the address to open the map on.
    """
    expected = urlparse(current_app.config["DISCORD_REDIRECT_URI"])
    if expected.netloc and request.host != expected.netloc:
        LOG.info("Login: departure from %s, but Discord will send back to %s — the session "
                 "cookie set here will not come back; open the map on %s",
                 request.host, expected.netloc, f"{expected.scheme}://{expected.netloc}/")


def session_cookie_state() -> str:
    """Describes the session cookie as it arrived: absent, unreadable, or readable and carrying
    what.

    Unreadable means signed by another `SECRET_KEY`. Readable but without the state means another
    request rewrote the cookie between the outward and return trips; the keys it carries say where
    that session came from. The keys alone: never the values.

    Returns:
        One line for the log.
    """
    cookie = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"])
    if cookie is None:
        return "session cookie absent"
    interface = current_app.session_interface
    serializer = (interface.get_signing_serializer(current_app)
                  if isinstance(interface, SecureCookieSessionInterface) else None)
    if serializer is None:
        return "session cookie present, but the application cannot verify its signature"
    try:
        serializer.loads(cookie)
    except BadSignature:
        return "session cookie present but unreadable — signed by another SECRET_KEY?"
    contents = ", ".join(sorted(session.keys()))
    return f"session cookie readable, session {'carrying ' + contents if contents else 'empty'}"


@blueprint.route("/login")
def login() -> ResponseReturnValue:
    """Leaves for Discord, with a single-use state against CSRF.

    Returns:
        A redirect to the authorization URL.
    """
    warn_if_the_return_lands_on_another_host()
    state = the_connection().set_oauth_state()
    return redirect(discord_client().authorization_url(state))


@blueprint.route("/login/return")
def login_return() -> ResponseReturnValue:
    """Handles the return from Discord: checks the state, exchanges the code, opens the session.

    The state is **removed** from the session first (`Connection.take_oauth_state`): a replayed
    return finds nothing to compare against. The comparison goes through `compare_digest`.

    Returns:
        A redirect to the map; 400 if the state or the code is missing or wrong.

    Raises:
        DiscordError: As it comes, with Discord's answer in its message, rather than a mute 502.
    """
    if request.args.get("error"):  # the player refused on Discord's page
        return redirect(url_for("game.board"))

    connection = the_connection()
    expected = connection.take_oauth_state()
    received = request.args.get("state")
    if not expected or not received or not secrets.compare_digest(expected, received):
        LOG.info("Login refused: %s", oauth_state_diagnosis(expected, received))
        abort(400, "état d'authentification absent ou inattendu")
    code = request.args.get("code")
    if not code:
        LOG.info("Login refused: authorization code absent from the request")
        abort(400, "code d'autorisation absent")

    token = discord_client().exchange_code(code)
    identity = discord_client().identity(token)

    player = connection.open(identity)
    LOG.info("Login: %s", player["nickname"])
    return redirect(url_for("game.board"))


@blueprint.route("/logout", methods=["POST"])
def logout() -> ResponseReturnValue:
    """Closes the session; the seat held is not given up.

    A POST, like everything that changes something: a link from another site must not log the
    player out.

    Returns:
        `{"connected": False}`.
    """
    the_connection().close()
    return {"connected": False}
