"""The general log: everything the server does that is neither a combat nor a movement.

Three logs, three files, and each one answers a different question.

- `battle_log.log` is **the game told to the player**: phases, combats, retreats, the end. It shows
  in the browser's column, and its sentences are read by whoever is playing.
- `movement.log` is the engine's walk, recomputed at every click and drowning anything put beside
  it (`movement_log.py`).
- `general.log`, here, is **the server's own trace**: the requests that come in and the answers
  that go out in full (`request_trace.py`), the whole of the Discord flow, the games opened, saved
  and left. It is what is read when something has gone wrong and the game itself has nothing to say
  about it - a login that comes back anonymous, an answer the page did not expect.

**DEBUG, and on.** The level is DEBUG unless `LOG_LEVEL` says otherwise in the environment: a trace
one must first go and turn on is a trace one does not have on the day it is needed. Nothing of this
reaches the browser's column - a different logger, different handlers, a different file.

Two ways in, and one rule for both: **name every variable and write out its content.**

    note("Opening the session", identifier=identity["discord_id"])   # a step, DEBUG
    event("Session opened", nickname=player["nickname"])             # something happened, INFO

The rule that is not negotiable: **a secret is never written out.** A name that says token, secret,
password, authorization, cookie, state or code - at the top level or deep inside a body being
logged - is replaced by its length. That discipline is the one `routes/authentication.py` already
followed for the OAuth state: the keys a session carries, never their values.
"""

import json
import logging
import os
from collections.abc import Mapping
from typing import Optional
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from tenebrae.application.config import ROOT
from tenebrae.application.logs.rotating_log import open_the_log

GENERAL_LOG_PATH = ROOT / "logs" / "general.log"

# The level, unless `LOG_LEVEL` says otherwise. Anything unreadable there falls back here rather
# than stopping the application: a mistyped level must not cost a start-up.
DEFAULT_LEVEL = logging.DEBUG

# Ten times the game log's file: this one carries whole payloads, and 50 KB of it would be a few
# minutes of play. 512 KB and five archives, so that yesterday's login is still there today.
MAX_BYTES = 512 * 1024
FILES_KEPT = 5

# Beyond that many characters a value is cut - and says it was, with its full length. A board
# snapshot is some twenty kilobytes, and a trace that wrote every one of them whole would hold one
# afternoon's play and nothing else - not the login of the morning one came to read.
# `LOG_VALUE_LIMIT` raises it, and 0 there writes every answer whole, however long.
DEFAULT_VALUE_LIMIT = 2000

# A field whose name carries one of these is never written out. Broad on purpose: a new secret
# passing through a name nobody thought of is hidden by default rather than published by default.
SECRET_NAMES = ("secret", "token", "password", "authorization", "cookie", "state", "code")

GENERAL_LOG = logging.getLogger("tenebrae.general")


def the_level() -> int:
    """Reads the level from `LOG_LEVEL`, DEBUG failing that.

    Returns:
        A `logging` level; DEBUG for an absent or unreadable one.
    """
    asked = os.environ.get("LOG_LEVEL", "").strip().upper()
    return logging.getLevelNamesMapping().get(asked, DEFAULT_LEVEL)


if not GENERAL_LOG.handlers:
    GENERAL_LOG.addHandler(open_the_log(GENERAL_LOG_PATH, MAX_BYTES, FILES_KEPT))
    GENERAL_LOG.setLevel(the_level())


def the_limit() -> int:
    """Reads the cut from `LOG_VALUE_LIMIT`, `DEFAULT_VALUE_LIMIT` failing that.

    Returns:
        The number of characters a value is written out to; 0 for no cut at all.
    """
    asked = os.environ.get("LOG_VALUE_LIMIT", "").strip()
    return int(asked) if asked.isdigit() else DEFAULT_VALUE_LIMIT


VALUE_LIMIT = the_limit()


def note(message: str, **variables: object) -> None:
    """Writes one step of what the server is doing, at DEBUG.

    Args:
        message: What is happening, in English and in plain words.
        **variables: Everything worth reading afterwards, each named; contents are written out,
            secrets excepted.
    """
    GENERAL_LOG.debug("%s", spell_out(message, variables))


def event(message: str, **variables: object) -> None:
    """Writes something that happened rather than a step towards it, at INFO.

    A login, a game opened, a session closed: what is still worth having when the level has been
    raised to leave the steps out.

    Args:
        message: What happened.
        **variables: Its variables, named; contents are written out, secrets excepted.
    """
    GENERAL_LOG.info("%s", spell_out(message, variables))


