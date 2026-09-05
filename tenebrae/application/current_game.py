"""The current game - one per process, in module globals - and the moves that change it.

The server lays out a scenario's set-up, read from `tenebrae/scenarios/` - no. 4, "La guerre des
nains", until a new game is opened on another one. The rules are not here: the possible moves and
their validation come from `tenebrae.engine`; this module holds the state the routes expose
(`SCENARIO`, `BOARD`, `TURN`, `REGISTER`, `CASUALTIES`, `SEATS`, `VERSION`), the snapshots the
browsers receive of it, and the operations every move goes through. Only the die roll
(`roll_the_die`) is here, so that the tests can fix it.

Two ways of reaching the globals, and the difference matters:

- `BOARD`, `TURN`, `REGISTER`, `CASUALTIES` and `SEATS` are bound once and changed in place:
  import them by name;
- `VERSION` is rebound at every move, `GAME_ID` whenever another game is opened, `SCENARIO` and
  `SCENARIO_NUMBER` whenever a new game is opened on another set-up (`switch_to_the_scenario`), and
  `BROADCASTER` and `roll_the_die` are substituted by the tests: read all of them from the module -
  `current_game.VERSION`, `current_game.SCENARIO`, `current_game.roll_the_die()` - so that the new
  binding reaches every caller.

The game is **saved in MongoDB** through the repository `wire_persistence` hooked on
(`persistence.py`), in state dicts, after every move. Several games live in base, one document
each; `GAME_ID` says which one the process is playing, and it is the one every save writes into.
`GET /game/<id>` opens another, `GET /game` the one in play. Each browser follows the game through
an open stream, and `mark_a_move` is the only point from which anything is published:
`open_a_new_game`, `restore_the_game` and `save_the_game` are its only callers. The snapshot it
pushes carries the log, hence the rule every route follows: **log before marking the move**.
"""

import random
import time
from typing import Optional

from tenebrae.application.logs.battle_log import LOG, log_lines
from tenebrae.application.logs.general_log import event, note
from tenebrae.application.logs.combat_sentences import (announce_the_end, combat_message,
                                                        describe_the_ratio, label_the_end,
                                                        retreat_messages)
from tenebrae.application.persistence import game_repository
from tenebrae.application.pieces import PIECES_BY_KEY
from tenebrae.application.stream import Broadcaster
from tenebrae.engine import ai, victory
from tenebrae.engine.board import Board
from tenebrae.engine.casualties import Casualties
from tenebrae.engine.combat import CombatResult
from tenebrae.engine.combat_register import CombatRegister
from tenebrae.engine.hexagon import Hex
from tenebrae.engine.models.seats import Seats
from tenebrae.engine.phase import Turn
from tenebrae.engine.piece import CATALOGUE
from tenebrae.engine.repositories.game import GameState
from tenebrae.engine.scenario import Scenario, available_scenarios, read, scenario

# The scenario the server opens on: "La guerre des nains" (see `tenebrae/scenarios/README.md`).
DEFAULT_SCENARIO = 4

# The set-up being played, and its number. Read at start-up, then rebound by
# `switch_to_the_scenario` each time a new game is opened on another one.
SCENARIO_NUMBER = DEFAULT_SCENARIO
SCENARIO = scenario(SCENARIO_NUMBER)

# The pieces currently placed: rebuilt at every board load, followed at every move.
BOARD = Board()

# The current phase: which side plays, and at what. Resumed with the board whenever a game is
# opened, and set up again on the sides of the scenario a new game is opened on.
TURN = Turn(SCENARIO.sides, {army["camp"]: army["armee"] for army in SCENARIO.armies})

# What the current combat phase has already consumed. Emptied at every phase change.
REGISTER = CombatRegister()

# The units removed from play since the game began: the booklet counts them at the end
# (`tenebrae/engine/casualties.py`). Emptied only when a new game is laid out.
CASUALTIES = Casualties()

