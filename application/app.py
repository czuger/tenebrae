"""A small Flask application that shows the Ave Tenebrae map with pieces laid out on it.

The server lays out a scenario's set-up - no. 4, "La guerre des nains" -, read once and for all
from `scenarios/`, and passes it to the template as JSON (a hidden field). It is the JavaScript
that converts cube coordinates into pixels and places the pieces on the map.

The game is **saved in MongoDB**: every move played records it, and "/" resumes it where it was
left. The routes do not see the base - they go through the repository that `create_app` hooks onto
the application (`engine/repositories/`), and speak to it in state dicts. `POST /game/new` starts
again from the set-up. Without persistence (`PERSISTENCE=none`, and the test configuration), the
repository keeps nothing: every load of "/" then places the same pieces on the same squares, as
before.

The rules are not here: the possible moves and their validation come from `engine.hexagon`, which
the /moves and /move routes merely expose. Each piece moves by the number of points read off its
counter (`engine.piece`): the browser says **which** piece it has in hand, never how many points
it has - that number is taken from the catalogue.

The server also holds the **turn** (`engine.phase.Turn`, the module global `TURN`): the routes
/phase/next, /combat and /combat/range expose it, and /move refuses a move outside the side's
movement phase. Combat resolution is in `engine.combat`; only the die roll (`roll_the_die`) is
here, so that the tests can fix it. The game log is written in two places:
`logs/battle_log.log` at the root of the repository - the second place where the application
writes to disk, a rotating file of a thousand lines, kept in three archives behind it -, and a
bounded in-memory queue, which the browser turns into a column under the unit card. Hence the rule
the routes follow: **log before marking the move**, since the snapshot pushed to the streams
carries the log (see `shared_snapshot`).

Beside the turn, the module global `REGISTER` (`engine.combat.CombatRegister`) keeps what the
current combat phase has already consumed: a unit attacks only once, a unit is attacked only once.
It is emptied at every phase change, and both /combat/range and /combat/target consult it so that
the browser does not highlight a unit that has already fought.

The game is played **by two, one player per side**, identified by Discord (see `discord_client.py`
for the OAuth2 flow, `engine/models/seats.py` for the table, `models/connection.py` for the link
between the session and the engine's player). The map stays public - a passing visitor sees it and
consults the possible moves -, but everything that changes the state requires being logged in and
holding the side whose phase it is: that is what the `login_required`, `seat_required` and
`active_side_required` decorators set out. The module global `SEATS` keeps who holds what, and
`VERSION` rises at every move played.

Each browser follows the other's game through an **open stream**, /stream, of Server-Sent Events:
it no longer asks for anything, the server pushes the game to it when it changes. The registry of
open streams is in `stream.py`; the only point from which anything is published is `mark_a_move`,
through which everything that moves passes. The /game/state route, which the browser used to poll,
is still served as a **fallback** - a page whose EventSource does not get through falls back on
it. See `DEPLOYMENT.md` for what the stream will require behind Nginx.

The /admin/map_fix route stands apart: it serves to fix by eye the errors of the map
transcription, and it is the only place where the application writes into `game_box/` - into a
file of its own, `map_fix.json`, never into `carte.json` nor `carte_details.json`. It always works
on the transcribed map, whereas the rest of the application plays on the fixed map the engine
derives from it at start-up. It is reserved to the accounts in `ADMIN_DISCORD_IDS`.

Everything the player reads - button labels, phase names, log lines - stays in French, as do the
data files; only the code is English.

Launch (from this directory):

    python3 app.py

then http://127.0.0.1:5000/
"""

import collections
import json
import logging
import logging.handlers
import math
import random
import secrets
import sys
import time
from functools import wraps
from pathlib import Path

from itsdangerous import BadSignature
from flask import Blueprint, Flask, abort, current_app, g, redirect, render_template, \
    request, send_from_directory, session, url_for

# The repository is not an installed package: we add it to sys.path to reach `engine`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config  # noqa: E402
from engine import ai  # noqa: E402
from engine import combat  # noqa: E402
from engine import hexagon as engine_hexagon  # noqa: E402
from engine.board import Board  # noqa: E402
from engine.hexagon import TRANSCRIBED_MAP, Hex  # noqa: E402
from engine.models.seats import Seats  # noqa: E402
from engine.phase import COMBAT, Turn  # noqa: E402
from engine.piece import CATALOGUE  # noqa: E402
from engine.scenario import scenario  # noqa: E402
from models.connection import Connection  # noqa: E402
from stream import Broadcaster  # noqa: E402

BOX = Path(__file__).resolve().parent.parent / "game_box"
PIECES = BOX / "pions"

# The 16 terrains of the map, in the priority order of game_box/map.md: it is also the order of
# the fix buttons. The names are those of the data files, and stay in French.
TERRAINS = ("ville", "fort", "chateau", "tour", "ruines", "village", "ile", "lac", "montagne",
            "colline", "bois", "faille", "riviere", "route", "chemin", "plaine")

# The scenario the server lays out when "/" is loaded: "La guerre des nains", dwarves against orcs
# (see `scenarios/README.md`).
SCENARIO_NUMBER = 4

# The game log: phase changes, combats declared, units out of range, results. It is written in two
# places at once - files, in `logs/` at the root of the repository, and a bounded in-memory queue,
# which the browser turns into its column under the unit card.
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "battle_log.log"

# What the current file accepts before it is set aside, and the number of archives kept behind it:
# `battle_log.log` plus `battle_log.log.1` to `.3`, that is at most 4,000 lines of game on disk.
# Beyond that the oldest archive is erased - a server running for months must not fill the disk
# with a log nobody reads.
LINES_PER_FILE = 1000
LOGS_KEPT = 3

# What the browser's column shows: the last lines, and no more. The file remains the archive; the
# page only has room for the end of the game, and a bounded queue serves it that without ever
# growing.
LINES_KEPT = 60


# What the booklet calls "the die roll result", from 1 to 6. Isolated in a function so that the
# tests can fix it without touching the engine's randomness.
def roll_the_die():
    return random.randint(1, 6)


# The three combat outcomes the todo asks to play; any other outcome changes nothing. French, like
# everything the player reads.
COMBAT_MESSAGES = {
    "DE": "Combat résolu : Défenseur Éliminé",
    "AE": "Combat résolu : Attaquant Éliminé",
    "EX": "Combat résolu : Échange — la cible est éliminée, avec les attaquants qui ne tirent pas",
}


