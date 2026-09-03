"""The stream: the game pushed to those watching it, as Server-Sent Events.

Each browser holds `GET /stream` open and the server writes to it at the moment the game changes,
through the broadcaster of `tenebrae/application/stream.py` - which knows neither Flask nor the
game. What is Flask's is here: the SSE formatting, the table composed per recipient, the
heartbeat, and the version the browser sends back to say where it stands.
"""

import json
from collections.abc import Iterator, Mapping
from typing import Optional, cast

from flask import Blueprint, Flask, current_app, request
from flask.typing import ResponseReturnValue
from werkzeug.local import LocalProxy

from tenebrae.application import current_game
from tenebrae.application.current_game import shared_snapshot
from tenebrae.application.players import table_for, the_connection
from tenebrae.engine.repositories.player import PlayerRecord

blueprint = Blueprint("stream", __name__)

# The heartbeat of the SSE stream: after that much silence, a comment line crosses the connection
# so that no intermediary closes it as dead.
#
# TODO: PRODUCTION - 20 s stays under the usual defaults (Nginx `proxy_read_timeout` 60 s). See
# `DEPLOYMENT.md`: raise the intermediary's timeout rather than lower this one.
HEARTBEAT = 20  # seconds


def sse_message(state: Mapping[str, object], player: Optional[PlayerRecord]) -> str:
    """Formats an SSE event: the shared state, *that* player's table, the version as identifier.

    Args:
        state: The shared snapshot.
        player: The spectator behind the stream, or `None`.

    Returns:
        The `id:` and `data:` lines, terminated by a blank line.
    """
    body = json.dumps({**state, "table": table_for(player)}, ensure_ascii=False)
    return f"id: {state['version']}\ndata: {body}\n\n"


def game_stream(application: Flask, identifier: Optional[str],
                known_version: Optional[int]) -> Iterator[str]:
    """Generates the stream: the entry state where called for, then one message per move played.

    It runs **outside any request**, so an application context is pushed by hand - and pushed and
    popped **between two `yield`s**, never straddling one: Flask keeps its contexts in
    `ContextVar`s that a generator shares with whoever unrolls it. `stream_with_context` is not
    used either: it would keep `g.player` cached for the whole life of the tab, whereas the player
    is re-read here at every message.

    Args:
        application: The application, captured while still in the request.
        identifier: The Discord identifier of the spectator, or `None`.
        known_version: The version the browser already has, or `None`.

    Yields:
        SSE events, and comment lines as heartbeats.
    """
    players = application.extensions["player_repository"]

    def compose(state: Mapping[str, object]) -> str:
        """The message to write, table included - the only step requiring the application."""
        with application.app_context():
            player = players.by_discord_id(identifier) if identifier else None
            return sse_message(state, player)

    with current_game.BROADCASTER.subscription() as subscriber:
        # An up-to-date browser gets a comment, enough to open the stream; a stale one - the
        # opponent played during the outage, or the server restarted - catches up at once.
        yield ": game followed\n\n" if known_version == current_game.VERSION \
            else compose(shared_snapshot())

        while True:
            state = subscriber.wait(HEARTBEAT)
            yield ": heartbeat\n\n" if state is None else compose(state)


@blueprint.route("/stream")
def stream() -> ResponseReturnValue:
    """Opens the game's event stream. Public, like `/game/state`.

    The version the browser knows comes from `?version=N` on the first connection - an
    `EventSource` cannot set a header - or from the `Last-Event-ID` header it sends back on
    reconnection; the latter prevails. Everything the generator needs is captured **here**, while
    still in the request.

    Returns:
        A `text/event-stream` response that never closes by itself.
    """
    last = request.headers.get("Last-Event-ID")
    known_version = _as_int(last) if last is not None \
        else request.args.get("version", type=int)

    # `current_app` is a proxy bound to the request; the generator outlives it and needs the
    # application itself.
    application = cast("LocalProxy[Flask]", current_app)._get_current_object()
    response = current_app.response_class(
        game_stream(application, the_connection().identifier, known_version),
        mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    # TODO: PRODUCTION - forbids Nginx's response buffering for this response; `proxy_buffering
    # off;` in `DEPLOYMENT.md` says the same on the server side.
    response.headers["X-Accel-Buffering"] = "no"
    return response


def _as_int(text: str) -> Optional[int]:
    """Reads the `Last-Event-ID` header as an integer.

    Args:
        text: The header, which may be empty or anything at all.

    Returns:
        The integer, or `None` - which makes the full state be sent back.
    """
    try:
        return int(text)
    except ValueError:
        return None