def failure(message: str, trouble: Optional[BaseException] = None,
            **variables: object) -> None:
    """Writes something that went wrong, at ERROR, with the traceback where there is one.

    Args:
        message: What failed.
        trouble: The exception, whose traceback is then written under the line; `None` for a
            failure that raised nothing. A variable of one's own may not be called `trouble`.
        **variables: Its variables, named; contents are written out, secrets excepted.
    """
    GENERAL_LOG.error("%s", spell_out(message, variables), exc_info=trouble)


def spell_out(message: str, variables: Mapping[str, object]) -> str:
    """Puts a message and its variables into the one line the log carries.

        Login: the return read — host='127.0.0.1:5000', code=<hidden, 30 characters>

    Args:
        message: The message.
        variables: Its variables, in the order they were given.

    Returns:
        The message alone when there is no variable; the message, an em dash and the variables
        otherwise.
    """
    if not variables:
        return message
    written = ", ".join(f"{name}={shown(name, value)}" for name, value in variables.items())
    return f"{message} — {written}"


def shown(name: str, value: object) -> str:
    """Writes out one variable's content, unless its name says it is a secret.

    Args:
        name: The variable's name, which is what decides.
        value: Its content.

    Returns:
        The content, cut at `VALUE_LIMIT`; a description of its length for a secret.
    """
    if is_a_secret(name):
        return hidden(value)
    return cut(readable(sanitised(value)))


def is_a_secret(name: str) -> bool:
    """Says whether a field's name forbids writing its content.

    Args:
        name: The field's name.

    Returns:
        True if it carries one of `SECRET_NAMES`.
    """
    lowered = name.lower()
    return any(word in lowered for word in SECRET_NAMES)


def hidden(value: object) -> str:
    """Describes a secret without writing it: its length, and nothing else.

    Args:
        value: The secret.

    Returns:
        `<absent>` for nothing at all, `<hidden, n characters>` otherwise.
    """
    if value is None:
        return "<absent>"
    return f"<hidden, {len(str(value))} characters>"


def sanitised(value: object) -> object:
    """Walks a value and replaces every secret-named field inside it.

    A body is logged whole, and a body is where a secret travels: the `code` and the `state` of the
    return from Discord are fields of `request.args`, not variables of their own.

    Args:
        value: Anything about to be written out.

    Returns:
        The same value, with the fields whose name is a secret's replaced by their description.
        Mappings come back as plain dicts, sequences as lists.
    """
    if isinstance(value, Mapping):
        return {str(name): hidden(content) if is_a_secret(str(name)) else sanitised(content)
                for name, content in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitised(item) for item in value]
    return value


def readable(value: object) -> str:
    """Writes a value the way it is read back: JSON for a structure, `repr` for a string.

    `repr` for strings on purpose - an empty one, a trailing space or a stray newline are read in
    the quotes and invisible without them. Anything JSON refuses (a date, an object) goes through
    `str`, as the log wants what it looks like, not what it can be reloaded from.

    Args:
        value: The value.

    Returns:
        Its written form.
    """
    if value is None or isinstance(value, (bool, int, float)):
        return str(value)
    if isinstance(value, str):
        return repr(value)
    try:
        return json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return repr(value)


def without_the_secrets(url: str) -> str:
    """A URL as a log may carry it: every parameter but the credentials in it.

    A URL is worth having whole - the redirect URI Discord compares character by character, the
    scope asked for, the game an address names - and the `state` and the `code` travelling in it
    are credentials. Used on the authorization URL and on the `Location` of every redirect, which
    is the same URL coming back as a header.

    The query is rebuilt unescaped, as it reads rather than as it would be replayed: this is a log.

    Args:
        url: The URL.

    Returns:
        The same URL, every secret-named parameter replaced by a description of its length.
    """
    parts = urlsplit(url)
    if not parts.query:
        return url
    parameters = [f"{name}={hidden(value) if is_a_secret(name) else value}"
                  for name, value in parse_qsl(parts.query)]
    return urlunsplit(parts._replace(query="&".join(parameters)))


def cut(text: str) -> str:
    """Shortens what is too long to be worth a whole file, and says what was cut.

    Args:
        text: The written value.

    Returns:
        The text as it is, or its beginning followed by its full length.
    """
    if VALUE_LIMIT <= 0 or len(text) <= VALUE_LIMIT:
        return text
    return f"{text[:VALUE_LIMIT]}… (cut, {len(text)} characters in all)"