def describe_the_ratio(result):
    """The strength ratio computation in one sentence, for the log line devoted to it.

    What the ratio alone does not say, and which nevertheless decides the combat: what the group
    of attackers totals, what the defender opposes **once its terrain is counted**, and the die as
    that same terrain modified it. A 12 against an 8 gives a 1-1 ratio in the plains and 1-2 in
    the mountains, and nothing showed it.

        Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4

    The three terms are only spelled out when there is a detail to spell out: a lone attacker, a
    terrain that multiplies nothing, a die that nothing raises are written as a single number. The
    terrain, however, is **always** named - it is what one came for, including when it does
    nothing.

    The engine does not build this sentence: it returns the numbers (`combat.RatioBreakdown`), and
    it is here that they are put into French, like the outcomes in `COMBAT_MESSAGES`.
    """
    breakdown = result.breakdown
    attack = " + ".join(str(strength) for strength in breakdown.strengths)
    if len(breakdown.strengths) > 1:
        attack += f" = {breakdown.attacking_strength}"
    defence = str(breakdown.target_strength)
    if breakdown.multiplier != 1:
        defence += f" × {breakdown.multiplier} = {breakdown.defending_strength}"
    die = str(breakdown.roll)
    if breakdown.die_bonus:
        die += f" + {breakdown.die_bonus} = {breakdown.roll + breakdown.die_bonus}"
        # Table I has only six rows: beyond that the die is brought back into it, and saying so
        # avoids an addition that would look wrong.
        if breakdown.roll + breakdown.die_bonus != breakdown.die:
            die += f", ramené à {breakdown.die}"
    ratio = "-".join(map(str, breakdown.ratio))
    return (f"Rapport {ratio} : attaque {attack} contre défense {defence} "
            f"({breakdown.terrain}) — dé {die}")


# The two refusals the combat phase register opposes. They go to the log, and the browser uses
# them so as not to highlight a unit that has already had its turn.
ALREADY_ATTACKED = "Cette unité a déjà attaqué durant cette phase de combat."
ALREADY_TARGETED = "Cette unité a déjà été attaquée durant cette phase de combat."

# What, within `pions/`, does not show a single piece: the directory of whole sheets, and the
# photographs of record sheets taken "as an overview".
EXCLUDED_DIRECTORIES = {"21-vues-d-ensemble"}
EXCLUDED_SUFFIX = "-vue-d-ensemble"

# Alignment of the grid on map.jpg, recorded in game_box/map.md:
#     centre(q, r) = ORIGIN + MATRIX . (q, r)
# Both constants are passed to the JavaScript, which does the conversion.
GRID_ORIGIN = [76.355, 70.511]
GRID_MATRIX = [[107.5724, -0.3407], [62.8901, 125.6828]]

# Side of a piece, in pixels of map.jpg (a hexagon is about 143 px from vertex to vertex).
PIECE_SIZE = 104

# The routes live on a blueprint: it is the `create_app` factory, at the end of this file, that
# registers them - after wiring up persistence. The game state, for its part, stays in the module
# globals below: one current game per process, which the tests read through `app.BOARD`.
game = Blueprint("game", __name__)


class InMemoryLog(logging.Handler):
    """The last lines of the log, kept so that the browser can show them.

    It is a *handler*, and not a call added beside each `LOG.info`: the log thus keeps a single
    point of writing, and the browser's column cannot say anything other than the file. The queue
    is bounded - a server running for a long time must not swell by one line per refused click.

    `deque.append` is atomic: the thread playing a move writes here while a stream thread copies
    the queue, and there is nothing more to lock.
    """

    def __init__(self, capacity):
        super().__init__()
        self.lines = collections.deque(maxlen=capacity)

    def emit(self, record):
        self.lines.append({
            "time": time.strftime("%H:%M:%S", time.localtime(record.created)),
            "text": record.getMessage(),
        })


class RotatingLog(logging.handlers.RotatingFileHandler):
    """The log on disk, set aside every `lines_per_file` lines.

    `RotatingFileHandler` counts bytes; here we count **lines**, because it is in lines that this
    log is read - one line per game event, and the browser's column shows the last of them. A
    threshold in bytes would say something about the disk and nothing about the game.

    The counter starts again from what the file already contains, and not from zero: a server
    restarted ten times in a day must not write ten times a thousand lines into the same file.
    """

    def __init__(self, path, lines_per_file, files_kept):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.lines_per_file = lines_per_file
        self.lines_written = self._lines_already_written(path)
        super().__init__(path, backupCount=files_kept, encoding="utf-8")

    @staticmethod
    def _lines_already_written(path):
        """What the file already carries, or zero if it does not exist yet."""
        try:
            with open(path, encoding="utf-8") as source:
                return sum(1 for _ in source)
        except OSError:
            return 0

    def shouldRollover(self, record):
        return self.lines_written >= self.lines_per_file

    def doRollover(self):
        super().doRollover()
        self.lines_written = 0

    def emit(self, record):
        super().emit(record)
        self.lines_written += 1


# The log is written one line per event, into the files under `logs/` and into memory. We
# configure it only once.
LOG = logging.getLogger("tenebrae.log")
LOG_MEMORY = InMemoryLog(LINES_KEPT)
if not LOG.handlers:
    _trace = RotatingLog(LOG_PATH, LINES_PER_FILE, LOGS_KEPT)
    _trace.setFormatter(logging.Formatter("%(asctime)s  %(message)s", "%Y-%m-%d %H:%M:%S"))
    LOG.addHandler(_trace)
    LOG.addHandler(LOG_MEMORY)
    LOG.setLevel(logging.INFO)


def log_lines():
    """The log as the page shows it: the last lines, from oldest to most recent. A copy - the
    queue goes on turning while the message travels."""
    return list(LOG_MEMORY.lines)


def is_a_piece(path):
    """Says whether `path`, relative to `pions/`, really shows a single piece."""
    directory, _, filename = path.partition("/")
    return (directory not in EXCLUDED_DIRECTORIES
            and not filename.removesuffix(".jpg").endswith(EXCLUDED_SUFFIX))


def load_pieces():
    """Returns the list of available pieces, values read off the counter included.

    The engine's catalogue carries the 127 photographs; we keep only those showing a single piece.
    Markers stay in the batch: they are placed on the map, they do not move from it.

    Everything printed on the counter goes with them - strength, fire, range, flight, symbol,
    abilities and remarks -, for the card the browser shows on hover. Values absent from the
    counter stay at `None`: it is the display that renders them as a dash.

    `Piece.to_dict()` is not reused as it is: its `movement` is the raw counter value, sometimes
    absent, whereas the key served here is the movement budget, and its `image` is the repository
    path, not that of the `/pieces/` route.
    """
    pieces = []
    for piece in sorted(CATALOGUE.values(), key=lambda piece: piece.image):
        path = PIECES / piece.image.removeprefix("game_box/pions/")
        relative = f"{path.parent.name}/{path.name}"
        if is_a_piece(relative):
            pieces.append({"key": piece.key, "path": relative, "name": name_of(path),
                           "movement": piece.movement_points, "side": piece.side,
                           "faction": piece.faction, "symbol": piece.symbol,
                           "strength": piece.strength, "fire": piece.fire, "range": piece.range,
                           "flight_movement": piece.flight_movement,
                           "special_abilities": piece.special_abilities,
                           "remarks": piece.remarks})
    return pieces