# Who holds which side - **the table of the game `GAME_ID` names, and no other**. It travels with
# the game, in its `places` field: opening one seats the people that game seated
# (`restore_the_game`), and a new game opens with the table its creator asked for and not with the
# one of the game the process happened to be on.
#
# It used to survive a new game, on the ground that starting over was the same two people laying
# the same board out again. That was true while there was one game; there are now as many tables as
# there are documents, and carrying one into another game would seat two strangers at it.
SEATS = Seats()

# Rises by one at every move played: how the opponent's browser sees it has something to catch up
# on. Also the SSE event identifier the browser sends back in `Last-Event-ID`.
VERSION = 0

# Whom to push the game to when it changes: one subscriber per open tab, in this process.
BROADCASTER = Broadcaster()

# Whether the server has a game of its own on the board: a set-up laid out
# (`open_a_new_game`) or a saved game resumed (`restore_the_game`). Only such a game can be
# won. A board somebody has placed counters on by hand - which is what a rule looked at under the
# microscope is - is a board and not a game: nothing there is won, whoever is left standing on it.
A_GAME_IS_ON = False

# Which saved game the process is playing: the document `save_the_game` writes into, by the
# identifier the repository gives out. `None` on a board carrying no game - before anything has
# been opened, and after `put_the_game_away`.
#
# There is still **one game per process**: several games live in base, each with its own address
# (`GET /game/<id>`), but the board, the turn and the table above are single. Opening another game
# moves the whole table to it, which is why this is rebound and not accumulated.
GAME_ID: Optional[str] = None

# The game's end, once combat has left a side without a single unit ("Object of the game": "to
# crush the opponent by annihilating their troops"). `GAME_IS_OVER` closes the game - no move, no
# combat, no phase change is taken any more - and `WINNER` names the side left standing, `None`
# where the last units of both fell in the same combat.
#
# Kept here rather than read off the board: a board carrying no unit of a side is not a game won by
# itself - it is also a board on which nothing has been laid out yet. What closes a game is the
# **event**, a combat that emptied a side, and only combat is ever in a position to raise it.
GAME_IS_OVER = False
WINNER: Optional[str] = None

# How long the AI waits between two of its own actions, in seconds. Its turn is played inside one
# request and pushed action by action (`let_the_ai_play`): without this the whole turn would land
# on the watching browsers at once, counters teleporting to where they ended up. The request is
# held for that long per action, which is what watching a turn being played costs.
#
# The tests set it to nothing - a suite that waited on the AI would take minutes - the way they fix
# the die: `current_game.PAUSE_BETWEEN_AI_ACTIONS`, read here at call time.
PAUSE_BETWEEN_AI_ACTIONS = 0.5

# Whether the AI has already acted in the turn being played: the pause goes between two actions,
# not before the first.
AI_HAS_ACTED = False


def roll_the_die() -> int:
    """Rolls what the booklet calls "the die roll result".

    Isolated so that the tests can fix it without touching the engine.

    Returns:
        An integer from 1 to 6.
    """
    return random.randint(1, 6)


# --- The scenario being played ------------------------------------------------------------------


def switch_to_the_scenario(chosen: Scenario) -> None:
    """Puts the server on another set-up, ready for `open_a_new_game` to place it.

    The board is not touched here: the caller lays the pieces out, which is what marks the move.
    The table is not touched either - changing scenario sends nobody away from their seat -, but
    the turn is, since the sides and the army names are the new scenario's.

    Args:
        chosen: The scenario to play, already read from its file.
    """
    global SCENARIO, SCENARIO_NUMBER
    note("Switching set-up", from_scenario=SCENARIO_NUMBER, to_scenario=chosen.number,
         name=chosen.name, sides=list(chosen.sides), pieces=len(chosen.placement))
    SCENARIO = chosen
    SCENARIO_NUMBER = chosen.number
    TURN.set_up(SCENARIO.sides, {army["camp"]: army["armee"] for army in SCENARIO.armies})


