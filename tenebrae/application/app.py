"""The Flask application: the Ave Tenebrae map with pieces laid out on it, and the routes to play.

The server lays out a scenario's set-up - no. 4, "La guerre des nains" -, read once and for all
from `tenebrae/scenarios/`, and passes it to the template as JSON. It is the JavaScript that
converts cube coordinates into pixels and places the pieces on the map.

The game is **saved in MongoDB**: every move played records it, and "/" resumes it where it was
left. The routes do not see the base - they go through the repository that `create_app` hooks onto
the application (`tenebrae/engine/repositories/`), and speak to it in state dicts. Without
persistence (`PERSISTENCE=none`, and the test configuration), the repository keeps nothing.

The rules are not here: the possible moves and their validation come from `tenebrae.engine`, which
the routes merely expose. The game state lives in the module globals `BOARD`, `TURN`, `REGISTER`,
`SEATS` and `VERSION`: one current game per process. Only the die roll (`roll_the_die`) is here, so
that the tests can fix it.

The game log (`tenebrae/application/battle_log.py`) is written to disk and to an in-memory queue
shown in the page. The snapshot pushed to the streams carries the log, hence the rule the routes
follow: **log before marking the move**.

The game is played **by two, one player per side**, identified by Discord (`discord_client.py` for
the OAuth2 flow, `tenebrae/engine/models/seats.py` for the table, `models/connection.py` for the
link between the session and the engine's player). The map stays public, but everything that
changes the state requires being logged in and holding the side whose phase it is: that is what the
`login_required`, `seat_required` and `active_side_required` decorators set out.

Each browser follows the other's game through an **open stream**, /stream, of Server-Sent Events
(`stream.py`); the only point from which anything is published is `mark_a_move`. `/game/state` is
still served as a fallback.

The /admin/map_fix route stands apart: it fixes by eye the errors of the map transcription, and it
is the only place where the application writes into `tenebrae/game_box/` - into `map_fix.json`,
never into `carte.json`. It is reserved to the accounts in `ADMIN_DISCORD_IDS`.

Everything the player reads - button labels, phase names, log lines - stays in French, as do the
data files; only the code is English.

Launch (from the root of the repository):

    python3 -m tenebrae.application.app

then http://127.0.0.1:5000/
"""

import json
import math
import random
import secrets
from collections.abc import Callable, Iterator, Mapping
from functools import wraps
from typing import Optional, cast
from urllib.parse import urlparse

from itsdangerous import BadSignature
from flask import Blueprint, Flask, abort, current_app, g, redirect, render_template, \
    request, send_from_directory, session, url_for
from flask.sessions import SecureCookieSessionInterface
from flask.typing import ResponseReturnValue
from werkzeug.local import LocalProxy

from tenebrae.application.battle_log import LOG, log_lines
from tenebrae.application.config import Config
from tenebrae.application.discord_client import DiscordClient, FakeDiscordClient
from tenebrae.application.models.connection import Connection, PlayerRepository
from tenebrae.application.pieces import BOX, PIECES, PIECES_BY_KEY, is_a_piece
from tenebrae.application.repositories.view import (InMemoryViewRepository, MongoViewRepository,
                                                    ViewRecord)
from tenebrae.application.stream import Broadcaster
from tenebrae.engine import ai
from tenebrae.engine import combat
from tenebrae.engine import hexagon as engine_hexagon
from tenebrae.engine.board import Board
from tenebrae.engine.combat import CombatResult
from tenebrae.engine.combat_register import CombatRegister
from tenebrae.engine.hexagon import TRANSCRIBED_MAP, Hex
from tenebrae.engine.models.seats import Seats
from tenebrae.engine.phase import COMBAT, Turn
from tenebrae.engine.piece import CATALOGUE, Piece
from tenebrae.engine.repositories.game import GameState, MongoGameRepository, NullGameRepository
from tenebrae.engine.repositories.player import (InMemoryPlayerRepository, MongoPlayerRepository,
                                                 PlayerRecord)
from tenebrae.engine.scenario import scenario

# The 16 terrains of the map, in the priority order of game_box/map.md: also the order of the fix
# buttons. The names are those of the data files, and stay in French.
TERRAINS = ("ville", "fort", "chateau", "tour", "ruines", "village", "ile", "lac", "montagne",
            "colline", "bois", "faille", "riviere", "route", "chemin", "plaine")

# The scenario the server lays out: "La guerre des nains" (see `tenebrae/scenarios/README.md`).
SCENARIO_NUMBER = 4

# The combat outcomes that change the board; any other outcome changes nothing. French, like
# everything the player reads.
COMBAT_MESSAGES = {
    "DE": "Combat résolu : Défenseur Éliminé",
    "AE": "Combat résolu : Attaquant Éliminé",
    "EX": "Combat résolu : Échange — la cible est éliminée, avec les attaquants qui ne tirent pas",
}
NO_EFFECT_MESSAGE = "Combat résolu : sans effet"
OUT_OF_RANGE_MESSAGE = "Cette unité n'est pas à portée de la cible"
NO_UNIT_MESSAGE = "Aucune unité sur cette case."

# The two refusals the combat phase register opposes. They go to the log, and the browser uses
# them so as not to highlight a unit that has already had its turn.
ALREADY_ATTACKED = "Cette unité a déjà attaqué durant cette phase de combat."
ALREADY_TARGETED = "Cette unité a déjà été attaquée durant cette phase de combat."