def name_of(path):
    """"01-yzent/yzent-05-1-belier.jpg" -> "yzent · 1 belier".

    The file name repeats the directory name without its number, followed by the piece's rank
    within the faction then by its description (see game_box/pions/README.md).
    """
    faction = path.parent.name.split("-", 1)[1]
    description = path.stem.removeprefix(f"{faction}-")[3:]
    return f"{faction.replace('-', ' ')} · {description.replace('-', ' ')}"


PIECE_CATALOGUE = load_pieces()
PIECES_BY_KEY = {piece["key"]: piece for piece in PIECE_CATALOGUE}

# The set-up being played, read once at start-up. A fixed scenario does not change from one load
# to the next: that is what makes it possible to exercise moves on a known position.
SCENARIO = scenario(SCENARIO_NUMBER)

# The server's game state: the pieces currently placed. It is rebuilt at every board load and
# followed at every move - it is from it that the zones of control come, which require knowing who
# occupies which square and on which side.
BOARD = Board()

# The current phase: which side plays, and at what. The side order and the army names come from
# the scenario. Like the board, the turn is reset at every load of "/".
TURN = Turn(SCENARIO.sides, {army["camp"]: army["armee"] for army in SCENARIO.armies})

# What the current combat phase has already consumed. It follows the turn: every phase stepped
# over empties it, which covers the move from the Dwarves' combat to the Orcs' as well as the next
# turn. Movement does not consult it - emptying it too often costs nothing.
REGISTER = combat.CombatRegister()

# Who holds which side (see `engine/models/seats.py`). Like the board and the turn, there is only
# one table per process: both players play the same game, each from their own browser. Unlike the
# board, it is **not rebuilt** at every load of "/" nor at every new game: starting over does not
# send anyone away from the table.
SEATS = Seats()

# The game's version number: it rises by one at every move played. That is how the opponent's
# browser sees it has something to catch up on. A plain integer is enough: there is only one
# process, and two browsers reading the same game. It serves twice - it is also the SSE stream's
# **event identifier**, the one the browser sends back in `Last-Event-ID` when it reconnects (see
# `/stream`).
VERSION = 0

# Whom to push the game to when it changes (see `stream.py`). One subscriber per open tab; the
# registry is in memory, in this process.
BROADCASTER = Broadcaster()


def mark_a_move():
    """Notes that a move has been played, and pushes it to the browsers following the game.

    This is the compulsory passage of everything that moves - `lay_out_the_scenario` and
    `save_the_game` are its only two callers, and every route that changes anything at all goes
    through one of the two. Wiring broadcasting here, and nowhere else, is what guarantees that no
    move can be played without the open streams learning of it.

    The snapshot is taken **here**, in the thread that has just written, and it is the snapshot
    that travels: stream generators thus never have to re-read the board from their own thread
    while another is modifying it (see the header of `stream.py`).
    """
    global VERSION
    VERSION += 1
    BROADCASTER.publish(shared_snapshot())
    return VERSION


def shared_snapshot():
    """The game state that **all** spectators have in common.

    Not everything is shared: `the_table` tells each of them whether they are logged in, under
    what nickname and which sides they hold - that is the only part of the message composed per
    recipient, and the stream adds it at the moment of writing (see `/stream`).

    The log is part of it, and for the same reason as the pieces: both players watch the same
    game, they read the same account of it. It is photographed here, with the rest - hence the
    rule the routes below follow: **log before marking the move**, without which the line just
    written would only leave at the next move.
    """
    return {"version": VERSION, "pieces": placed_units(), "phase": current_phase(),
            "log": log_lines()}


def lay_out_the_scenario():
    """Rebuilds the server's board from the scenario, and returns its units for display.

    The scenario gives only a "square -> piece key" pairing: the pieces are placed, then it is the
    board that is described, by `placed_units` - the set-up has nothing more to say than a resumed
    game, and the tilt the placing has just drawn is already there.

    The table is not touched: starting a game over sends nobody away from their seat.

    The move is marked **once the pieces are placed**, and not before: `mark_a_move` photographs
    the game to push it to the open streams, and a photograph taken between the `clear` and the
    placing would show a deserted board. That was already true of the polling - a `/game/state`
    falling in that interval returned an empty game - but it had to land just right; the stream
    would have landed there every time.
    """
    BOARD.clear()
    TURN.restart()
    REGISTER.reset()
    for square, key in SCENARIO.placement.items():
        BOARD.place(Hex.from_key(square), CATALOGUE[key])
    mark_a_move()
    return placed_units()


def unavailable_units():
    """The squares of units that can no longer attack, or no longer be attacked, this phase.

    Squares cleared by combat are discarded: the register keeps them - they bother nobody, nothing
    moves before the end of the phase - but the browser no longer has a piece there to grey out.
    """
    placed = BOARD.pieces
    return {
        "attackers": [Hex.from_key(key).to_dict()
                      for key in sorted(REGISTER.engaged_attackers) if key in placed],
        "targets": [Hex.from_key(key).to_dict()
                    for key in sorted(REGISTER.engaged_targets) if key in placed],
    }


def current_phase():
    """The phase as the browser receives it: the turn, and what the phase has already consumed."""
    return TURN.to_dict() | {"unavailable": unavailable_units()}


# --- The saved game ---
#
# The routes know nothing of MongoDB: they go through the repository the factory has hooked onto
# the application (see `engine/repositories/`), and exchange only state dicts with it. Under the
# test configuration - and under `PERSISTENCE=none` - that repository keeps nothing, and
# everything happens as before: every load of "/" starts again from the set-up.


def game_repository():
    """The current application's game repository."""
    return current_app.extensions["game_repository"]


def player_repository():
    """The current application's player repository."""
    return current_app.extensions["player_repository"]


def view_repository():
    """The current application's map view repository (see `models/view.py`)."""
    return current_app.extensions["view_repository"]


def player_view():
    """Where the session's player had got to on the map, or `None`.

    `None` for an anonymous visitor as for a player who has adjusted nothing yet: in both cases
    the page opens fitted to the window, as it always has.
    """
    player = current_player()
    return view_repository().by_discord_id(player["discord_id"]) if player else None