def resume_the_scenario(number: int) -> bool:
    """Puts the server back on the scenario a saved game was played on, if its file is still there.

    A game under way is resumed whatever the file says of `enabled`: disabling a scenario withdraws
    it from the ones a **new** game can be opened on, it does not interrupt the game in progress.

    Args:
        number: The scenario number the saved game carries.

    Returns:
        True if the server is now on that scenario - it may already have been -, False if no file
        has that number any more, in which case nothing was changed.
    """
    if number == SCENARIO_NUMBER:
        return True
    files = available_scenarios()
    if number not in files:
        return False
    switch_to_the_scenario(read(files[number]))
    return True


# --- The game state and its snapshots -----------------------------------------------------------


def mark_a_move() -> int:
    """Notes that a move has been played, and pushes it to the browsers following the game.

    The compulsory passage of everything that moves - `open_a_new_game`, `restore_the_game` and
    `save_the_game` are its only callers. The snapshot is taken **here**, in the thread that has
    just written, so that the stream generators never re-read the board from their own thread.

    Returns:
        The new version number.
    """
    global VERSION
    VERSION += 1
    note("Move marked and pushed to those watching", game=GAME_ID, version=VERSION,
         phase=TURN.phase_type, side=TURN.active_side, turn=TURN.number, units=len(BOARD))
    BROADCASTER.publish(shared_snapshot())
    return VERSION


def shared_snapshot() -> dict[str, object]:
    """Takes the game state that **all** spectators have in common.

    The table is not part of it: it is the only part of the message composed per recipient, and
    the stream adds it at the moment of writing. The log is part of it - hence the rule: **log
    before marking the move**.

    Returns:
        `game`, `version`, `pieces`, `phase` and `log`.
    """
    return {"game": GAME_ID, "version": VERSION, "pieces": placed_units(),
            "phase": current_phase(), "log": log_lines()}


def lay_out_the_set_up() -> None:
    """Rebuilds the server's board from the scenario being played, without marking anything.

    The table is not touched here: it is the caller that decides what table the game opens with.
    Nothing is published either - a snapshot taken between the `clear` and the placing would show
    a deserted board, and one taken after but before the game has its identifier would carry the
    identifier of the game just left.
    """
    BOARD.clear()
    TURN.restart()
    REGISTER.reset()
    CASUALTIES.reset()
    for square, key in SCENARIO.placement.items():
        BOARD.place(Hex.from_key(square), CATALOGUE[key])
    reopen_the_game()
    note("Set-up laid out on the board", scenario=SCENARIO_NUMBER, name=SCENARIO.name,
         units=len(BOARD), first_phase=TURN.phase_type, first_side=TURN.active_side)


def reopen_the_game() -> None:
    """Opens the game the set-up laid out is: it is on, nothing is won yet, and it can be."""
    global A_GAME_IS_ON, GAME_IS_OVER, WINNER
    A_GAME_IS_ON, GAME_IS_OVER, WINNER = True, False, None


def put_the_game_away() -> None:
    """Leaves the board with no game on it: what is placed there afterwards is placed by hand.

    The board emptied out from under a game is the one case, and it is not a case the server makes
    for itself: a set-up is always laid out again in place of the one before. It is the tests that
    desert the map to look at a rule on two counters, and a rule looked at is not a game that can
    be won.

    The document goes with the game: what is played on that board afterwards belongs to no saved
    game, and the first move on it opens one of its own rather than write into the last one.
    """
    global A_GAME_IS_ON, GAME_IS_OVER, WINNER, GAME_ID
    note("Game put away: the board carries none", game=GAME_ID, units=len(BOARD))
    A_GAME_IS_ON, GAME_IS_OVER, WINNER, GAME_ID = False, False, None, None


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


def the_winning_army() -> Optional[str]:
    """The name of the army that won, or `None` - the game goes on, or nobody was left standing."""
    return TURN.army_of(WINNER) if WINNER is not None else None