# Alignment of the grid on map.jpg, recorded in game_box/map.md:
#     centre(q, r) = ORIGIN + MATRIX . (q, r)
# Both constants are passed to the JavaScript, which does the conversion.
GRID_ORIGIN = [76.355, 70.511]
GRID_MATRIX = [[107.5724, -0.3407], [62.8901, 125.6828]]

# Side of a piece, in pixels of map.jpg (a hexagon is about 143 px from vertex to vertex).
PIECE_SIZE = 104

# The heartbeat of the SSE stream: after that much silence, a comment line crosses the connection
# so that no intermediary closes it as dead.
#
# TODO: PRODUCTION - 20 s stays under the usual defaults (Nginx `proxy_read_timeout` 60 s). See
# `DEPLOYMENT.md`: raise the intermediary's timeout rather than lower this one.
HEARTBEAT = 20  # seconds

# A Flask view, as the authorization decorators wrap it.
RouteFunction = Callable[..., ResponseReturnValue]

# What the factory hooks onto the application, in either branch of its configuration.
GameRepository = MongoGameRepository | NullGameRepository
ViewRepository = MongoViewRepository | InMemoryViewRepository
IdentityClient = DiscordClient | FakeDiscordClient

# The routes live on a blueprint registered by `create_app`; the game state stays in the module
# globals below.
game = Blueprint("game", __name__)

# The set-up being played, read once at start-up.
SCENARIO = scenario(SCENARIO_NUMBER)

# The pieces currently placed: rebuilt at every board load, followed at every move.
BOARD = Board()

# The current phase: which side plays, and at what. Reset with the board at every load of "/".
TURN = Turn(SCENARIO.sides, {army["camp"]: army["armee"] for army in SCENARIO.armies})

# What the current combat phase has already consumed. Emptied at every phase change.
REGISTER = CombatRegister()

# Who holds which side. Unlike the board, **not rebuilt** at every load of "/" nor at every new
# game: starting over does not send anyone away from the table.
SEATS = Seats()

# Rises by one at every move played: how the opponent's browser sees it has something to catch up
# on. Also the SSE event identifier the browser sends back in `Last-Event-ID`.
VERSION = 0

# Whom to push the game to when it changes: one subscriber per open tab, in this process.
BROADCASTER = Broadcaster()


def roll_the_die() -> int:
    """Rolls what the booklet calls "the die roll result".

    Isolated so that the tests can fix it without touching the engine.

    Returns:
        An integer from 1 to 6.
    """
    return random.randint(1, 6)


def describe_the_ratio(result: CombatResult) -> str:
    """Puts the strength ratio computation into one French sentence, for the log.

    What the ratio alone does not say: what the attackers total, what the defender opposes once
    its terrain is counted, and the die as that terrain modified it. Each term is only spelled out
    when there is a detail to spell out; the terrain is always named.

        Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4

    Args:
        result: A resolved combat, whose `breakdown` is not `None`.

    Returns:
        The sentence.

    Raises:
        ValueError: If the combat was not resolved: there is no computation to describe.
    """
    breakdown = result.breakdown
    if breakdown is None:
        raise ValueError("this combat was not resolved: no ratio to describe")
    attack = " + ".join(str(strength) for strength in breakdown.strengths)
    if len(breakdown.strengths) > 1:
        attack += f" = {breakdown.attacking_strength}"
    defence = str(breakdown.target_strength)
    if breakdown.multiplier != 1:
        defence += f" × {breakdown.multiplier} = {breakdown.defending_strength}"
    die = str(breakdown.roll)
    if breakdown.die_bonus:
        die += f" + {breakdown.die_bonus} = {breakdown.roll + breakdown.die_bonus}"
        # Table I has only six rows: saying the die was brought back avoids an addition that would
        # look wrong.
        if breakdown.roll + breakdown.die_bonus != breakdown.die:
            die += f", ramené à {breakdown.die}"
    ratio = "-".join(map(str, breakdown.ratio))
    return (f"Rapport {ratio} : attaque {attack} contre défense {defence} "
            f"({breakdown.terrain}) — dé {die}")


def combat_message(result: CombatResult) -> str:
    """Puts a combat's outcome into the French sentence the log and the browser show.

    Args:
        result: The combat, resolved or not.

    Returns:
        The sentence of `COMBAT_MESSAGES`, or `NO_EFFECT_MESSAGE` for a retreat as for an
        unresolved combat.
    """
    if result.outcome is None:
        return NO_EFFECT_MESSAGE
    return COMBAT_MESSAGES.get(result.outcome, NO_EFFECT_MESSAGE)


# --- The game state and its snapshots -----------------------------------------------------------


def mark_a_move() -> int:
    """Notes that a move has been played, and pushes it to the browsers following the game.

    The compulsory passage of everything that moves - `lay_out_the_scenario` and `save_the_game`
    are its only two callers. The snapshot is taken **here**, in the thread that has just written,
    so that the stream generators never re-read the board from their own thread.

    Returns:
        The new version number.
    """
    global VERSION
    VERSION += 1
    BROADCASTER.publish(shared_snapshot())
    return VERSION


def shared_snapshot() -> dict[str, object]:
    """Takes the game state that **all** spectators have in common.

    The table is not part of it: it is the only part of the message composed per recipient, and
    the stream adds it at the moment of writing. The log is part of it - hence the rule: **log
    before marking the move**.

    Returns:
        `version`, `pieces`, `phase` and `log`.
    """
    return {"version": VERSION, "pieces": placed_units(), "phase": current_phase(),
            "log": log_lines()}


