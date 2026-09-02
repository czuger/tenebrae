"""The application's configuration, in a single place.

MongoDB connection details and Discord secrets never live in the code: they are read from `.env`
(at the root of the repository, not versioned - see `.env.example`), loaded here once, when the
module is imported. `create_app` receives one of these classes and hands it to Flask; nothing else
reads the environment.

`PERSISTENCE` says what becomes of the game: `mongo` saves it after every move and resumes it on
load, `none` plays as before - everything in memory, nothing outlives the server. It is also what
makes it possible to play without MongoDB installed.

`AUTHENTICATION` says where a player's identity comes from: from Discord, or from a fake client
that answers by itself. **It is not read from the environment, and that is deliberate**: a `.env`
variable that unplugs authentication is an open door that a typo is enough to leave gaping. Only
`TestingConfig` sets "fake", and the engine are the only place it can be used from.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# The root of the repository: `tenebrae/application/config.py` -> three levels up.
# `.env` and `logs/` live there, outside the package.
ROOT = Path(__file__).resolve().parents[2]

# A single read of `.env`, at first import; variables already set in the environment keep the
# upper hand, as python-dotenv intends.
load_dotenv(ROOT / ".env")


def _list(name):
    """An environment variable as a list: "12,34" -> ["12", "34"], absence -> []."""
    return [element.strip() for element in os.environ.get(name, "").split(",") if element.strip()]


class Config:
    """The ordinary game configuration: the game is saved in MongoDB."""

    PERSISTENCE = os.environ.get("PERSISTENCE", "mongo")
    # The format the MongoEngine extension expects: everything fits in the URI.
    MONGODB_SETTINGS = {"host": os.environ.get("MONGODB_URI",
                                               "mongodb://localhost:27017/tenebrae")}

    # --- The session ---
    #
    # What signs the session cookie. Absent, `create_app` refuses to start rather than draw one at
    # random: a key that changes at every launch would disconnect everyone at every restart, and
    # nobody would see why.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # JavaScript has nothing to read in the cookie: everything it knows about the player comes
    # from the template.
    SESSION_COOKIE_HTTPONLY = True
    # "Lax" and not "Strict": the return from Discord is a top-level navigation coming from
    # another site. "Strict" would withhold the cookie, the session would look empty, the OAuth
    # state would be nowhere to be found - and the flow could never complete.
    SESSION_COOKIE_SAMESITE = "Lax"
    # In development we speak http://127.0.0.1, where a "Secure" cookie would not be set at all:
    # the variable defaults to "no", and goes to "yes" behind HTTPS.
    SESSION_COOKIE_SECURE = os.environ.get("SECURE_COOKIE", "no") == "yes"
    # The cookie is only rewritten by responses that have **modified** the session: opening or
    # closing a connection, setting or taking back the OAuth2 state. By default Flask rewrites it
    # on every response as soon as the session is permanent - hence as soon as it carries a player
    # - and that is what used to break logging in: a request that left with the old session before
    # `/login` - a fallback poll, a stream reconnection from another tab - answers afterwards, and
    # its cookie, lacking the state, overwrites the one `/login` had just set. The return from
    # Discord then found nothing left to compare against. What is lost: the cookie's expiry
    # (`PERMANENT_SESSION_LIFETIME`, 31 days) runs from the login and not from the last visit -
    # one reconnects once a month, that is all.
    SESSION_REFRESH_EACH_REQUEST = False

    # --- Player identity ---
    AUTHENTICATION = "discord"
    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
    # Discord compares this URI with the one in the Developer Portal **character by character**:
    # "localhost" is not "127.0.0.1" there, and one extra "/" is enough to make the exchange fail.
    # It comes from the configuration and never from `request.host`, which a forged header would
    # displace.
    DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI",
                                          "http://127.0.0.1:5000/login/return")

    # Who may fix the map (`/admin/map_fix`), by Discord identifier. An empty list admits nobody:
    # a security variable whose absence would open everything would be a trap. The refusal says
    # how to declare oneself.
    ADMINISTRATORS = _list("ADMIN_DISCORD_IDS")


class TestingConfig(Config):
    """The test configuration: no MongoDB - the null repository saves nothing, and the routes keep
    their behaviour from before persistence."""

    TESTING = True
    PERSISTENCE = "none"

    # Discord without Discord: the fake client closes the flow on our own return route (see
    # `tenebrae/application/discord_client.py`). Nothing leaves the machine, and the whole flow is
    # exercised.
    AUTHENTICATION = "fake"

    # Fixed, and never used anywhere else: the suite does not depend on a local `.env`.
    SECRET_KEY = "worthless-test-key"

    # The test player fixes the map just as they play: it is `tenebrae/engine/conftest.py` that puts
    # this identifier into the session.
    ADMINISTRATORS = ["100000000000000001"]