def current_phase() -> dict[str, object]:
    """Serialises the phase as the browser receives it.

    A game that is over has no phase worth showing: its `label` says how it ended instead, which
    is what the toolbar displays. `over` closes the buttons, `winner` names the army that won -
    absent where the last units of both sides fell together.

    Returns:
        The turn's dict, plus `unavailable`, `over` and `winner`.
    """
    phase: dict[str, object] = dict(TURN.to_dict())
    phase["unavailable"] = unavailable_units()
    phase["over"] = GAME_IS_OVER
    phase["winner"] = the_winning_army()
    if GAME_IS_OVER:
        phase["label"] = label_the_end(the_winning_army())
    return phase


def close_the_game_if_a_side_is_wiped_out() -> None:
    """Ends the game when combat has left a side with no unit at all, and says so in the log.

    "To crush the opponent by annihilating their troops" is the booklet's first victory condition
    and the only one transcribed (`tenebrae/engine/victory.py`). Called from wherever units are
    removed - a combat, the AI's turn - and **before** the move is marked, so that the browsers
    receive the sentence with the position it speaks of.

    Called again once the game is closed it does nothing: a game ends once. Nor does it close a
    board that is carrying no game (`A_GAME_IS_ON`).
    """
    global GAME_IS_OVER, WINNER
    if GAME_IS_OVER or not A_GAME_IS_ON:
        return
    beaten = victory.annihilated_sides(BOARD, SCENARIO.sides)
    if not beaten:
        return
    standing = [side for side in SCENARIO.sides if side not in beaten]
    GAME_IS_OVER = True
    WINNER = standing[0] if len(standing) == 1 else None
    LOG.info("Game over: %s", announce_the_end(the_winning_army()))


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


