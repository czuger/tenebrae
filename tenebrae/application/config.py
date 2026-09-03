"""The application's configuration, in a single place.

MongoDB connection details and Discord secrets never live in the code: they are read from `.env`
(at the root of the repository, not versioned - see `.env.example`), loaded here once, when the
module is imported. `create_app` receives one of these classes and hands it to Flask; nothing else
reads the environment.

The game is saved in MongoDB, always: `MONGODB_URI` says where. The test configuration writes into
a base of its own, the one `make test` brings up, named by `MONGODB_URI_TEST`.

`AUTHENTICATION` says where a player's identity comes from: from Discord, or from a fake client
that answers by itself. **It is not read from the environment, and that is deliberate**: a `.env`
variable that unplugs authentication is an open door that a typo is enough to leave gaping. Only
`TestingConfig` sets "fake".
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# The root of the repository, where `.env` and `logs/` live, outside the package.
ROOT = Path(__file__).resolve().parents[2]

# Variables already set in the environment keep the upper hand, as python-dotenv intends.
load_dotenv(ROOT / ".env")


def _list(name: str) -> list[str]:
    """Reads an environment variable as a comma-separated list.

    Args:
        name: The variable's name.

    Returns:
        The stripped, non-empty elements: "12,34" -> ["12", "34"], absence -> [].
    """
    return [element.strip() for element in os.environ.get(name, "").split(",") if element.strip()]


class Config:
    """The ordinary game configuration: the game is saved in MongoDB."""

    # The format the MongoEngine extension expects: everything fits in the URI.
    MONGODB_SETTINGS = {"host": os.environ.get("MONGODB_URI",
                                               "mongodb://localhost:27017/tenebrae")}

    # --- The session ---
    #
    # Absent, `create_app` refuses to start rather than draw a key at random: a key that changes at
    # every launch would disconnect everyone at every restart.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    SESSION_COOKIE_HTTPONLY = True
    # "Lax", not "Strict": the return from Discord is a top-level navigation from another site, and
    # "Strict" would withhold the cookie carrying the OAuth state.
    SESSION_COOKIE_SAMESITE = "Lax"
    # Development speaks http://127.0.0.1, where a "Secure" cookie would not be set at all.
    SESSION_COOKIE_SECURE = os.environ.get("SECURE_COOKIE", "no") == "yes"
    # Only responses that modified the session rewrite the cookie. Rewriting it on every response
    # let a request in flight during `/login` (a fallback poll, a stream reconnection) overwrite the
    # cookie carrying the OAuth state. The cookie's 31-day expiry then runs from the login rather
    # than from the last visit.
    SESSION_REFRESH_EACH_REQUEST = False

    # --- Player identity ---
    AUTHENTICATION = "discord"
    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
    # Compared by Discord with the Developer Portal character by character ("localhost" is not
    # "127.0.0.1"). From the configuration, never from `request.host`, which a forged header
    # would displace.
    DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI",
                                          "http://127.0.0.1:5000/login/return")

    # Who may fix the map (`/admin/map_fix`), by Discord identifier. An empty list admits nobody.
    ADMINISTRATORS = _list("ADMIN_DISCORD_IDS")


class TestingConfig(Config):
    """The test configuration: the test MongoDB, no Discord, a fixed secret key."""

    TESTING = True

    # The base `make test` brings up (see the Makefile): another port than the game's, and a
    # database of its own, emptied before every test.
    MONGODB_SETTINGS = {"host": os.environ.get("MONGODB_URI_TEST",
                                               "mongodb://localhost:27018/tenebrae_test")}

    # The fake client closes the OAuth flow on our own return route (see `discord_client.py`):
    # nothing leaves the machine, and the whole flow is exercised.
    AUTHENTICATION = "fake"

    # Fixed, and never used anywhere else: the suite does not depend on a local `.env`.
    SECRET_KEY = "worthless-test-key"

    # The test player, the one `tests/application/conftest.py` puts into the session.
    ADMINISTRATORS = ["100000000000000001"]