def lay_out_the_scenario() -> list[dict[str, object]]:
    """Rebuilds the server's board from the scenario, and marks the move.

    The table is not touched: starting a game over sends nobody away from their seat. The move is
    marked **once the pieces are placed**: a snapshot taken between the `clear` and the placing
    would show a deserted board.

    Returns:
        The placed units, for display.
    """
    BOARD.clear()
    TURN.restart()
    REGISTER.reset()
    for square, key in SCENARIO.placement.items():
        BOARD.place(Hex.from_key(square), CATALOGUE[key])
    mark_a_move()
    return placed_units()


def unavailable_units() -> dict[str, list[dict[str, Optional[int] | Optional[str]]]]:
    """Lists the squares of units that can no longer attack, or be attacked, this phase.

    Squares cleared by combat are discarded: the browser no longer has a piece there to grey out.

    Returns:
        `attackers` and `targets`, each a list of serialised hexagons.
    """
    placed = BOARD.pieces
    return {
        "attackers": [Hex.from_key(key).to_dict()
                      for key in sorted(REGISTER.engaged_attackers) if key in placed],
        "targets": [Hex.from_key(key).to_dict()
                    for key in sorted(REGISTER.engaged_targets) if key in placed],
    }


def current_phase() -> dict[str, object]:
    """Serialises the phase as the browser receives it.

    Returns:
        The turn's dict, plus `unavailable`.
    """
    return TURN.to_dict() | {"unavailable": unavailable_units()}


def placed_units() -> list[dict[str, object]]:
    """Serialises the board's units in the form the browser expects.

    Everything that is not the square comes from the display catalogue, plus the tilt, which is of
    the board and not of the counter. `path` is renamed to `image`, what the browser puts into
    `src`.

    Returns:
        One entry per placed piece.
    """
    placed: list[dict[str, object]] = []
    for square, placed_piece in BOARD.pieces.items():
        hexagon = Hex.from_key(square)
        piece = dict(PIECES_BY_KEY[placed_piece.key])
        placed.append({"q": hexagon.q, "r": hexagon.r, "s": hexagon.s,
                       "tilt": BOARD.tilt_on(hexagon),
                       "image": piece.pop("path"), **piece})
    return placed


# --- The saved game -----------------------------------------------------------------------------


def game_repository() -> GameRepository:
    """The current application's game repository.

    Returns:
        Whichever `wire_persistence` hooked on.
    """
    return current_app.extensions["game_repository"]


def player_repository() -> PlayerRepository:
    """The current application's player repository.

    Returns:
        Whichever `wire_persistence` hooked on.
    """
    return current_app.extensions["player_repository"]


def view_repository() -> ViewRepository:
    """The current application's map view repository (see `models/view.py`).

    Returns:
        Whichever `wire_persistence` hooked on.
    """
    return current_app.extensions["view_repository"]


def player_view() -> Optional[ViewRecord]:
    """Reads where the session's player had got to on the map.

    Returns:
        The view, or `None` for an anonymous visitor as for a player who has adjusted nothing yet:
        the page then opens fitted to the window.
    """
    player = current_player()
    return view_repository().by_discord_id(player["discord_id"]) if player else None


def read_a_view(data: object) -> Optional[ViewRecord]:
    """Reads the view sent by the browser, reduced to its four fields.

    The scale is not bounded here: `static/zoom.js` bounds it for good, when setting as when
    restoring.

    Args:
        data: The request body, whatever it is.

    Returns:
        `{scale, x, y, fitted}`, or `None` if the body is not a dict of finite numbers.
    """
    if not isinstance(data, dict):
        return None
    try:
        view = {field: float(data[field]) for field in ("scale", "x", "y")}
    except (KeyError, TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in view.values()):
        return None
    view["fitted"] = bool(data.get("fitted"))
    return view


def snapshot_the_game() -> GameState:
    """Takes the server's whole game state, in the form the repository writes.

    Returns:
        The scenario number, the board, the turn, the combat register and the seats.
    """
    register = REGISTER.to_dict()
    return {"scenario": SCENARIO_NUMBER,
            "placement": BOARD.to_dict(),
            "tilts": BOARD.tilts,
            "active_side": TURN.active_side,
            "phase_type": TURN.phase_type,
            "turn_number": TURN.number,
            "engaged_attackers": register["engaged_attackers"],
            "engaged_targets": register["engaged_targets"],
            "seats": SEATS.to_dict()["seats"]}


def restore_the_game(state: GameState) -> None:
    """Puts the board, the turn, the combat register and the table back as a saved game held them.

    Args:
        state: The saved state. `tilts` and `seats` are read with `.get`: games saved before they
            existed must stay resumable.
    """
    BOARD.restore(state["placement"], state.get("tilts"))
    TURN.restore(state["active_side"], state["phase_type"], state["turn_number"])
    REGISTER.restore(state["engaged_attackers"], state["engaged_targets"])
    SEATS.restore(state.get("seats"))


def save_the_game() -> None:
    """Records the game after a move played - a move, a combat, a phase change - and marks it."""
    mark_a_move()
    game_repository().save(snapshot_the_game())


def let_the_ai_play() -> None:
    """Lets the AI play its whole turn if it holds the active side, then saves the game.

    Movement, combat, and play handed back to the other side, within the request. An `if`, not a
    `while`: the AI holds only one side and always hands play back, so a save never lands on a
    phase held by the AI.
    """
    if SEATS.occupant(TURN.active_side) != ai.AI_PLAYER:
        return
    moves, combats = ai.play_turn(BOARD, TURN, REGISTER, roll_the_die)
    for origin, destination in moves:
        LOG.info("AI: move %s → %s", origin.key, destination.key)
    for target, attackers, result in combats:
        if result.breakdown is not None:
            LOG.info("AI: %s", describe_the_ratio(result))
        LOG.info("AI: %s attacker(s) on %s — %s", len(attackers), target.key,
                 combat_message(result))
    LOG.info("AI: turn played — %s (turn %s)", TURN.label, TURN.number)
    save_the_game()