def read_a_view(data):
    """The view sent by the browser, reduced to its four fields - or `None` if it is not one.

    The body comes from outside: we take from it only what we expect, and refuse whatever is not a
    number. The scale is not bounded here - it is `apply` (`static/zoom.js`) that bounds it for
    good, when setting as when restoring, and one more bound, written elsewhere, would end up
    saying something different from that one.
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


def snapshot_the_game():
    """The server's whole game state, in the form the repository knows how to write.

    Nothing else changes while playing: the map, the counters and the scenario are reference data
    read at start-up, and it is the scenario number that says which of those set-ups the saved
    game reads against.
    """
    return {"scenario": SCENARIO_NUMBER,
            "placement": BOARD.to_dict(),
            "tilts": BOARD.tilts,
            "active_side": TURN.active_side,
            "phase_type": TURN.phase_type,
            "turn_number": TURN.number} | REGISTER.to_dict() | SEATS.to_dict()


def restore_the_game(state):
    """Puts the board, the turn, the combat register and the table back as a saved game held them.

    `.get` on the seats: a game saved before players existed has none, and it must stay resumable
    - the table is then simply empty, and everyone comes and sits down at it.
    """
    # The tilts go back with the pieces: a resumed game finds its counters lying as they were
    # left. `.get` for the same reason as the seats - a game saved before we started keeping them
    # has none, and the board then draws fresh ones.
    BOARD.restore(state["placement"], state.get("tilts"))
    TURN.restore(state["active_side"], state["phase_type"], state["turn_number"])
    REGISTER.restore(state["engaged_attackers"], state["engaged_targets"])
    SEATS.restore(state.get("seats"))


def save_the_game():
    """Records the game after a move played - a move, a combat, a phase change.

    It is also the compulsory passage of everything that moves: the version rises here, and the
    opponent's browser learns of it at its next poll.
    """
    mark_a_move()
    game_repository().save(snapshot_the_game())


def let_the_ai_play():
    """If the active side is held by the AI, it plays its whole turn, and the game is saved.

    The turn is played in full within the request - movement, combat, and play handed back to the
    other side: a few milliseconds for some thirty units. A single save at the end; the version
    rises, and the browser sees the AI's moves at its next poll, as it would see a human
    opponent's.

    An `if`, not a `while`: the AI holds only one side - game creation sees to that - and once its
    turn is played it always hands play back. A save therefore never lands on a phase held by the
    AI, and "/" never has to make it play.
    """
    if SEATS.occupant(TURN.active_side) != ai.AI_PLAYER:
        return
    moves, combats = ai.play_turn(BOARD, TURN, REGISTER, roll_the_die)
    for origin, destination in moves:
        LOG.info("IA : déplacement %s → %s", origin.key, destination.key)
    for target, attackers, result in combats:
        message = COMBAT_MESSAGES.get(result.outcome, "Combat résolu : sans effet")
        if result.breakdown is not None:
            LOG.info("IA : %s", describe_the_ratio(result))
        LOG.info("IA : %s attaquant(s) sur %s — %s", len(attackers), target.key, message)
    LOG.info("IA : tour joué — %s (tour %s)", TURN.label, TURN.number)
    save_the_game()


def placed_units():
    """The board's units in the form the browser expects, as at set-up.

    Everything that is not the square comes from the catalogue - the image, the name, the counter
    values - and the entry goes out whole: whatever is added to it will follow by itself. Only
    `path` is renamed, to `image`, because that is what the browser puts into `src`. To it is
    added the tilt, which is not of the counter but of the board: it says how **this** piece lies,
    and the browser takes it as it is instead of drawing one (see `engine/board.py`).

    A fresh game goes through here just like a resumed one: `lay_out_the_scenario` places the
    scenario's pieces, then calls this function.
    """
    placed = []
    for square, placed_piece in BOARD.pieces.items():
        hexagon = Hex.from_key(square)
        piece = dict(PIECES_BY_KEY[placed_piece.key])
        placed.append({"q": hexagon.q, "r": hexagon.r, "s": hexagon.s,
                       "tilt": BOARD.tilt_on(hexagon),
                       "image": piece.pop("path")} | piece)
    return placed


# --- The players --------------------------------------------------------------------------------
#
# Two players, one per side, identified by Discord. The server tells them apart only by their
# Discord identifier - the very one that travels in the session, in the seats and in the state
# dict: there is a single notion of identity in the whole project.
#
# What the session carries, and the way to open it, are in a single place: `Connection`
# (`models/connection.py`), the only model the application keeps for itself. The routes no longer
# touch `session` themselves - they ask for `the_connection()`, which designates the **engine's**
# player by their Discord identifier and goes and re-reads them from the repository. The nickname
# and the avatar are therefore never copied into the session: a nickname change is visible from
# the very next request.


def discord_client():
    """The current application's identity client - the real one, or the tests' fake one."""
    return current_app.extensions["discord"]


def the_connection():
    """The current request's connection: the session, and the repository to re-read the player from.

    A passing object, with no state of its own: building it costs nothing, so there is no reason
    to keep it.
    """
    return Connection(session, player_repository())


def current_player():
    """The session's player, or `None`.

    Kept on `g`: several decorators ask for it within a single request, and that would be as many
    round trips to the base. An identifier that no longer matches anyone - base emptied, in-memory
    repository of a restarted server - returns `None` without making a fuss: the visitor becomes
    anonymous again.
    """
    if "player" not in g:
        g.player = the_connection().player()
    return g.player


def is_administrator(player):
    """Says whether this player may fix the map - see `ADMINISTRATORS` in `config.py`."""
    return player is not None and player["discord_id"] in current_app.config["ADMINISTRATORS"]


def the_table():
    """The table as the current request's visitor sees it."""
    return table_for(current_player())


def table_for(player):
    """Who is watching, who holds what - in the form the browser receives.

    Discord identifiers are not part of it: the browser only needs a nickname and an avatar to say
    who holds the Alliance, and serving an identifier to every visitor would be giving away a
    personal detail for nothing.

    The player is passed rather than read from the session: it is the **only** part of the state
    that differs from one spectator to another, and the SSE stream composes it outside any
    request, for a player it re-read from the repository itself (see `/stream`). The routes, for
    their part, call `the_table()` and see no difference.
    """

    def occupant_of(side):
        """The player seated at this side - the AI is not in base, it only has a name."""
        occupant = SEATS.occupant(side)
        if occupant == ai.AI_PLAYER:
            return {"nickname": ai.AI_NAME}
        return player_repository().by_discord_id(occupant)

    occupants = {side: occupant_of(side) for side in SCENARIO.sides}
    return {
        "connected": player is not None,
        "nickname": player["nickname"] if player else None,
        "avatar": player["avatar"] if player else None,
        "administrator": is_administrator(player),
        # A list, and not a side: ordinarily zero or one, but the test suite seats one and the
        # same player on both sides to play the game by itself.
        "sides": SEATS.sides_of(player["discord_id"]) if player else [],
        "armies": {army["camp"]: army["armee"] for army in SCENARIO.armies},
        "seats": {side: (occupant["nickname"] if occupant else None)
                  for side, occupant in occupants.items()},
    }