def snapshot_the_game() -> GameState:
    """Takes the server's whole game state, in the form the repository writes.

    Returns:
        The scenario number, the board, the turn, the combat register, the fallen and the seats.
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
            "casualties": CASUALTIES.to_dict()["casualties"],
            "seats": SEATS.to_dict()["seats"],
            "over": GAME_IS_OVER,
            "winner": WINNER}


def restore_the_game(identifier: str, state: GameState) -> None:
    """Puts the board, the turn, the combat register and the table back as a saved game held them.

    The table comes with the game rather than staying at the server's: `places` is a field of the
    document, and opening another game seats the people that game seated. That is what makes the
    landing page's list playable - a game one holds a side in is still one's own when it is opened
    again, whoever played in between.

    Args:
        identifier: The game being opened; every save from now on writes into it.
        state: The saved state. `tilts`, `casualties`, `seats`, `over` and `winner` are read with
            `.get`: games saved before they existed must stay resumable, and a game saved before
            an end was recorded resumes as one still being played.
    """
    global A_GAME_IS_ON, GAME_IS_OVER, WINNER, GAME_ID
    another_game = identifier != GAME_ID
    note("Restoring a saved game", game=identifier, played_before=GAME_ID,
         another_game=another_game, scenario=state["scenario"],
         turn=state["turn_number"], phase=state["phase_type"], side=state["active_side"],
         units=len(state["placement"]), seats=state.get("seats"), over=state.get("over"),
         winner=state.get("winner"))
    BOARD.restore(state["placement"], state.get("tilts"))
    TURN.restore(state["active_side"], state["phase_type"], state["turn_number"])
    REGISTER.restore(state["engaged_attackers"], state["engaged_targets"])
    CASUALTIES.restore(state.get("casualties"))
    SEATS.restore(state.get("seats"))
    GAME_ID = identifier
    A_GAME_IS_ON = True
    GAME_IS_OVER = bool(state.get("over"))
    WINNER = state.get("winner")
    if another_game:
        mark_a_move()


def open_a_new_game() -> str:
    """Lays the set-up being played out as a game of its own, and plays that game from now on.

    The move is marked **after** the game has its identifier, and in one go: the snapshot says
    which game it is of, and one published while `GAME_ID` still named the game just left would
    tell every tab watching that one that its own board had changed - which is exactly the tab
    this is meant to warn (see `restore_the_game`).

    Returns:
        The new game's identifier.
    """
    global GAME_ID
    lay_out_the_set_up()
    GAME_ID = game_repository().new_game(snapshot_the_game())
    event("New game opened", game=GAME_ID, scenario=SCENARIO_NUMBER, name=SCENARIO.name,
          units=len(BOARD), seats=SEATS.to_dict()["seats"])
    mark_a_move()
    return GAME_ID


def save_the_game() -> None:
    """Records the game after a move played - a move, a combat, a phase change - and marks it.

    Into **the game being played** and no other: several games live in base, and writing into the
    most recent one would land this game's moves in somebody else's. A board carrying no game
    opens one at its first move, which is what an empty base did before.
    """
    global GAME_ID
    mark_a_move()
    was_playing = GAME_ID
    GAME_ID = game_repository().save(GAME_ID, snapshot_the_game())
    note("Game saved", game=GAME_ID, opened_by_this_save=was_playing is None,
         turn=TURN.number, phase=TURN.phase_type, side=TURN.active_side, units=len(BOARD),
         over=GAME_IS_OVER, winner=WINNER)


def pause_between_two_actions() -> None:
    """Waits before the AI's next action, so that a watcher sees the turn played and not its end.

    The first action of a turn does not wait: the pause goes **between** two, and a turn that
    began with one would only look like a slow server. Nothing waits when the pause is zero, which
    is how the tests run - a suite that watched the AI think would take minutes.
    """
    global AI_HAS_ACTED
    if AI_HAS_ACTED and PAUSE_BETWEEN_AI_ACTIONS > 0:
        time.sleep(PAUSE_BETWEEN_AI_ACTIONS)
    AI_HAS_ACTED = True


def the_ai_moves(origin: Hex, destination: Hex) -> None:
    """Logs one move of the AI and pushes it to the browsers, then waits."""
    pause_between_two_actions()
    LOG.info("AI: move %s → %s", origin.key, destination.key)
    mark_a_move()


def the_ai_fights(target: Hex, attackers: list[Hex], result: CombatResult) -> None:
    """Logs one combat of the AI - its outcome, its fall-backs, its computation - and pushes it.

    The retreats it caused are already on the board: what goes out is the position after the
    combat, counters fallen back included.
    """
    pause_between_two_actions()
    if result.breakdown is not None:
        LOG.info("AI: %s", describe_the_ratio(result))
    LOG.info("AI: %s attacker(s) on %s — %s", len(attackers), target.key, combat_message(result))
    for sentence in retreat_messages(result):
        LOG.info("AI: %s", sentence)
    mark_a_move()


def let_the_ai_play() -> None:
    """Lets the AI play its whole turn if it holds the active side, then saves the game.

    Movement, combat, and play handed back to the other side, within the request. An `if`, not a
    `while`: the AI holds only one side and always hands play back, so a save never lands on a
    phase held by the AI.

    Each action is logged and pushed as it is played rather than at the end, with a pause between
    two: the AI plays a whole turn inside one request, and a single push would show the board it
    left behind instead of the turn it played. The request is held for the length of the turn -
    that is the price of watching it.
    """
    if SEATS.occupant(TURN.active_side) != ai.AI_PLAYER:
        return
    global AI_HAS_ACTED
    AI_HAS_ACTED = False
    ai.play_turn(BOARD, TURN, REGISTER, roll_the_die, CASUALTIES,
                 moving=the_ai_moves, fighting=the_ai_fights)
    LOG.info("AI: turn played — %s (turn %s)", TURN.label, TURN.number)
    # Its combats may have taken the last unit of the other side, and its turn is then its last.
    close_the_game_if_a_side_is_wiped_out()
    save_the_game()