# --- The players --------------------------------------------------------------------------------
#
# The routes never touch `session` themselves: `the_connection()` designates the engine's player
# by their Discord identifier and re-reads them from the repository at every request.


def discord_client() -> IdentityClient:
    """The current application's identity client.

    Returns:
        Whichever `wire_authentication` hooked on.
    """
    return current_app.extensions["discord"]


def the_connection() -> Connection:
    """Builds the current request's connection: the session, and the repository to re-read from.

    Returns:
        A passing object, with no state of its own.
    """
    return Connection(session, player_repository())


def current_player() -> Optional[PlayerRecord]:
    """Reads the session's player, once per request.

    Kept on `g`: several decorators ask for it within a single request.

    Returns:
        The player, or `None` for an anonymous visitor.
    """
    if "player" not in g:
        g.player = the_connection().player()
    return g.player


def logged_in_player() -> PlayerRecord:
    """Reads the session's player where a route requires one.

    The routes behind `login_required` call this rather than `current_player`: the decorator has
    already turned the anonymous visitor away, with its own message.

    Returns:
        The player; 401 if there is none.
    """
    player = current_player()
    if player is None:
        abort(401, "no player logged in")
    return player


def is_administrator(player: Optional[PlayerRecord]) -> bool:
    """Says whether a player may fix the map.

    Args:
        player: The player, or `None` for an anonymous visitor.

    Returns:
        True if their identifier is in `ADMINISTRATORS` (see `config.py`).
    """
    return player is not None and player["discord_id"] in current_app.config["ADMINISTRATORS"]


def the_table() -> dict[str, object]:
    """Serialises the table as the current request's visitor sees it.

    Returns:
        What `table_for` gives for the session's player.
    """
    return table_for(current_player())


def table_for(player: Optional[PlayerRecord]) -> dict[str, object]:
    """Serialises who is watching and who holds what, for one spectator.

    Discord identifiers are not part of it: the browser only needs nicknames and avatars. The
    player is passed rather than read from the session because the SSE stream composes this
    outside any request.

    Args:
        player: The spectator, or `None` for an anonymous visitor.

    Returns:
        `connected`, `nickname`, `avatar`, `administrator`, `sides`, `armies`, `seats`.
    """

    def nickname_at(side: str) -> Optional[str]:
        """The nickname of whoever holds this side; the AI is not in base, it only has a name."""
        occupant = SEATS.occupant(side)
        if occupant is None:
            return None
        if occupant == ai.AI_PLAYER:
            return ai.AI_NAME
        seated = player_repository().by_discord_id(occupant)
        return seated["nickname"] if seated else None

    return {
        "connected": player is not None,
        "nickname": player["nickname"] if player else None,
        "avatar": player["avatar"] if player else None,
        "administrator": is_administrator(player),
        # A list: ordinarily zero or one side, but the test suite seats one player on both.
        "sides": SEATS.sides_of(player["discord_id"]) if player else [],
        "armies": {army["camp"]: army["armee"] for army in SCENARIO.armies},
        "seats": {side: nickname_at(side) for side in SCENARIO.sides},
    }


def login_required(view: RouteFunction) -> RouteFunction:
    """Refuses the route to anyone who has not opened a session.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 401 to anonymous visitors.
    """
    @wraps(view)
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 401, or lets the route through."""
        if current_player() is None:
            return {"allowed": False, "message": "Connectez-vous pour jouer."}, 401
        return view(*args, **kwargs)
    return wrapper


def seat_required(view: RouteFunction) -> RouteFunction:
    """Refuses the route to anyone holding no side.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 403 to spectators.
    """
    @wraps(view)
    @login_required
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 403 to a spectator, or lets the route through."""
        if not SEATS.sides_of(logged_in_player()["discord_id"]):
            return {"allowed": False, "message": "Prenez place à un camp pour jouer."}, 403
        return view(*args, **kwargs)
    return wrapper