def login_required(view):
    """Refuses the route to anyone who has not opened a session - 401, "I do not know who you are"."""
    @wraps(view)
    def wrapper(*args, **kwargs):
        if current_player() is None:
            return {"allowed": False, "message": "Connectez-vous pour jouer."}, 401
        return view(*args, **kwargs)
    return wrapper


def seat_required(view):
    """Refuses the route to anyone holding no side - 403, "you are not at the table"."""
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not SEATS.sides_of(current_player()["discord_id"]):
            return {"allowed": False, "message": "Prenez place à un camp pour jouer."}, 403
        return view(*args, **kwargs)
    return wrapper


def active_side_required(view):
    """Refuses the route to anyone not holding the side whose phase it is - 403, "not your turn".

    The decorator looks only at the **seat**. The phase type and the side of the piece aimed at
    are still checked in the routes, from the turn and the board: a move outside the movement
    phase goes on returning 200 and `allowed: false`, a combat outside its phase 200 and
    `resolved: false`. It is that boundary which leaves the earlier checks untouched.
    """
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not SEATS.holds(current_player()["discord_id"], TURN.active_side):
            return {"allowed": False,
                    "message": f"C'est au camp {TURN.active_army} de jouer."}, 403
        return view(*args, **kwargs)
    return wrapper


def administrator_required(view):
    """Reserves the route to the accounts declared in `ADMIN_DISCORD_IDS`.

    An empty list admits nobody: a security variable whose absence would open everything would be
    a trap, and the refusal says how to declare oneself in it.
    """
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not is_administrator(current_player()):
            return {"allowed": False,
                    "message": "Corriger la carte demande un compte déclaré dans "
                               "ADMIN_DISCORD_IDS."}, 403
        return view(*args, **kwargs)
    return wrapper


def oauth_state_diagnosis(expected, received):
    """Why the anti-CSRF state does not pass, in plain words for the log.

    Three cases, and they are not cured the same way: a state absent from the **session** means
    the cookie set at departure did not come back - a different host between the outward and
    return trips (`localhost` against `127.0.0.1`), a "Secure" cookie over http, a session emptied
    meanwhile; a state absent from the **request**, that Discord did not return the parameter; two
    different states, a replayed or forged return. The log says which one, the host requested and
    whether a session cookie arrived at all - without ever writing the states themselves.
    """
    if not expected:
        cause = "état d'authentification absent de la session"
    elif not received:
        cause = "état d'authentification absent de la requête"
    else:
        cause = "état d'authentification différent de celui de la session"
    return f"{cause} (hôte {request.host}, {session_cookie_state()})"


def session_cookie_state():
    """The session cookie as it arrived: absent, unreadable, or readable and carrying what.

    A cookie **present but without the state** has two explanations that do not look alike, and
    only this line tells them apart. Unreadable - the signature does not check out - means it was
    signed by another `SECRET_KEY`: the key changed in `.env`, or two servers answer on the same
    host. Readable means another request rewrote the cookie between the outward and return trips -
    a neighbouring tab, a poll in flight - and the list of keys it still carries says where that
    session came from. The keys alone: never the values.
    """
    cookie = request.cookies.get(current_app.config["SESSION_COOKIE_NAME"])
    if cookie is None:
        return "cookie de session absent"
    try:
        current_app.session_interface.get_signing_serializer(current_app).loads(cookie)
    except BadSignature:
        return "cookie de session présent mais illisible — signé par une autre SECRET_KEY ?"
    contents = ", ".join(sorted(session.keys()))
    return f"cookie de session lisible, session {'portant ' + contents if contents else 'vide'}"


@game.route("/login")
def login():
    """Leaves for Discord, with a single-use state against CSRF."""
    state = the_connection().set_oauth_state()
    return redirect(discord_client().authorization_url(state))


@game.route("/login/return")
def login_return():
    """The return from Discord: we check the state, exchange the code, open the session.

    The state is **removed** from the session first of all - that is `Connection.take_oauth_state`'s
    job: a replayed return will find nothing left to compare against. The comparison goes through
    `compare_digest` - it is a secret, it is not compared character by character.
    """
    if request.args.get("error"):  # the player refused on Discord's page
        return redirect(url_for("game.board"))

    connection = the_connection()
    expected = connection.take_oauth_state()
    received = request.args.get("state")
    if not expected or not received or not secrets.compare_digest(expected, received):
        LOG.info("Connexion refusée : %s", oauth_state_diagnosis(expected, received))
        abort(400, "état d'authentification absent ou inattendu")
    code = request.args.get("code")
    if not code:
        LOG.info("Connexion refusée : code d'autorisation absent de la requête")
        abort(400, "code d'autorisation absent")

    # No `try` around the two exchanges: a `DiscordError` comes back up as it is, with the status
    # and the body of Discord's answer in its message, and Flask traces its stack. Catching it to
    # return a mute 502 left only "Discord did not answer" to read.
    token = discord_client().exchange_code(code)
    identity = discord_client().identity(token)

    player = connection.open(identity)
    LOG.info("Connexion : %s", player["nickname"])
    return redirect(url_for("game.board"))


@game.route("/logout", methods=["POST"])
def logout():
    """Closes the session. The seat held is not given up: one comes back to sit in it.

    A POST, like everything that changes something here: a link or an image from another site must
    not be able to log the player out.
    """
    the_connection().close()
    return {"connected": False}


@game.route("/game/seat", methods=["POST"])
@login_required
def take_a_seat():
    """Sitting down at a free side - body `{"side": "alliance"}`.

    Two rules, and they do not live in the same place: an occupied side is not taken over, and it
    is the register that holds that one; a player holds only one side, and that is here and
    nowhere else - a player seated on both sides would play alone against themselves.
    """
    side = (request.get_json(silent=True) or {}).get("side")
    if side not in SCENARIO.sides:
        abort(400, f"unknown side; expected one of {', '.join(SCENARIO.sides)}")

    player = current_player()["discord_id"]
    if SEATS.holds(player, side):
        return {"seated": True, "side": side} | the_table()
    if SEATS.sides_of(player):
        return {"seated": False, "message": "Vous tenez déjà un camp."} | the_table(), 409
    if not SEATS.is_free(side):
        return {"seated": False, "message": "Ce camp est déjà tenu."} | the_table(), 409

    SEATS.seat(side, player)
    LOG.info("Place prise : %s par %s", side, current_player()["nickname"])
    save_the_game()
    return {"seated": True, "side": side} | the_table()


@game.route("/game/seat/leave", methods=["POST"])
@login_required
def leave_the_seat():
    """Gives up one's seat: the side becomes free again, the game stays where it is."""
    player = current_player()["discord_id"]
    for side in SEATS.sides_of(player):
        SEATS.free(side)
    save_the_game()
    return {"seated": False} | the_table()


@game.route("/view", methods=["POST"])
@login_required
def record_the_view():
    """Keeps where the player is on the map - body `{scale, x, y, fitted}`.

    This is the only route in the whole server that has nothing to do with the game: it touches
    neither the board, nor the turn, nor the version, and **publishes nothing** - a view belongs
    to one pair of eyes, and pushing it to the stream would make the other player's map jump. Nor
    is it therefore a move played: nothing rises, nothing is broadcast.

    Login required, and no seat: we keep the view of a logged-in spectator as of a seated player.
    An anonymous visitor has nowhere to store it.
    """
    view = read_a_view(request.get_json(silent=True))
    if view is None:
        abort(400, "unreadable view; expected {scale, x, y, fitted}")
    return view_repository().record(current_player()["discord_id"], view)


@game.route("/")
def board():
    """The map, its pieces and the current phase.

    The game is resumed where it was left: the repository returns the last save, and the server
    lays it out again. Failing a save - first visit, empty base, null repository -, or if the save
    is that of a scenario other than the one being played, the scenario's set-up is rebuilt and a
    new game opened.
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


@game.route("/game/new", methods=["POST"])
@seat_required
def new_game():
    """Starts over: the scenario's set-up, and a fresh game in base.

    Previous games stay in base - that is the repository's decision -, but this one becomes the
    most recent, hence the one "/" will resume.

    With a body `{"against_ai": true}`, the side the requester does not hold is entrusted to the
    AI - if it is free, or already the AI's: we do not throw a human player out. And if the
    scenario opens on the AI's side, it plays its first turn straight away: the answer carries the
    pieces as it left them.
    """
    against_ai = bool((request.get_json(silent=True) or {}).get("against_ai"))
    if against_ai:
        player = current_player()["discord_id"]
        opposing_sides = [side for side in SCENARIO.sides if not SEATS.holds(player, side)]
        if not opposing_sides:
            return {"message": "Aucun camp à confier à l'IA."} | the_table(), 409
        for side in opposing_sides:
            if SEATS.occupant(side) not in (None, ai.AI_PLAYER):
                return {"message": "Ce camp est déjà tenu."} | the_table(), 409

    # The table is set, then the line written, and the set-up only afterwards: it is the set-up
    # that marks the move and pushes the game to the open streams (see `shared_snapshot`), and it
    # must push it with the AI already seated and the line already in the log.
    if against_ai:
        for side in opposing_sides:
            SEATS.seat(side, ai.AI_PLAYER)
        LOG.info("Nouvelle partie contre l'IA : scénario %s, l'IA tient %s",
                 SCENARIO_NUMBER, ", ".join(opposing_sides))
    else:
        LOG.info("Nouvelle partie : scénario %s", SCENARIO_NUMBER)
    lay_out_the_scenario()
    game_repository().new_game(snapshot_the_game())
    let_the_ai_play()
    return {"pieces": placed_units(), "phase": current_phase()} | the_table()


@game.route("/game/state")
def game_state():
    """Where the game stands - the SSE stream's **fallback**, and nothing more.

    This is the route the browser used to poll every three seconds. It no longer polls it: it
    holds an open stream (`/stream`) and the server pushes the game to it when it changes. It is
    still served for two reasons, and it is written so as never to have to change:

    - a browser whose `EventSource` fails five times in a row falls back on it (see `followTheGame`
      in `map.js`) - an intermediary that breaks SSE must not break the game;
    - it states the state in one round trip, which is convenient to query.

    With `?version=N`, it returns only the number as long as nothing has moved; as soon as the
    version has changed, everything comes back at once - the pieces, the phase, the table - and
    the browser lays the scene out again.

    It is public: a passing visitor follows the game as they see the map.
    """
    known = request.args.get("version", type=int)
    if known == VERSION:
        return {"version": VERSION, "changed": False}
    return {"version": VERSION, "changed": True, "pieces": placed_units(),
            "phase": current_phase(), "table": the_table(),
            "log": log_lines()}


# --- The stream: the game pushed to those watching it --------------------------------------------
#
# One `GET /stream` per open tab, which never closes by itself. The server writes a message into
# it at every move played - not a second before, not one more -, and a plain comment now and then
# so that the connection stays alive.
#
# The format is that of Server-Sent Events, which the browser can read all by itself through
# `EventSource`: reconnection included, with the identifier of the last message received in
# `Last-Event-ID`. That identifier, here, is the game's version number - there was nothing left to
# invent.

# The heartbeat: after that much silence, the stream writes an SSE comment rather than nothing. A
# line beginning with ":" is ignored by the browser, but it crosses the connection, and that is
# all we ask of it - without which a firewall, a proxy or the browser itself would end up closing
# a connection it believes dead.
#
# TODO: PRODUCTION - 20 s stays under the usual default values (Nginx `proxy_read_timeout` at
# 60 s, ALB at 60 s). See `DEPLOYMENT.md`: raise the intermediary's timeout rather than lower
# this one.
HEARTBEAT = 20  # seconds


def sse_message(state, player):
    """An SSE event: the shared state, *that* player's table, and the version as identifier.

    The identifier is what the browser will send back in `Last-Event-ID` if it reconnects: the
    server will then know whether it missed anything meanwhile.
    """
    body = json.dumps(state | {"table": table_for(player)}, ensure_ascii=False)
    return f"id: {state['version']}\ndata: {body}\n\n"


def game_stream(application, identifier, known_version):
    """The stream's generator: the entry state where called for, then one message per move played.

    It runs **outside any request** - werkzeug unrolls it after the view has returned its
    response. Hence the application context pushed by hand: composing the table requires the
    player repository and the administrator list, both hooked onto the application.

    That context is pushed and popped **between two `yield`s**, never straddling one, and that is
    the only way to do it: Flask keeps its contexts in `ContextVar`s, which a generator does not
    own - it shares them with whoever unrolls it. A `with application.app_context():` wrapping the
    loop would be entered in one caller and left in another, and Flask says so bluntly: "Popped
    wrong app context".

    Nor do we use `stream_with_context`, which would keep the *request* context open for the whole
    duration of the stream - that is, as long as the tab stays open: `g.player` would be cached
    there once and for all, and a player changing nickname or leaving their seat would never see
    it. Here the player is re-read from the repository at every message, as everywhere else in the
    project.

    The subscription, on the other hand, does wrap the whole loop: it is an object of ours, with
    no `ContextVar`. Whatever happens - tab closed, network cut, server stopped - the generator is
    closed, `GeneratorExit` crosses the `with`, and the subscriber is removed.
    """
    players = application.extensions["player_repository"]

    def compose(state):
        """The message to write, table included - the only place that requires the application."""
        with application.app_context():
            player = players.by_discord_id(identifier) if identifier else None
            return sse_message(state, player)

    with BROADCASTER.subscription() as subscriber:
        # The entry state. The browser arrives with the number it knows - from the template on
        # first connection, from the `Last-Event-ID` on a reconnection. If it is up to date, we do
        # not send it the whole board for nothing: a comment is enough to open the stream, which
        # moves its `EventSource` to the "open" state. If it is not - the opponent played during
        # the outage, or the server restarted and its version started again from zero - it catches
        # up on everything at once.
        yield ": partie suivie\n\n" if known_version == VERSION \
            else compose(shared_snapshot())

        while True:
            state = subscriber.wait(HEARTBEAT)
            yield ": battement\n\n" if state is None else compose(state)


@game.route("/stream")
def stream():
    """The game's event stream. Public, like `/game/state`.

    The version the browser knows comes from two places, and never from both at once:
    `?version=N` on the first connection - an `EventSource` cannot set a header - and the
    `Last-Event-ID` header the browser sends back by itself at every reconnection. The latter
    prevails: it is more recent than the URL, which dates from when the page opened.

    Everything the generator will need to know is captured **here**, while we are still in the
    request: the application object, and the session's Discord identifier. The generator itself
    runs afterwards.
    """
    last = request.headers.get("Last-Event-ID")
    known_version = _as_int(last) if last is not None \
        else request.args.get("version", type=int)

    response = current_app.response_class(
        game_stream(current_app._get_current_object(),
                    the_connection().identifier, known_version),
        mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    # TODO: PRODUCTION - Nginx buffers responses by default, and would hold each message until its
    # buffer filled: the game would look frozen. This header forbids it for this response, with
    # nothing to configure. The `proxy_buffering off;` in `DEPLOYMENT.md` says the same thing on
    # the server side; both together, neither depending on the other.
    response.headers["X-Accel-Buffering"] = "no"
    return response


def _as_int(text):
    """The `Last-Event-ID` as an integer, or `None` if it is not one.

    The header comes from the browser: it may be empty - that is what an `EventSource` that has
    received nothing yet sends - or anything at all. A `None` simply makes the full state be sent
    back.
    """
    try:
        return int(text)
    except ValueError:
        return None


@game.route("/moves")
def moves():
    """The hexagons a unit placed at (q, r, s) can reach.

    This is where the browser comes for the squares to cover with ghosts: it applies no rule
    itself. It is the **server's board** that says which piece stands there, on which side, and
    which opponents oppose their zones of control to it. The `piece` parameter only serves to
    query an empty square; without it, the flat 5-point rate applies and the map is held to be
    free of opponents.
    """
    origin = read_a_hexagon(request.args)
    piece = read_a_piece(request.args.get("piece"))
    return describe_a_move(origin, piece) | {
        "hexagons": [hexagon.to_dict() for hexagon in BOARD.moves(origin, piece)],
    }


@game.route("/move", methods=["POST"])
@active_side_required
def move():
    """Moves a unit from `origin` to `destination`, if the rules allow it.

    The server does not take the browser's word for it: it recomputes the reach, and it is the
    server that holds the board. An accepted move is applied to it, without which the next move's
    zones of control would be computed on stale positions.

    Movement is open only to the active side, and only during its movement phase: outside that,
    the move is refused without the board budging.
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
    # The counter has been picked up and lies down again: it is the board that drew the angle, and
    # the browser receives it rather than drawing one of its own - without which the piece would
    # lie down differently again at the first page reload.
    return described | {"allowed": allowed, "destination": destination.to_dict(),
                        "tilt": BOARD.tilt_on(destination)}