def active_side_required(view: RouteFunction) -> RouteFunction:
    """Refuses the route to anyone not holding the side whose phase it is.

    The decorator looks only at the **seat**. The phase type and the side of the piece aimed at
    are still checked in the routes: a move outside the movement phase goes on returning 200 and
    `allowed: false`.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 403 when it is not the requester's turn.
    """
    @wraps(view)
    @login_required
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 403 out of turn, or lets the route through."""
        if not SEATS.holds(logged_in_player()["discord_id"], TURN.active_side):
            return {"allowed": False,
                    "message": f"C'est au camp {TURN.active_army} de jouer."}, 403
        return view(*args, **kwargs)
    return wrapper


def administrator_required(view: RouteFunction) -> RouteFunction:
    """Reserves the route to the accounts declared in `ADMIN_DISCORD_IDS`.

    An empty list admits nobody, and the refusal says how to declare oneself in it.

    Args:
        view: The route to protect.

    Returns:
        The wrapped route, answering 403 to everyone else.
    """
    @wraps(view)
    @login_required
    def wrapper(*args: object, **kwargs: object) -> ResponseReturnValue:
        """Answers 403 to a non-administrator, or lets the route through."""
        if not is_administrator(current_player()):
            return {"allowed": False,
                    "message": "Corriger la carte demande un compte déclaré dans "
                               "ADMIN_DISCORD_IDS."}, 403
        return view(*args, **kwargs)
    return wrapper


# --- Logging in through Discord -----------------------------------------------------------------


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


@game.route("/login")
def login() -> ResponseReturnValue:
    """Leaves for Discord, with a single-use state against CSRF.

    Returns:
        A redirect to the authorization URL.
    """
    warn_if_the_return_lands_on_another_host()
    state = the_connection().set_oauth_state()
    return redirect(discord_client().authorization_url(state))


@game.route("/login/return")
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


@game.route("/logout", methods=["POST"])
def logout() -> ResponseReturnValue:
    """Closes the session; the seat held is not given up.

    A POST, like everything that changes something: a link from another site must not log the
    player out.

    Returns:
        `{"connected": False}`.
    """
    the_connection().close()
    return {"connected": False}


# --- Two players, two sides ---------------------------------------------------------------------


@game.route("/game/seat", methods=["POST"])
@login_required
def take_a_seat() -> ResponseReturnValue:
    """Seats the requester at a free side - body `{"side": "alliance"}`.

    Two rules, in two places: an occupied side is not taken over, and the register holds that one;
    a player holds only one side, and that is here and nowhere else.

    Returns:
        `seated`, the side and the table; 400 for an unknown side, 409 for a refused seat.
    """
    side = (request.get_json(silent=True) or {}).get("side")
    if side not in SCENARIO.sides:
        abort(400, f"unknown side; expected one of {', '.join(SCENARIO.sides)}")

    player = logged_in_player()["discord_id"]
    if SEATS.holds(player, side):
        return {"seated": True, "side": side} | the_table()
    if SEATS.sides_of(player):
        return {"seated": False, "message": "Vous tenez déjà un camp."} | the_table(), 409
    if not SEATS.is_free(side):
        return {"seated": False, "message": "Ce camp est déjà tenu."} | the_table(), 409

    SEATS.seat(side, player)
    LOG.info("Seat taken: %s by %s", side, logged_in_player()["nickname"])
    save_the_game()
    return {"seated": True, "side": side} | the_table()


@game.route("/game/seat/leave", methods=["POST"])
@login_required
def leave_the_seat() -> ResponseReturnValue:
    """Gives up the requester's seat: the side becomes free again, the game stays where it is.

    Returns:
        `{"seated": False}` and the table.
    """
    player = logged_in_player()["discord_id"]
    for side in SEATS.sides_of(player):
        SEATS.free(side)
    save_the_game()
    return {"seated": False} | the_table()


@game.route("/view", methods=["POST"])
@login_required
def record_the_view() -> ResponseReturnValue:
    """Keeps where the player is on the map - body `{scale, x, y, fitted}`.

    The only route that has nothing to do with the game: it touches neither the board nor the
    version, and **publishes nothing** - pushing a view to the stream would make the other
    player's map jump. Login required, no seat: a logged-in spectator's view is kept too.

    Returns:
        The view as stored; 400 if unreadable.
    """
    view = read_a_view(request.get_json(silent=True))
    if view is None:
        abort(400, "unreadable view; expected {scale, x, y, fitted}")
    return view_repository().record(logged_in_player()["discord_id"], view)


# --- The board ----------------------------------------------------------------------------------


@game.route("/")
def board() -> ResponseReturnValue:
    """Serves the map, its pieces and the current phase.

    The game is resumed where it was left. Failing a save - first visit, empty base, null
    repository -, or if the save is that of another scenario, the set-up is rebuilt and a new game
    opened.

    Returns:
        The rendered `map.html`.
    """
    state = game_repository().load()
    if state is None or state["scenario"] != SCENARIO_NUMBER:
        placed = lay_out_the_scenario()
        game_repository().new_game(snapshot_the_game())
    else:
        restore_the_game(state)
        placed = placed_units()
    return render_template(
        "map.html",
        pieces=json.dumps(placed, ensure_ascii=False),
        grid=json.dumps({"origin": GRID_ORIGIN, "matrix": GRID_MATRIX,
                         "piece_size": PIECE_SIZE}),
        phase=json.dumps(current_phase(), ensure_ascii=False),
        table=json.dumps(the_table(), ensure_ascii=False),
        log=json.dumps(log_lines(), ensure_ascii=False),
        view=json.dumps(player_view()),
        version=VERSION,
    )


def sides_to_entrust_to_the_ai() -> list[str]:
    """Lists the sides the requester does not hold, to give to the AI.

    Returns:
        The opposing sides.

    Raises:
        ValueError: With a French message, if there is no such side or if one is held by a human.
    """
    player = logged_in_player()["discord_id"]
    opposing_sides = [side for side in SCENARIO.sides if not SEATS.holds(player, side)]
    if not opposing_sides:
        raise ValueError("Aucun camp à confier à l'IA.")
    for side in opposing_sides:
        if SEATS.occupant(side) not in (None, ai.AI_PLAYER):
            raise ValueError("Ce camp est déjà tenu.")
    return opposing_sides


@game.route("/game/new", methods=["POST"])
@seat_required
def new_game() -> ResponseReturnValue:
    """Starts over: the scenario's set-up, and a fresh game in base.

    With a body `{"against_ai": true}`, the side the requester does not hold is entrusted to the AI
    - if it is free, or already the AI's. If the scenario opens on the AI's side, it plays its
    first turn straight away. The table is set and the line written **before** the set-up, which
    is what pushes the game to the open streams.

    Returns:
        The pieces, the phase and the table; 409 if no side can go to the AI.
    """
    against_ai = bool((request.get_json(silent=True) or {}).get("against_ai"))
    if against_ai:
        try:
            opposing_sides = sides_to_entrust_to_the_ai()
        except ValueError as refusal:
            return {"message": str(refusal)} | the_table(), 409
        for side in opposing_sides:
            SEATS.seat(side, ai.AI_PLAYER)
        LOG.info("New game against the AI: scenario %s, the AI holds %s",
                 SCENARIO_NUMBER, ", ".join(opposing_sides))
    else:
        LOG.info("New game: scenario %s", SCENARIO_NUMBER)
    lay_out_the_scenario()
    game_repository().new_game(snapshot_the_game())
    let_the_ai_play()
    return {"pieces": placed_units(), "phase": current_phase()} | the_table()


@game.route("/game/state")
def game_state() -> ResponseReturnValue:
    """Tells where the game stands - the SSE stream's **fallback**.

    A browser whose `EventSource` fails five times in a row falls back on it (see `followTheGame`
    in `map.js`). With `?version=N`, only the number comes back as long as nothing has moved.
    Public, like the map.

    Returns:
        `version` and `changed`; the pieces, phase, table and log too when something moved.
    """
    known = request.args.get("version", type=int)
    if known == VERSION:
        return {"version": VERSION, "changed": False}
    return {"version": VERSION, "changed": True, "pieces": placed_units(),
            "phase": current_phase(), "table": the_table(),
            "log": log_lines()}


# --- The stream: the game pushed to those watching it -------------------------------------------


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

    with BROADCASTER.subscription() as subscriber:
        # An up-to-date browser gets a comment, enough to open the stream; a stale one - the
        # opponent played during the outage, or the server restarted - catches up at once.
        yield ": game followed\n\n" if known_version == VERSION \
            else compose(shared_snapshot())

        while True:
            state = subscriber.wait(HEARTBEAT)
            yield ": heartbeat\n\n" if state is None else compose(state)


@game.route("/stream")
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


# --- Movement -----------------------------------------------------------------------------------


@game.route("/moves")
def moves() -> ResponseReturnValue:
    """Lists the hexagons a unit placed at (q, r, s) can reach.

    The **server's board** says which piece stands there and which opponents oppose their zones of
    control to it. The `piece` parameter only serves to query an empty square.

    Returns:
        The move's description and the reachable `hexagons`.
    """
    origin = read_a_hexagon(request.args)
    piece = read_a_piece(request.args.get("piece"))
    return describe_a_move(origin, piece) | {
        "hexagons": [hexagon.to_dict() for hexagon in BOARD.moves(origin, piece)],
    }


@game.route("/move", methods=["POST"])
@active_side_required
def move() -> ResponseReturnValue:
    """Moves a unit from `origin` to `destination`, if the rules allow it.

    The server recomputes the reach and applies the move to its board. Movement is open only to the
    active side during its movement phase: outside that, the move is refused without the board
    budging.

    Returns:
        The move's description, `allowed`, the destination and the tilt the board drew.
    """
    demand = request.get_json(silent=True) or {}
    origin = read_a_hexagon(demand.get("origin") or {})
    destination = read_a_hexagon(demand.get("destination") or {})
    piece = read_a_piece(demand.get("piece"))
    described = describe_a_move(origin, piece)
    placed = BOARD.piece_on(origin)
    out_of_phase = placed is not None and not TURN.allows_movement(placed.side)
    allowed = not out_of_phase and BOARD.move(origin, destination, piece)
    if allowed:
        save_the_game()
    return described | {"allowed": allowed, "destination": destination.to_dict(),
                        "tilt": BOARD.tilt_on(destination)}


def describe_a_move(origin: Hex, piece: Optional[Piece]) -> dict[str, object]:
    """Serialises what the server knows of the departing unit.

    Args:
        origin: The departure square.
        piece: The piece to assume if the square is empty.

    Returns:
        `origin`, `piece`, `side` and `movement`.
    """
    placed = BOARD.piece_on(origin) or piece
    return {
        "origin": origin.to_dict(),
        "piece": placed.key if placed else None,
        "side": placed.side if placed else None,
        "movement": BOARD.movement_of(origin, piece),
    }


@game.route("/phase")
def phase() -> ResponseReturnValue:
    """Serves the current phase, for the browser's label and blocks.

    Returns:
        The phase as `current_phase` serialises it.
    """
    return current_phase()


@game.route("/phase/next", methods=["POST"])
@active_side_required
def next_phase() -> ResponseReturnValue:
    """Steps to the next phase; magic is stepped over by itself, the combat register emptied.

    Returns:
        The new phase.
    """
    TURN.advance()
    REGISTER.reset()
    LOG.info("Phase: %s (turn %s)", TURN.label, TURN.number)
    save_the_game()
    let_the_ai_play()
    return current_phase()


# --- Combat -------------------------------------------------------------------------------------


def read_prefixed_hexagon(prefix: str, source: Mapping[str, object]) -> Hex:
    """Reads a `Hex` from `{prefix}q`, `{prefix}r`, `{prefix}s` - for two hexagons in one URL.

    Args:
        prefix: `"a"` for the attacker, `"c"` for the target.
        source: The query string.

    Returns:
        The hexagon; 400 or 404 as `read_a_hexagon` decides.
    """
    return read_a_hexagon({name: source.get(f"{prefix}{name}") for name in ("q", "r", "s")})


@game.route("/combat/range")
def check_range() -> ResponseReturnValue:
    """Says whether the unit at `a...` can engage the target at `c...`.

    An attacker out of range, or that has already had its turn this phase, is refused and the
    refusal goes to the log.

    Returns:
        `in_range`, `available` and a French `message` when refused.
    """
    target = read_prefixed_hexagon("c", request.args)
    attacker = read_prefixed_hexagon("a", request.args)
    attacking_piece = BOARD.piece_on(attacker)
    if attacking_piece is None:
        return {"in_range": False, "available": False, "message": NO_UNIT_MESSAGE}
    within_range = combat.in_range(attacker, attacking_piece, target)
    available = REGISTER.can_attack(attacker.key)
    if not available:
        message = ALREADY_ATTACKED
    elif not within_range:
        message = OUT_OF_RANGE_MESSAGE
    else:
        message = None
    if message:
        LOG.info(message)
    return {"in_range": within_range, "available": available, "message": message}


@game.route("/combat/target")
def check_target() -> ResponseReturnValue:
    """Says whether the unit at `c...` can still be taken as a target this combat phase.

    Returns:
        `available` and a French `message` when refused.
    """
    target = read_prefixed_hexagon("c", request.args)
    if BOARD.piece_on(target) is None:
        return {"available": False, "message": NO_UNIT_MESSAGE}
    available = REGISTER.can_be_targeted(target.key)
    message = None if available else ALREADY_TARGETED
    if message:
        LOG.info(message)
    return {"available": available, "message": message}


def sort_the_attackers(squares: list[object], target: Hex) -> tuple[list[Hex], list[str]]:
    """Keeps the attackers the rules allow against a target, and explains each refusal.

    Args:
        squares: The attackers' coordinates, as the browser sent them.
        target: The target's square.

    Returns:
        The valid attackers, and one French message per refused one.
    """
    valid, messages = [], []
    for square in squares:
        attacker = read_a_hexagon(square if isinstance(square, Mapping) else {})
        attacking_piece = BOARD.piece_on(attacker)
        if attacking_piece is None or attacking_piece.side != TURN.active_side:
            messages.append("Cette unité ne peut pas attaquer cette cible.")
        elif not REGISTER.can_attack(attacker.key):
            messages.append(ALREADY_ATTACKED)
        elif not combat.in_range(attacker, attacking_piece, target):
            messages.append(OUT_OF_RANGE_MESSAGE)
        else:
            valid.append(attacker)
    return valid, messages


@game.route("/combat", methods=["POST"])
@active_side_required
def fight() -> ResponseReturnValue:
    """Resolves a combat: one opposing target, one or more attackers of the active side.

    Body `{"target": {q, r, s}, "attackers": [{q, r, s}, ...]}`. The server revalidates
    everything, discards attackers out of range or having already attacked, rolls the die, applies
    the result to the board and logs the outcome in French. The combat is entered in the phase
    register **whatever its outcome**.

    Returns:
        `resolved`, and on success the outcome, the eliminated squares, the roll, the die, the
        ratio and the units now unavailable.
    """
    demand = request.get_json(silent=True) or {}
    if TURN.phase_type != COMBAT:
        return {"resolved": False, "message": "Ce n'est pas la phase de combat."}

    target = read_a_hexagon(demand.get("target") or {})
    if target.key not in BOARD.opponents_of(TURN.active_side):
        return {"resolved": False, "message": "La cible doit être une unité adverse."}
    if not REGISTER.can_be_targeted(target.key):
        LOG.info(ALREADY_TARGETED)
        return {"resolved": False, "message": ALREADY_TARGETED}

    valid, messages = sort_the_attackers(demand.get("attackers") or [], target)
    for message in messages:
        LOG.info(message)
    if not valid:
        return {"resolved": False, "message": "Aucun attaquant valide.", "messages": messages}

    roll = roll_the_die()
    result = combat.fight(BOARD, target, valid, roll)
    REGISTER.record([hexagon.key for hexagon in valid], target.key)
    message = combat_message(result)
    # The computation first, the outcome next: the browser's column reads bottom-up, so the outcome
    # ends up at the top, its breakdown just below.
    if result.breakdown is not None:
        LOG.info(describe_the_ratio(result))
    LOG.info(message)
    save_the_game()
    return {
        "resolved": True,
        "outcome": result.outcome,
        "message": message,
        "eliminated": [hexagon.to_dict() for hexagon in result.eliminated],
        "roll": roll,
        "die": result.die,
        "ratio": list(result.ratio) if result.ratio else None,
        "unavailable": unavailable_units(),
    }


# --- Fixing the map -----------------------------------------------------------------------------


def write_the_fixes(fixes: Mapping[str, str]) -> None:
    """Rewrites `map_fix.json`, sorted and one entry per line.

    The application alone writes this file; the engine reads it at its next start-up.

    Args:
        fixes: "q,r,s" -> fixed terrain.
    """
    with engine_hexagon.FIXES_PATH.open("w", encoding="utf-8") as target:
        json.dump(dict(sorted(fixes.items())), target, ensure_ascii=False, indent=0)
        target.write("\n")


@game.route("/admin/map_fix")
@administrator_required
def fix_the_map() -> ResponseReturnValue:
    """Serves the map with the terrain of each hexagon on hover, and a click to fix it.

    The **transcribed** map goes to the browser, fixes apart: the page says what the scan gave, and
    what has been fixed of it.

    Returns:
        The rendered `map_fix.html`.
    """
    return render_template(
        "map_fix.html",
        map=json.dumps({key: elements[0] for key, elements in TRANSCRIBED_MAP.items()}),
        fixes=json.dumps(engine_hexagon.read_fixes(), ensure_ascii=False),
        applied=json.dumps(engine_hexagon.APPLIED_FIXES, ensure_ascii=False),
        terrains=json.dumps(TERRAINS),
        grid=json.dumps({"origin": GRID_ORIGIN, "matrix": GRID_MATRIX}),
    )


@game.route("/admin/map_fix", methods=["POST"])
@administrator_required
def fix_a_hexagon() -> ResponseReturnValue:
    """Records the fix of a hexagon - body `{q, r, s, terrain}`.

    Choosing the terrain the **transcribed** map already gives removes the fix instead of writing
    one: that is how one goes back.

    Returns:
        The key, the terrain chosen, the original one and whether a fix now stands; 400 for an
        unknown terrain.
    """
    demand = request.get_json(silent=True) or {}
    aimed = read_a_hexagon(demand)
    terrain = demand.get("terrain")
    if terrain not in TERRAINS:
        abort(400, f"unknown terrain; expected one of {', '.join(TERRAINS)}")

    original = TRANSCRIBED_MAP[aimed.key][0]
    fixes = engine_hexagon.read_fixes()
    if terrain == original:
        fixes.pop(aimed.key, None)
    else:
        fixes[aimed.key] = terrain
    write_the_fixes(fixes)

    return {"key": aimed.key, "terrain": terrain, "original": original,
            "fixed": terrain != original}


# --- Reading the request ------------------------------------------------------------------------


def read_a_piece(key: Optional[str]) -> Optional[Piece]:
    """Finds the piece a request names in the catalogue.

    Movement points and side come from the catalogue, never from the request.

    Args:
        key: The piece key, or `None` if the request names none.

    Returns:
        The piece, or `None`; 400 for an unknown key - better refuse than move an imaginary piece.
    """
    if key is None:
        return None
    if key not in CATALOGUE:
        abort(400, f"unknown piece: {key}")
    return CATALOGUE[key]


def read_a_hexagon(source: Mapping[str, object]) -> Hex:
    """Builds a `Hex` from `q`, `r`, `s` parameters.

    Args:
        source: The query string or the request body.

    Returns:
        The hexagon; 400 if unreadable, 404 if off the map.
    """
    try:
        hexagon = Hex(*(read_a_coordinate(source[name]) for name in ("q", "r", "s")))
    except (KeyError, TypeError, ValueError):
        abort(400, "q, r and s coordinates expected, integers summing to zero")
    if not hexagon.is_on_map:
        abort(404, f"hexagon {hexagon.key} is not on the map")
    return hexagon


def read_a_coordinate(value: object) -> int:
    """Reads one cube coordinate, as the query string (text) or the JSON body (a number) gives it.

    Args:
        value: The parameter, whatever the request put there.

    Returns:
        The integer.

    Raises:
        TypeError: For anything that is neither text nor a number.
        ValueError: For text that is not an integer.
    """
    if isinstance(value, (str, int, float)):
        return int(value)
    raise TypeError(f"coordinate expected, not {type(value).__name__}")


# --- Static files -------------------------------------------------------------------------------


@game.route("/map.jpg")
def map_image() -> ResponseReturnValue:
    """Serves the scan of the map.

    Returns:
        `game_box/map.jpg`.
    """
    return send_from_directory(BOX, "map.jpg")


@game.route("/pieces/<path:path>")
def piece_image(path: str) -> ResponseReturnValue:
    """Serves the photograph of a piece.

    Args:
        path: The path relative to `pions/`.

    Returns:
        The photograph; 404 for anything that is not a single piece.
    """
    if not is_a_piece(path):
        abort(404)
    return send_from_directory(PIECES, path)


# --- The factory --------------------------------------------------------------------------------


def wire_persistence(application: Flask) -> None:
    """Hooks the three repositories onto the application, according to `PERSISTENCE`.

    The extension is imported here, and not at the top of the file: it is the only module that
    imports mongoengine at load, and an application without persistence builds without it.

    Args:
        application: The application being built.
    """
    games: GameRepository
    players: PlayerRepository
    views: ViewRepository
    if application.config["PERSISTENCE"] == "mongo":
        from tenebrae.application.extensions import db
        db.init_app(application)  # before the routes, and only once: the instance is shared
        games, players, views = (MongoGameRepository(), MongoPlayerRepository(),
                                 MongoViewRepository())
    else:
        games, players, views = (NullGameRepository(), InMemoryPlayerRepository(),
                                 InMemoryViewRepository())
    application.extensions["game_repository"] = games
    application.extensions["player_repository"] = players
    application.extensions["view_repository"] = views


def wire_authentication(application: Flask) -> None:
    """Hooks the identity client onto the application, according to `AUTHENTICATION`.

    Args:
        application: The application being built.
    """
    if application.config["AUTHENTICATION"] == "discord":
        application.extensions["discord"] = DiscordClient(
            application.config["DISCORD_CLIENT_ID"],
            application.config["DISCORD_CLIENT_SECRET"],
            application.config["DISCORD_REDIRECT_URI"])
    else:
        application.extensions["discord"] = FakeDiscordClient()


def create_app(config: Optional[type] = None) -> Flask:
    """Builds the application: the configuration, persistence, authentication, then the routes.

    Args:
        config: The configuration class; `Config` when omitted.

    Returns:
        The Flask application.

    Raises:
        RuntimeError: If `SECRET_KEY` is missing - a blunt failure at start-up rather than a Flask
            error at the first click on "se connecter".
    """
    application = Flask(__name__)
    application.config.from_object(config or Config)

    if not application.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY missing: without it no session can be signed. Set one in .env - "
            "python3 -c \"import secrets; print(secrets.token_hex(32))\"")

    wire_persistence(application)
    wire_authentication(application)
    application.register_blueprint(game)
    return application


if __name__ == "__main__":
    create_app().run(debug=True)