def describe_a_move(origin, piece):
    """What the server knows of the departing unit: its square, its piece, its side, its points."""
    placed = BOARD.piece_on(origin) or piece
    return {
        "origin": origin.to_dict(),
        "piece": placed.key if placed else None,
        "side": placed.side if placed else None,
        "movement": BOARD.movement_of(origin, piece),
    }


@game.route("/phase")
def phase():
    """The current phase - the browser uses it for its label and its blocks."""
    return current_phase()


@game.route("/phase/next", methods=["POST"])
@active_side_required
def next_phase():
    """Steps to the next phase; magic is stepped over by itself.

    The combat register is emptied on the way: every combat phase starts again with all its units
    available, the Darkness' as well as the Alliance's, this turn as well as the next.
    """
    TURN.advance()
    REGISTER.reset()
    LOG.info("Phase : %s (tour %s)", TURN.label, TURN.number)
    save_the_game()
    let_the_ai_play()
    return current_phase()


def read_prefixed_hexagon(prefix, source):
    """A `Hex` from `{prefix}q`, `{prefix}r`, `{prefix}s` - for two hexagons in the URL."""
    return read_a_hexagon({name: source.get(f"{prefix}{name}") for name in ("q", "r", "s")})


@game.route("/combat/range")
def check_range():
    """Says whether the unit at `a...` can engage the target at `c...`: in range, and not already
    engaged.

    An attacker out of range is not added to the combat, and the refusal goes to the log - as the
    todo requires. An attacker that has already had its turn this phase is refused the same way:
    the browser then only has to leave it unhighlighted.
    """
    target = read_prefixed_hexagon("c", request.args)
    attacker = read_prefixed_hexagon("a", request.args)
    attacking_piece = BOARD.piece_on(attacker)
    if attacking_piece is None:
        return {"in_range": False, "available": False,
                "message": "Aucune unité sur cette case."}
    within_range = combat.in_range(attacker, attacking_piece, target)
    available = REGISTER.can_attack(attacker.key)
    if not available:
        message = ALREADY_ATTACKED
    elif not within_range:
        message = "Cette unité n'est pas à portée de la cible"
    else:
        message = None
    if message:
        LOG.info(message)
    return {"in_range": within_range, "available": available, "message": message}


@game.route("/combat/target")
def check_target():
    """Says whether the unit at `c...` can still be taken as a target during this combat phase.

    Until now the browser asked for its red highlight without asking the server anything; it now
    has to come through here, the phase register alone knowing who has already been attacked.
    """
    target = read_prefixed_hexagon("c", request.args)
    if BOARD.piece_on(target) is None:
        return {"available": False, "message": "Aucune unité sur cette case."}
    available = REGISTER.can_be_targeted(target.key)
    message = None if available else ALREADY_TARGETED
    if message:
        LOG.info(message)
    return {"available": available, "message": message}


@game.route("/combat", methods=["POST"])
@active_side_required
def fight():
    """Resolves a combat: one opposing target, one or more attackers of the active side.

    Body `{"target": {q, r, s}, "attackers": [{q, r, s}, ...]}`. The server revalidates
    everything, discards attackers out of range or having already attacked (with a message to the
    log), rolls the die, applies the result to the board and logs the outcome in French.

    The combat fought is entered in the phase register, **whatever its outcome**: a retreat, which
    the engine leaves without effect, has engaged its units all the same.
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

    valid, messages = [], []
    for square in demand.get("attackers") or []:
        attacker = read_a_hexagon(square or {})
        attacking_piece = BOARD.piece_on(attacker)
        if attacking_piece is None or attacking_piece.side != TURN.active_side:
            messages.append("Cette unité ne peut pas attaquer cette cible.")
        elif not REGISTER.can_attack(attacker.key):
            messages.append(ALREADY_ATTACKED)
        elif not combat.in_range(attacker, attacking_piece, target):
            messages.append("Cette unité n'est pas à portée de la cible")
        else:
            valid.append(attacker)
    for message in messages:
        LOG.info(message)

    if not valid:
        return {"resolved": False, "message": "Aucun attaquant valide.", "messages": messages}

    roll = roll_the_die()
    result = combat.fight(BOARD, target, valid, roll)
    REGISTER.record([hexagon.key for hexagon in valid], target.key)
    message = COMBAT_MESSAGES.get(result.outcome, "Combat résolu : sans effet")
    # The computation first, the outcome next: the browser's column reads the other way round from
    # the file, so the outcome ends up at the top, its breakdown just below.
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


def write_the_fixes(fixes):
    """Rewrites `map_fix.json`, sorted and one entry per line, so it stays readable.

    The application alone writes this file; it is the engine that reads it, and the path belongs
    to it. The engine will only re-read it at the next start-up.
    """
    with engine_hexagon.FIXES_PATH.open("w", encoding="utf-8") as target:
        json.dump(dict(sorted(fixes.items())), target, ensure_ascii=False, indent=0)
        target.write("\n")


@game.route("/admin/map_fix")
@administrator_required
def fix_the_map():
    """The map, the terrain of each hexagon on hover, and a click to fix it.

    The whole map goes to the browser at once: there is nothing to ask the server in order to show
    a terrain, only to record one. It is the **transcribed** map that goes, fixes apart: the page
    says what the scan gave, and what has been fixed of it.
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
def fix_a_hexagon():
    """Records the fix of a hexagon - body `{q, r, s, terrain}`.

    Choosing the terrain the **transcribed** map already gives removes the fix instead of writing
    one: that is how one goes back, and it stays true now that the engine plays on the fixed map.
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


def read_a_piece(key):
    """The piece with key `key` in the catalogue, or `None` if the request names none.

    The browser only transmits a key: movement points and side come from the catalogue, never from
    the request. An unknown key is a 400 - better refuse than move an imaginary piece.
    """
    if key is None:
        return None
    if key not in CATALOGUE:
        abort(400, f"unknown piece: {key}")
    return CATALOGUE[key]


def read_a_hexagon(source):
    """Builds a `Hex` from q, r, s parameters; 400 if unreadable, 404 if off the map."""
    try:
        hexagon = Hex(*(int(source[name]) for name in ("q", "r", "s")))
    except (KeyError, TypeError, ValueError):
        abort(400, "q, r and s coordinates expected, integers summing to zero")
    if not hexagon.is_on_map:
        abort(404, f"hexagon {hexagon.key} is not on the map")
    return hexagon


@game.route("/map.jpg")
def map_image():
    return send_from_directory(BOX, "map.jpg")


@game.route("/pieces/<path:path>")
def piece_image(path):
    if not is_a_piece(path):
        abort(404)
    return send_from_directory(PIECES, path)


def create_app(config=None):
    """Builds the application: the configuration, persistence, then the routes.

    All of Flask is born here - the module no longer has a global app, only the `game` blueprint
    and the game state. Persistence is wired in as a repository (see `engine/repositories/`),
    hooked onto the app's extensions: the routes find it again through `game_repository()` and
    know nothing of MongoDB. The imports of the Mongo branch are done here, and not at the top of
    the file, so that an app without persistence - the tests' - builds without mongoengine.
    """
    application = Flask(__name__)
    application.config.from_object(config or Config)

    # A blunt failure at start-up rather than a Flask error at the first `session[...]`, that is,
    # at the first click on "se connecter".
    if not application.config.get("SECRET_KEY"):
        raise RuntimeError(
            "SECRET_KEY missing: without it no session can be signed. Set one in .env - "
            "python3 -c \"import secrets; print(secrets.token_hex(32))\"")

    if application.config["PERSISTENCE"] == "mongo":
        from engine.repositories.game import MongoGameRepository
        from engine.repositories.player import MongoPlayerRepository
        from extensions import db
        from repositories.view import MongoViewRepository
        db.init_app(application)  # before the routes, and only once: the instance is shared
        games, players, views = (MongoGameRepository(), MongoPlayerRepository(),
                                 MongoViewRepository())
    else:
        from engine.repositories.game import NullGameRepository
        from engine.repositories.player import InMemoryPlayerRepository
        from repositories.view import InMemoryViewRepository
        games, players, views = (NullGameRepository(), InMemoryPlayerRepository(),
                                 InMemoryViewRepository())
    application.extensions["game_repository"] = games
    application.extensions["player_repository"] = players
    # The map view is not part of the game: its model and its repository belong to the application
    # (`models/view.py`, `repositories/view.py`), and not to the engine, which does not know that
    # an image exists.
    application.extensions["view_repository"] = views

    if application.config["AUTHENTICATION"] == "discord":
        from discord_client import DiscordClient
        application.extensions["discord"] = DiscordClient(
            application.config["DISCORD_CLIENT_ID"],
            application.config["DISCORD_CLIENT_SECRET"],
            application.config["DISCORD_REDIRECT_URI"])
    else:
        from discord_client import FakeDiscordClient
        application.extensions["discord"] = FakeDiscordClient()

    application.register_blueprint(game)
    return application


if __name__ == "__main__":
    create_app().run(debug=True)
