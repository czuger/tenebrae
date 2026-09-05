# `tenebrae/application/` — the map displayed in the browser

A Flask application that serves `tenebrae/game_box/map.jpg`, **lays a scenario out on it** — no. 4,
"La guerre des nains", 18 dwarves against 30 orcs — and lets the browser do the geometry. Clicking
a piece shows as **ghosts** the squares it can go to; clicking a ghost moves it there. Hovering it
opens its **card**: its photograph enlarged and everything its counter carries.

**One arrives on the list of the games saved so far** (`/`), not on the map: one picks up a game
that was left, or opens a new one — the set-up, the side one takes, and whether the opponent is the
machine. The board is at `/game/<id>`, one address per game, and `/game` is the game most recently
played (see "The list of games").

The game follows a **turn**: movement then combat, for the Dwarves then for the Orcs, round and
round (magic is skipped). The "Phase suivante" button advances; the toolbar's label says where one
stands. In the **combat phase**, a click on an opposing unit takes it as the target (red), a click
on one's own units within range designates them as attackers (gold), and "Attaquer" resolves after
the booklet's Table I. **A unit fights only once per phase**: those that have had their turn are
greyed out and refuse the click until the next phase.

The rules are not here: moves come from `tenebrae/engine/`, the application only serves them. The
JavaScript never decides the legality of a move. **Each piece moves by the number of points printed
on its counter** — from 1 to 20 depending on the unit, read from
`tenebrae/game_box/pions/pions.json` by `tenebrae.engine.piece` — and **stops on contact with
opponents**, whose zones of control cover the six squares surrounding them.

The game is played **by two, one player per side**, each identified by their Discord account: the
server refuses a move played by whoever's turn it is not, and each browser sees the other's game
advance without reloading anything — through an **event stream** the server pushes when the game
changes, and no longer by asking again every three seconds. The map itself stays visible without an
account (see "Two players, two sides" and "Logging in through Discord").

A third page, `/admin/map_fix`, serves to fix the map transcription: it is the only place where the
application writes into `tenebrae/game_box/`, and only into a file of its own. The engine applies
those fixes at start-up — so the board is played on the fixed map. It is reserved to the accounts
declared in `ADMIN_DISCORD_IDS`.

A fourth page, `/admin/scenarios`, composes a scenario on the map: pieces taken from a palette, laid
with a click, and saved as a **new file in `tenebrae/scenarios/`** — or, opened on
`/admin/scenarios/<number>/edit`, rewrites an existing one —, the only place where the
application writes there. Reserved to the same accounts.

The code is English; everything the player reads on screen is French, and so is the game data the
application serves.

## Layout

| Module | What it holds |
| --- | --- |
| `app.py` | the factory `create_app`: the configuration, persistence, authentication, then the blueprints |
| `config.py` | the configuration classes, read from `.env` |
| `current_game.py` | the game being played — `GAME_ID`, `BOARD`, `TURN`, `REGISTER`, `CASUALTIES`, `SEATS`, `VERSION` —, its snapshots, saving and restoring it, the AI's turn |
| `players.py` | the session's player, the table, the identity client |
| `persistence.py` | the repositories hooked onto the application, and how the routes reach them |
| `routes/` | the routes, one blueprint per subject, with the guards (`authorization.py`) and the request readers (`reading.py`) |
| `logs/` | the game log: the logger, its two handlers, the combat sentences |
| `stream.py` | the broadcaster behind `/stream` |
| `discord_client.py` | the OAuth2 flow, and the fake client of the tests |
| `pieces.py`, `grid.py` | the pieces and the grid alignment, as the browser receives them |
| `static/`, `templates/` | the four pages — the list of games, the board, the map-fixing page, the scenario page — and what they share: `debug.js` everywhere, and, for the three that carry a map, `geometry.js`, `zoom.js`, `pieces.js`, `pawns.js` (with `pawn_icons.json`, `faction_colours.json` and `pawn_colours.json`, the three data files it reads) |
| `extensions.py` | the MongoDB extension |
| `models/`, `repositories/` | what is not the game: the connection and the map view (see "The models") |

## Running

From the root of the repository, with the pyenv virtualenv `tenebrae`:

```
python3 -m tenebrae.application.app
```

then <http://127.0.0.1:5000/> for the list of the games saved so far,
<http://127.0.0.1:5000/game> for the one most recently played,
<http://127.0.0.1:5000/admin/map_fix> to fix the map, and
<http://127.0.0.1:5000/admin/scenarios> to compose a scenario.

`/game` **resumes the game where it was left** and lays a set-up out where there is nothing to
resume (see "Game persistence"); it redirects to that game's own address, `/game/<id>`, which is
what the list links to. `POST /game/new` opens one more.

A `.env` at the repository root is required (see `.env.example`): without `SECRET_KEY`, the
application refuses to start, and without the Discord credentials nobody can log in.

Dependencies: `Flask`, `mongoengine` and `python-dotenv` (plus `pytest` and `pytest-playwright`
for the tests). **Authentication adds none**: the session rests on `flask.session`, and
the two calls to Discord on `urllib` from the standard library.

## Game persistence

The game is recorded in **MongoDB** at every move played — a move, a combat, a phase change — and
`GET /game/<id>` resumes it. Only the game state goes there: the positions, the angle each counter lies at,
the current phase, what the combat phase has already consumed, the units removed from play, and
**who holds which side** —
knowing who plays the Alliance is part of the game, and a restart must not empty the table. Beside
it, two other collections: the known **players** (`joueurs`), and each one's **map view** (`vues`,
see "Finding one's map view again") — the only one that is not part of the game. The map, the piece
catalogue and the scenarios stay as files in `tenebrae/game_box/` and `tenebrae/scenarios/`, which
are the repository's source of truth.

The Mongo collection names and the stored field names are French, and stay so: renaming a stored
field would orphan the games already saved. The models pin them through `db_field`.

The seats travel in the state dict, with the rest, and not through separate repository methods:
`_fill()` rewrites the whole game at every move, and seats held on the side would be erased at
every save. A game recorded before players existed has no `places` field: it stays resumable, the
table is simply empty. The same holds for the `inclinaisons` field, which came later: the pieces of
an old save lie down once when it is resumed, and the first move played freezes their angles; and
for `pertes`, the units removed from play, which came later still: a game saved before the retreat
rule existed resumes with nobody fallen.

**Running a local MongoDB**, through Docker:

```
docker run -d --name tenebrae-mongo -p 27017:27017 mongo:7
```

or through Homebrew (`brew install mongodb-community && brew services start mongodb-community`).

**Configuring**, from the repository root:

```
cp .env.example .env
```

`.env` is not versioned: it is the only place where the connection details and the secrets live, and
`tenebrae/application/config.py` reads them there once at start-up. `MONGODB_URI` for the database; `SECRET_KEY`, the three `DISCORD_*`, `ADMIN_DISCORD_IDS` and `SECURE_COOKIE` for
the players (see "Logging in through Discord").

**There is no playing without MongoDB**: the game is saved at every move, and the players and
their views have no other home. The test suite runs on a base of its own, the one `make test`
brings up (`MONGODB_URI_TEST`, see "Tests"), emptied before each test.

| Route | Effect |
| --- | --- |
| `GET /` | the list of the saved games, and the form that opens one more; public, and it **creates nothing** (see "The list of games") |
| `GET /game/<id>` | that game: the process takes it up — board, turn and table — and serves the map on it; 404 in French for an identifier no game carries, one that is not an identifier at all, or a game whose scenario has left the disk |
| `GET /game` | the game most recently played, or, where there is none to resume — an empty base, a saved scenario whose file has gone — the current set-up laid out as a new one; **redirects** to `/game/<id>`, query string and all |
| `GET /game/scenarios` | the set-ups a new game may be opened on — `number`, `name`, `max_turns`, `units`, `armies` — and the `current` number; read from the files at every request, public like the map |
| `POST /game/new` | opens a game and answers `{"id": …, "url": …}`, which the browser follows; `{"scenario": N}` for the set-up, `{"side": "alliance"}` for the side its creator takes, `{"against_ai": true}` to give the rest to the machine (see "Playing against the AI"); **an account is enough, a seat is not required** — the game is created before anybody sits at it; 409 for a scenario not on offer or a side the scenario has not |
| `POST /view` — body `{scale, x, y, fitted}` | keeps where this player is on the map, and returns it as it stands; **login required, a seat not**; it is not a move played (see "Finding one's map view again") |

The previous games stay in base: `POST /game/new` erases nothing, it opens one more document. They
are no longer a history nobody reads — the list at `/` is made of them, and each one can be opened
again by its own address.

### Which document the process is playing

`save` used to write into the most recent document, and that was true as long as the server only
ever played that one. As soon as an older game can be opened, writing into "the most recent" lands
one game's moves in another's. So the process **remembers which game it is playing**:
`current_game.GAME_ID`, the identifier of its document, bound by `restore_the_game` when a game is
opened and by `open_a_new_game` when one is created, and cleared by `put_the_game_away`.

The repository's whole surface, in state dicts as before — a `GameSummary` is what a list shows, a
`GameState` what a board is played from, and neither carries a `Document`:

| Method | What it gives |
| --- | --- |
| `games()` | one `GameSummary` per document, most recently played first |
| `most_recent()` | the identifier **and** the state of the last game played, in one query, or `None` |
| `load(identifier=None)` | that game's state, or the most recent one's; `None` for an identifier no game carries **and for one that is not an identifier at all** — a badly typed address is a game that is not there, not a 500 |
| `save(identifier, state)` | writes into that document and returns the identifier written; with no identifier, or one whose document has gone, it opens a new game, which is what an empty base did before |
| `new_game(state)` | opens one, and returns its identifier |

`GameState` deliberately carries no identifier: a state dict is what a game *is*, not which row
holds it. `GameSummary` carries one, because naming the game is the whole point of a list.

The times come back from MongoDB **naive**, and a naive time serialised for a browser reads as that
browser's own: `_in_utc` puts the offset back where the fact that it is UTC is known, rather than
leaving it to be guessed at the far end.

**The routes do not know MongoDB.** They go through a *repository* (`tenebrae/engine/repositories/`)
that the `create_app` factory hooks onto the application, and exchange only state dicts with it; the
document and the queries are in `tenebrae/engine/repositories/game.py` and
`tenebrae/engine/models/game.py`, nowhere else. Serialisation, for its part, is in the engine
(`Board.to_dict`/`restore`, `Turn.restore`, `CombatRegister.to_dict`/`restore`) and depends on no
database.

**The game is not a model of the application**: it is part of the game, and the game is in the
engine. The application keeps only the orchestration — when to load, when to save, and what is
shown of it to the browser. See "The models" below, and the "Architecture" section of the root
`CLAUDE.md`.

A word on the extension: the todo asked for Flask-MongoEngine, whose last version (1.0.0, 2022)
imports `flask.json.JSONEncoder`, removed from Flask since 2.3 — it does not import under this
repository's Flask 3. `tenebrae/application/extensions.py` takes over its interface (`db =
MongoEngine()`, `db.init_app(app)`, `MONGODB_SETTINGS` in the config) on top of `mongoengine` alone.
If the extension becomes installable again, this file is the only one to change.

## The models

The application models only **what is not the game**: the connection, and the map view. Everything
else lives in `tenebrae/engine/models/` — one file per model, on both sides, and one repository per
subject beside it (`tenebrae/application/repositories/`, `tenebrae/engine/repositories/`).

| Class | Module | Mongo collection | File |
| --- | --- | --- | --- |
| `Connection` | application | — (Flask's signed cookie) | `models/connection.py` |
| `View` | application | `vues` | `models/view.py` |
| `Game` | engine | `parties` | `tenebrae/engine/models/game.py` |
| `Player` | engine | `joueurs` | `tenebrae/engine/models/player.py` |
| `Seats` | engine | — (`Game`'s `places` field) | `tenebrae/engine/models/seats.py` |

**Why `View` is here and not in the engine**: the engine does not know that an image, pixels or a
window exist — a game can be played from an interpreter, where zoom means nothing. A piece's tilt,
on the other hand, *is* part of the board: the counter really does lie askew, and both players see
it the same way; a map view belongs to one pair of eyes.

`Connection` is the link between a Flask session and the engine's player. It duplicates nothing of
what `Player` knows: it keeps only a **Discord identifier**, the one the session carries, and goes
and re-reads the player from the repository each time it is asked — that is what makes a nickname
change visible from the very next request. It is not persisted: Flask's signed cookie *is* its
storage, and it lives on the player's machine.

```python
connection = the_connection()       # Connection(session, player_repository())
connection.set_oauth_state()        # before leaving for Discord
connection.take_oauth_state()       # on the return: the state is removed from the session
connection.open(identity)           # records the engine's player, opens the session
connection.player()                 # the player's dict, re-read from the repository — or None
connection.close()                  # log out
```

The routes therefore no longer touch `session`: they ask for `the_connection()`, and the knowledge
of what the session carries — which keys, in which order, with what precaution — sits in a single
file. The session key names stay French (`joueur`, `etat_oauth`): they are already in browsers'
cookies. The dependency runs one way only: `models/connection.py` knows the engine, the engine
knows nothing of Flask.

## How it works

The server draws nothing: it passes two pieces of JSON to the template, in hidden fields
(`#pieces` and `#grid`), and `static/map.js` uses them. Two pieces are shared with the map-fixing
page: the geometry — cube ↔ pixels — in `static/geometry.js`, and the zoom — wheel, buttons,
scrolling — in `static/zoom.js` and `static/zoom.css`.

| Hidden field | Contents |
| --- | --- |
| `#pieces` | one entry per unit of the scenario: `{q, r, s}` its square, `tilt` the angle it lies at, `{key, image, name}` the piece placed, `{movement, side}` what movement uses, and the values of its counter (see "Hovering a unit") |
| `#grid` | `origin`, `matrix` and `piece_size`: the alignment of the grid on `map.jpg` |
| `#phase` | the current phase: `{side, type, army, label, number, unavailable}` (see "Phases and combat") |
| `#table` | who is watching and who holds which side: `{connected, nickname, avatar, administrator, sides, armies, seats}` (see "Two players, two sides") |
| `#game` | which saved game this page was served for, so that it can tell that another has been opened under it (see "One game per process, several URLs") |
| `#version` | the game's version number, by which the browser sees that the opponent has played |
| `#view` | where this player was on the map: `{scale, x, y, fitted}`, or `null` (see "Finding one's map view again") |
| `#initial-log` | the game log when the page opens: `[{time, text}, …]`, from the oldest line to the most recent (see "The log column") |

## The server's board

Zones of control require knowing **who occupies which square and on which side**: the server
therefore holds an `tenebrae.engine.board.Board`, rebuilt at every load of `/game/<id>` and updated
by `/move`. Without it, the zones would be computed on stale positions from the first move on.

Beside the board, the server holds an `tenebrae.engine.phase.Turn` — the module global `TURN`: which
side plays, and at what. Board and turn are **resumed from the saved game** each time one is opened,
or laid out from the scenario when a new one is (see "Game persistence"). There is only **one
current game per process**: two tabs open on the same game share the same board and the same turn —
which suits, since both players play the same game. Two tabs on **different** games do not, and
that is what "One game per process, several URLs" is about.

Beside them, the module global `SEATS` (`tenebrae/engine/models/seats.py`) keeps who holds which
side — the table of the game `GAME_ID` names, and no other. It travels in that game's `places`
field: opening a game seats the people that game seated, and a new game opens with the table its
creator asked for.

The JavaScript converts each hexagon into pixels with the formula recorded in
`tenebrae/game_box/map.md`:

```
centre(q, r) = origin + matrix . (q, r)
```

The piece is then **centred** on that point (`translate(-50%, -50%)`) then **tilted by a few
degrees**, so that the board does not look laid out with a ruler. That angle is **not** drawn by the
page: it comes from the server, with the piece, because it is part of the game state — the engine's
board draws it when placing and keeps it (`tenebrae/engine/board.py`), the save carries it, and it
changes only when the piece is moved. A page that redrew it every time made all the counters spin at
every scene laid out again. The page draws one only for the **ghosts**, which are placed nowhere.
The positions are expressed in pixels of `map.jpg`: the map is carried at its natural size by
`#board`, which the JavaScript then scales.

## Zooming in and out

The map is 6173 × 5102 px and opens **fitted to the window** — a piece is about fifteen pixels
there, nothing can be read. The board is therefore zoomed like the map-fixing page, and by the same
code (`static/zoom.js`):

- the **wheel** zooms in keeping under the cursor the point it was designating; the `+`, `−` and
  "ajuster" buttons of the toolbar do the same from the centre of the window — the card of the
  hovered piece sits under that bar (see "Hovering a unit");
- the scale runs from 5 % to 100 % — beyond the scan there is nothing more to see;
- **the zoom touches nothing else.** Everything placed on the map — pieces, ghosts, highlight — is
  expressed in pixels of `map.jpg`, in the frame of `#board`: scaling it carries the lot, and the
  click goes back through the same conversion. There is therefore no position to recompute, and
  aiming at a hexagon works at any scale;
- resizing the window **refits** the map, as long as one has not set the scale oneself — without
  which the zoom one has just chosen would be undone.

`zoom()` keeps nothing from one load to the next: it exposes the means to read a view (`scale()`,
`viewedCentre()`) and the means to restore it (`set()`, `centreOn()`), and leaves the page to
decide where to store it. `map.js` sends it to the server (see the next section);
`map_fix.html`, which loads the same zoom, does nothing with it.

## Finding one's map view again

On a map of 6173 × 5102 px, one plays zoomed in: every page reload brought the player back to the
fit, the whole map in the window, and one had to redo one's zoom then find one's corner of the
front. The server therefore keeps, **per player**, what they were looking at.

| | |
| --- | --- |
| What is stored | `{scale, x, y, fitted}` |
| Where | the `vues` collection, one document per player, overwritten at each adjustment |
| By whom | `POST /view` → `repositories/view.py` → `models/view.py` |
| Returned | in the hidden field `#view` of `GET /`, or `null` |

`x` and `y` are **not the scroll**: they are the point of `map.jpg`, in pixels of the image, that
was at the centre of the window. A `scrollLeft` in screen pixels would mean nothing at another
scale, nor on another screen; that point does. And `fitted` says the map was still set to the
window: no scale is then frozen, we refit — a window of a different size finds its own fit instead
of inheriting another screen's zoom.

The browser sends after **half a second of quiet** (`VIEW_DELAY`), and only if the view has changed
from what the server already has: one wheel gesture is worth one request, not a hundred, and
restoring on load the view one has just received is worth none.

It is **neither a move played nor shared state**: the version does not rise, nothing is pushed to
the stream, and `/game/state` says nothing of it — one player's view must not make the other's map
jump. `POST /view` requires a login but **no seat**: we keep the view of a logged-in spectator as
of a seated player. An anonymous visitor has nowhere to store it, and the map opens fitted as it
always has.

## Clicking, showing, moving

A click is first brought back into cube coordinates: the same matrix, **inverted**, then cube
rounding gives the hexagon aimed at. That is the only thing the browser computes — the rest is a
round trip with the server.

| Route | Response |
| --- | --- |
| `GET /moves?q=&r=&s=&piece=` | `{"origin": {…}, "piece": "key", "side": "alliance", "movement": 8, "hexagons": [{q, r, s, terrain}, …]}` |
| `POST /move` — body `{"origin": {…}, "destination": {…}, "piece": "key"}` | `{"allowed": bool, "origin": {…}, "destination": {…}, "tilt": -3.52, "piece": "key", "side": "alliance", "movement": 8}` |

Unreadable coordinates or a non-zero sum → 400; a hexagon off the map → 404; a piece unknown to the
catalogue → 400.

`/moves` stays read-only and is never blocked. `/move`, on the other hand, **refuses
(`allowed: false`, without touching the board) any move outside the movement phase of the piece's
side**: that is the only place where the turn weighs on movement.

**It is the server's board that says which piece stands on the origin square**, on which side, and
which opponents oppose their zones of control to it. The `piece` parameter — the key from
`pions.json`, `reissland-02-8-cavaleries` — serves only to question an **empty square**: the placed
piece always prevails. The browser therefore never says how many points it has, and a `movement`
slipped into the request has no effect. With no `piece` on an empty square, the flat 5 points apply
and the map is held to be free of opponents.

1. a click on a piece → `/moves` → one ghost per hexagon returned: the same image, at 50 % opacity,
   under the placed pieces, centred and tilted like them. A Reissland cavalry (8 points) covers
   more than two hundred on the plain, the Yzent ram (2 points) about twenty, a marker none — and a
   nearby opponent makes them stop at its contact;
2. a click on a ghost → `/move` → the piece lies down again on the square, askew differently — it
   is the server that drew that new angle and returns it, in `tilt` — and it **changes square on
   the server's board**: the next move's zones take account of it;
3. a click elsewhere, or again on the selected piece → the ghosts disappear.

`/move` recomputes the reach on the server side instead of believing the browser.

In the **combat phase**, the click no longer serves to move: it designates a target and then
attackers (see "Phases and combat").

## Phases and combat

The server holds the current phase in `TURN` (`tenebrae.engine.phase.Turn`) and passes it to the
template in `#phase`. The booklet chains, for each side, **movement → magic → combat**; magic is not
implemented, `Turn.advance()` skips it — it is never the current one.

| Route | Response |
| --- | --- |
| `GET /phase` | `{side, type, army, label, number, unavailable}` — to refresh the browser |
| `POST /phase/next` | the next phase, same shape; logged. 403 `La partie est terminée.` once a side has been annihilated, like `/move` and `/combat` (see "The end of a game") |
| `GET /combat/range?cq=&cr=&cs=&aq=&ar=&as=` | `{"in_range": bool, "available": bool, "message": str\|null}`; a refusal goes to the log |
| `GET /combat/target?cq=&cr=&cs=` | `{"available": bool, "message": str\|null}`; a refusal goes to the log |
| `GET /combat/ratio?cq=&cr=&cs=&a=q,r,s&a=…` | `{"ratio": [3, 1]\|null, "attack": 36, "defence": 12, "outcomes": ["DR", …]}` — the combat being composed, weighed; **nothing is logged** |
| `POST /combat` — body `{"target": {q,r,s}, "attackers": [{q,r,s}, …]}` | see below |

`GET /game/<id>` carries `#phase`; the JavaScript takes from it the toolbar's label and **what a click
does**: in the movement phase, only the active side shows its ghosts; in the combat phase,

1. a click on an **opposing** unit → the server (`/combat/target`) says whether it can still be
   taken; if so, it becomes the target, highlighted in **red**;
2. a click on one of one's **own** units → the server (`/combat/range`) says whether it is in range
   (distance ≤ 1, or ≤ its firing range) and whether it has not already attacked; if so, it joins
   the attackers, highlighted in **gold**; if not, nothing moves and the refusal is in the log;
3. "Attaquer" (visible as soon as there is a target and an attacker) → `POST /combat`;
4. "Annuler", or a new click on the target → the selection empties and the highlights fall away.

**The bar says what the attack weighs**, between the phase and the button that resolves it:

```
Phase de combat — Nains    Ratio : 3/1 (36/12) — DR,DR,DR,DR,DR;AR    [Attaquer] [Annuler]
```

`A/D` is the column of Table I the attack would be read on, `(PA/PD)` the points on either side —
the attackers' total, and the defender's strength **its terrain counted** — and then **what each
face of the die would give**, in the order the die can fall. A comma between two faces that give
the same thing, a semicolon where the outcome changes: five chances of pushing the defender back
and one of giving ground read as `DR,DR,DR,DR,DR;AR` without a figure being read. The repetition is
the information, which `5×DR` would take away.

Those six are the **faces**, not the row of Table I: on a hill the ground adds 2 to the throw, so
the same 3-1 reads `DR,DR,DR;AR,AR,AR` there (`weighed.outcomes`, `tenebrae/engine/README.md`).
That is why the figure is the server's: the terrain of a square is not in the page, and the ratio
is a rule. It is asked
for at every change of selection (`GET /combat/ratio`, one request per click as `/combat/range` is
one per click), and it is `combat.weigh` that answers — the very weighing `fight` will read, so
what is shown is what is dealt (`tenebrae/engine/README.md` § "The breakdown of the computation").
Answers can come back out of order, so each carries the number of the selection it was asked for
and a stale one is dropped.

It is there only while a target **and** at least one attacker are designated — exactly when the two
buttons are — so the bar is lengthened only while it is being read, and it never wraps: the
reference height holds (`#combat-ratio` in `map.css`). Gold, as the attackers are on the map.

It does lengthen the bar, by some forty characters, and the bar is clipped on the right where the
account button sits. A browser test therefore checks that the button is still whole with the
weighing shown; on a window narrow enough the clipping is the one that was always there.

`POST /combat` revalidates everything on the server side — phase, the target's side, each
attacker's range, and the phase register — rolls the die (`app.roll_the_die`, isolated for the
tests), resolves through `tenebrae.engine.combat.fight` and applies the result:

```json
{"resolved": true, "outcome": "DE", "message": "Combat résolu : Défenseur Éliminé",
 "eliminated": [{"q": 1, "r": 26, "s": -27, "terrain": "plaine"}], "retreats": [], "roll": 4, "die": 4,
 "ratio": [3, 1],
 "unavailable": {"attackers": [{"q": 0, "r": 26, "s": -26, "terrain": "plaine"}], "targets": []}}
```

The outcomes `AE`, `DE` and `EX` remove pieces, the retreats `AR` and `DR` move them: `eliminated`
gives **every** square cleared — the units eliminated for want of anywhere to fall back included —
and `retreats` the fall-backs themselves, `{"from": …, "to": …, "tilt": …}` per unit that gave
ground, the retreating one before the friends it pushed. The angle travels with the square, as it
does for a move: it is the server that draws it and that keeps it.

The tab that asked for the combat lays those two lists out itself — the eliminated squares cleared
**first**, since a unit falling back may be taking over the square of one that has just left the
board — while the other tabs get the whole scene again through the stream. `fallThePiecesBack` in
`static/map.js` takes each counter by the square it holds **before** any of them moves: along a
chain of pushes each square is handed to the unit behind, and a counter looked up after the first
step would be the one that has just arrived on it.

**One counter at a time, half a second apart** (`FALL_BACK_PAUSE`, the pause the AI takes between
two of its actions): a chain of pushes is three or four units changing square at once, and laid
out in one go the whole figure jumps and nothing says which unit went where. The combat is not
cleared until they have all landed, so the "Attaquer" button goes when the fall-back is over and
not before — which is also what the browser tests wait on. The other tabs are unaffected: they get
the scene from the stream, in one piece, as they always did.

`{"resolved": false, "message": …}` when it is not the combat phase, when the target is not an
opponent, when it has already been attacked, or when no attacker is valid.

### One combat per unit and per phase

The booklet limits each unit to one attack per phase, and each target to one attack per phase even
by different attackers. The count is kept **on the server side** by the module global `REGISTER`
(`tenebrae.engine.combat_register.CombatRegister`), beside `BOARD` and `TURN`:

- it is **emptied at every phase change** (`POST /phase/next`) — so between the Dwarves' combat
  phase and the Orcs', and at the next turn. Opening a game resumes it from the save; opening a new
  one empties it with the rest;
- a combat **fought** enters all its attackers and its target in it, **whatever its outcome**: a
  retreat has engaged its units all the same. The squares entered are those the units hold **after**
  the combat (`CombatResult.square_after`): a unit that has fought and then fallen back must stay
  marked, and it is no longer where it stood when the combat was declared;
- a combat **refused** (no valid attacker) enters nothing.

`unavailable` — carried by `#phase`, `GET`/`POST /phase…` and the response of `POST /combat` — gives
the **squares** of that register that still carry a piece, so that the page can grey those units out
(`.piece.unavailable`). The register designates units by their square and not by their counter: see
`tenebrae/engine/README.md` § "One combat per unit and per phase" for what that assumes.

**The log is written in two places at once** (`logs/battle_log.py`, which configures the logger
once, at import) — one line per event: a phase change, a seat taken, a unit out of range, a combat result
in French, the AI's moves.

A combat writes **two**, plus one per unit that had to give ground: the ratio computation, the
fall-backs, then the outcome. The outcome is logged last and therefore read first — the column shows
the most recent line at the top — so the player reads the headline, then the fall-backs it caused,
then the computation behind it.

```
Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4
Combat résolu : Défenseur Éliminé
```

**Each of the five outcomes names itself**, the two retreats like the three eliminations
(`COMBAT_MESSAGES`): `Combat résolu : Défenseur Recule` is followed by the `Recul :` line of the
unit that gave ground. When a retreat moved nobody — the two exemptions of
`tenebrae/engine/combat.py`, a defender in a fort or a castle and an attacker that fires — the
sentence says so rather than leaving the result unexplained:

```
Combat résolu : Défenseur Recule — mais un défenseur en fort ou en château ne recule pas
```

`Combat résolu : sans effet` is left to the combat that could **not** be resolved: an absent
target, an illegible strength.

The computation first, the outcome next — the browser's column reading the other way round from
the file, that is what puts the outcome at the top and its breakdown just below. The sentence is
composed by `describe_the_ratio` (`logs/combat_sentences.py`), from the numbers
`combat.RatioBreakdown` kept (see
`tenebrae/engine/README.md` § "The breakdown of the computation"): the engine builds no sentence,
and the application recomputes nothing. The **defender's terrain is always named**, including when
it multiplies nothing — it is what one came for; the three terms, for their part, are only spelled
out when there is a detail to spell out (a lone attacker, a neutral terrain and a die that nothing
raises are written as a single number).

- `logs/battle_log.log`, **the file**, at the repository root. It is the second place where the
  application writes to disk, after `/admin/map_fix`; the whole of `logs/` is ignored by git. It is
  **rotating**, by the standard handler and by size: at 50 KB it is set aside as
  `battle_log.log.1`, the archives shifting behind it up to three — 200 KB kept, the oldest erased
  next. `logs/rotating_log.py` holds the one thing `RotatingFileHandler` does not do, which is to
  create the directory it writes into: `logs/` is not versioned, and a fresh clone has none. Both
  logs are opened through it;
- a **bounded in-memory queue** (`InMemoryLog`, `logs/in_memory_log.py`, `LINES_KEPT` lines),
  which the browser turns into
  its column. It is a *handler* plugged onto the same logger, and not a call added beside each
  `LOG.info`: there is only one point of writing, and the column cannot say anything other than the
  file.

The lines kept leave with the game: `shared_snapshot` carries them, so the SSE stream and
`GET /game/state` do too, and `GET /game/<id>` gives them straight away in `#initial-log`. Hence the rule
the routes follow: **log before marking the move**. `mark_a_move` photographs the game, log
included; a route that logged after saving would push the browsers an account one move behind.
`tests/application/test_log.py` checks it route by route.

### `logs/movement.log` — the engine's trace, in a file of its own

`Board.moves` writes its whole computation to its module logger, `tenebrae.engine.board`: the piece
and its budget, what the walk was told to avoid, and every square it reached with its distance, its
terrain and the reason it is not offered (`tenebrae/engine/README.md` shows the lines). The engine
imports nothing from the application and chooses no path: `logs/movement_log.py` gives that logger
its file, `create_app` wiring it beside persistence and authentication.

**A second file, and not a second column.** The game log is what the player reads; a movement is
recomputed at every click, and by the AI for every unit of its turn. Those lines would drown the
column, so they never reach it — different logger, different handler, different file. Same
rotation: 50 KB, three archives.

The level is **DEBUG and it is on**: there is no switch to find. Read from an interpreter with no
application around, the logger falls back to the root's level and says nothing, and `moves` does
not even compose its lines — `logging.basicConfig(level=logging.DEBUG)` is enough to see them.

### `logs/general.log` — everything that is neither a combat nor a movement

The third log, and the one nobody reads while things go well: **the server's own trace**. The game
log is the game told to the player and shows in their column; the movement log is the engine's
walk; this one is what the server did — every request with its answer, the whole of the connection
flow, the games opened, saved and left. `logs/general_log.py` configures it at import, as the game
log configures itself, and `logs/request_trace.py` is what `create_app` hooks onto the application.

**DEBUG, and on.** The level is DEBUG unless `LOG_LEVEL` says otherwise in `.env` — a trace one
must first go and turn on is a trace one does not have on the day it is needed. `INFO` leaves the
steps out and keeps what happened (`event`), `WARNING` only what went wrong. Its file rotates like
the others, larger because its lines are: 512 KB and five archives.

Two ways of writing to it, and one rule for both — **name every variable and write its content**:

```python
note("Login: back from Discord", host=request.host, arguments=sorted(request.args.keys()))
event("New game opened", game=GAME_ID, scenario=SCENARIO_NUMBER, units=len(BOARD))
```

```
Login: back from Discord — host='127.0.0.1:5000', arguments=["code", "state"]
New game opened — game='68bb…', scenario=4, name='Le siège de Morgenstern', units=87
```

**Every request, and its answer.** `request_trace.py` is wired onto the application and not onto a
blueprint, so nothing is outside it — a page, an image, a refusal, an address matching no route.
The answer goes out **in full**, which is what one comes to this log for: what the page was given,
not what it was meant to be. Three exceptions: a **streamed** answer is named and left untouched
(`/stream` is a generator held open for the life of a tab, `send_file` hands the file over as it
is, and reading either to log it would consume the one and load the other into memory); anything
**not JSON** is described rather than copied, *unless it is a refusal* — from 400 up the body
carries the sentence that explains it; and a value longer than `LOG_VALUE_LIMIT` characters (2000
by default, `0` for no cut at all) is cut and says how long it really was. A board snapshot is some
twenty kilobytes: written whole, one afternoon of play would be the only thing left in the file.
A redirect adds where it sends, its `Location` being the whole of what it says.

**The connection, step by step.** It is the flow the game log has almost nothing to say about — one
`Login:` line — and the one that breaks for reasons outside the game: a cookie that did not come
back, a redirect URI off by a hostname, an application secret changed in the Developer Portal. Each
step is therefore written: the departure and the authorization URL, the state drawn and put in the
session, the return and what it carried, the two exchanges with Discord (`discord_client.py` writes
its calls and their answers), the account read, the session opened, the session closed. `/logout`
too, with who was there.

**The two ends of a stream, and not its middle.** A tab that opens `/stream` writes one line, and
another when it stops following, with how many were following at the time; a heartbeat every twenty
seconds per open tab would say nothing and fill the file. Between the two, `mark_a_move` writes
every move published, with the version it gives it — which is the other half of the answer to "the
other board is not refreshing".

**A secret is never written.** A field whose name says token, secret, password, authorization,
cookie, state or code is replaced by its length — `state=<hidden, 43 characters>` — at the top
level and **inside** anything logged: the `code` and the `state` of the return from Discord are
fields of `request.args`, not variables of their own. URLs go through the same scrubbing, the
`Location` of a redirect included, which is where the state travels to Discord. The MongoDB URI
loses its credentials before the start-up line is written. It is the discipline
`routes/authentication.py` already followed for the OAuth state — the keys a session carries, never
their values — applied to everything.

`tests/application/test_general_log.py` checks all three: what is written, what is never written,
and what stays elsewhere — none of these lines reaches the browser's column.

## The log column

The log reads **in a column under the card**, in the same panel (`#panel`) and of the same make as
the bar and the card: same box, same background, same font size. Nothing moves — the panel grows
downwards, the bar does not budge.

It reads **the other way round from the file**: the server gives its lines from the oldest to the
most recent, the column shows the last one at the top, where the eye returns. One therefore sees
what has just happened without doing anything, and nothing scrolls anything in the player's stead.
Beyond `max-height: 40vh` the older lines leave the column — they are read in `battle_log.log`,
the column letting the click through and therefore not scrolling (see the next section). Empty,
the column does not appear — as long as the player has not used its button (below).

## Moving the block of information

Letting the pointer through is not enough: what the panel covers cannot be *read*, and a scenario
puts its units where the panel sits. The **first button of the bar** therefore sends the whole
block to the other edge of the window — the bar, the refusal message, the card and the log column
together, `#panel.right` in `map.css` swapping `left` for `right` and aligning the boxes on the
edge they now hang from.

Two positions and nothing between them, hence a single button, which shows the edge it would go to
(`→`, then `←`). A block one could drag anywhere would hide as much map for a decision to be made
at every game; and the bar is clipped on the right, so the handle of the block comes **first** in
it, where the clipping cannot reach it.

The choice is kept in `localStorage` under `tenebrae.panelSide`, as the debug log's is: it belongs
to this browser, and to nothing else. It is not the player's stored view — `/view` keeps the scale
and the point one was manoeuvring at, which is the game seen from a pair of eyes, not where the
buttons sit — and the reads and writes are guarded, a browser that refuses its storage opening the
block where it always has.

## The face the pawns show

The counter photographed is the game's own object, and it is what the board lays. Fitted to the
window, the map is a thousand pixels wide and a counter some fifteen: what one reads there is a
small grey square, and which of two grey squares carries the cavalry is a matter of memory. The
**second button of the bar** puts a drawn icon on the units that have one, and puts the photographs
back.

### Which counter is drawn as what — `static/pawn_icons.json`

The correspondences are **a data file**, not a table in a script: giving a counter a drawing is
editing that file, and nothing else. It is a list of pairs, **one row per counter**:

```json
["reissland-01-15-infanteries.jpg",  "lorc/barbute"],
["reissland-02-8-cavaleries.jpg",    "delapouite/cavalry"],
["elfes-01-5-infanteries.jpg",       ""]
```

| The column | What it holds |
| --- | --- |
| `photograph` | the name of the counter's photograph in `game_box/pions/`, extension included |
| `icon` | the file under `static/icons/…/1x1/`, without its extension, or `""` for none |

The photograph is the one name that tells two counters apart whatever they carry — two infantries
of the same symbol wear two different helmets because they are two different counters, and nothing
has to be said about their values. The rows follow the box, faction by faction and rank by rank, as
`pions/` numbers them.

**Every counter the pages can lay has a row** — the 121 of the display catalogue, the overview
sheets apart — and one with no drawing carries an empty icon: adding a correspondence is filling a
blank in, never working out where a new row should go.

**What has no icon keeps its photograph** — a phalanx, a ram, a leader, the populace — and the
board then shows both faces at once. That is the honest answer: an icon invented for a counter the
file leaves blank would say something the box does not.

`tests/application/test_pawn_icons.py` reads that file without a browser and holds what a hand
editing it can get wrong: a photograph the box does not carry, a counter of the box with no row,
the same photograph named twice, rows out of the box's order, and above all an icon named where no
file lies — the one mistake a browser would swallow in silence.

**The colour is the army's**, and it is put on here. `static/icons/` is the game-icons.net set, and
it carries one variant only: a black drawing on a white square, which is what `000000/ffffff` says
in the path. So the file is read once and its two fills — the square, the drawing — are exchanged
for the army's two colours; what comes out is a `data:` URL an `<img>` takes as it takes any other
source. No second set of coloured files is written to disk.

### Which army is drawn in what — `static/faction_colours.json`

The colours are **a data file** as the correspondences are, and read where they are read. It is a
list of triples, one row per faction the pages can lay:

```json
["02-reissland",     "#a8cdf0", "#10243d"],
["15-demons",        "#f5c518", "#8b1111"],
["10-nains",         "",        ""]
```

| The column | What it holds |
| --- | --- |
| `faction` | the directory `pions/` numbers the army by |
| `square` | what the counter is filled with, `"#rrggbb"` |
| `drawing` | the ink the icon is drawn in, `"#rrggbb"` |

| The army | Its square | Its drawing |
| --- | --- | --- |
| Reissland, and the populace with it | clear blue | dark |
| Yzent | deep blue | pale |
| the Empire | gold | black |
| the Empire of Lynn, and the Juggernaut with it | deep blue of its own | green |
| the templars | white | red |
| the chaos | black | bright red |
| the elves | deep green | white |
| the dwarves | black | light brown |
| the orcs, and the non-humans with them | green, a shade clearer than the elves' | brown |
| the sahuagins | marine green | pale |
| the undead | white | black |
| the demons | yellow | red |
| the flyings | violet | black |
| the conjurations | white | deep purple |
| every other faction | the tone of the cardboard | dark |

**Two empty strings leave an army the tone of the cardboard** it is printed on, rather than a
colour invented for it, so that an icon never claims a colour the box does not give it. That tone
is the one colour that is not a statement about an army, which is why it stays in `static/pawns.js`
as `ANY_OTHER_ARMY` and not in the file.

**The drawing has to read on the square.** At a counter's fifteen pixels an army of one tone shows
nothing at all, so `tests/application/test_faction_colours.py` holds the two of them a hundred
points of brightness apart — and, as for the icons, that every faction of the box has a row, that
no row names one it does not carry, and that a coloured army carries both colours and not half a
pair.

### One counter painted apart — `static/pawn_colours.json`

An army's colours say whose the unit is; now and then a single counter is worth telling from the
rest of its army — a named character among the rank and file. That is a third file, and it holds
**exceptions only**:

```json
["conjurations-04-6-elementaires-de-feu.jpg",  "#f8f7f4",  "#d94f04"],
["marqueurs-02-brume-mur-de-brume.jpg",        "#cfe4f7",  "#111111"]
```

| The column | What it holds |
| --- | --- |
| `photograph` | the name of the counter's photograph, as in `pawn_icons.json` |
| `square`, `drawing` | the two colours it is painted in instead of its army's, `"#rrggbb"` |

A counter named there wins over its faction; a counter absent from it — which is nearly all of
them — takes its army's colours as before. **The file is short on purpose**: one line is added
when one counter deserves one, and there is nothing to fill in otherwise. What it holds as things
stand is what an army's colour cannot say — the four elementals apart from one another, fire in
its own orange, water in blue, earth in brown, air in a light grey; the rats, the wolves and the
bats in a darker one, and the ruined fortress and the breached wall with them; the wall of flames
in the elementals' orange and the wall of mist black on a pale sky; and the dwarves' mage told
from the dwarves. Delete a row and its counter goes back to its army's colours.

The tinted drawings are kept **under the icon and the two colours it was painted with**, not under
the army: two counters of one army painted apart must not be handed each other's drawing.

`tests/application/test_pawn_colours.py` holds the same things as the armies' file — a photograph
the box carries, no counter named twice, both colours, the drawing readable on its square — and
two of its own: that a row does not simply repeat its army's colours, which would except nothing,
and that the counter it names has an icon to paint at all.

**The drawn pawn is made to lie on the map.** A photograph carries the shading of the cardboard it
was taken from; the drawn square carries none and would read as printed on the map rather than
placed on it. Two things in `pieces.css` put it back on top: its hairline is graded — lightest
along the top edge, darkest along the bottom, which is the counter's own thickness lit from above
— and its shadow is doubled, a tight one where the cardboard meets the map and a soft one for what
it casts. Both stay small; a counter is some fifteen pixels on a fitted map, and a heavier shadow
reads as a hole in the ground. The ghosts are left flat — they mark a square a unit could go to,
not a counter lying on one — and the piece in hand still gives way to its gold ring.

A pawn is an **`<img>` in both faces, and only its source changes**: the selection, the ghosts, the
card, the click and the tests all go on reading `img.piece`, and nothing else in `map.js` knows
which face is showing. Nor is the face applied piece by piece from there: `dressThePawn` is handed
to the layer as `dress`, so that a counter born after the choice — the scene laid out again after a
move or a phase, a ghost under a selection — arrives already wearing it.

### The scenario page carries the same button

`/admin/scenarios` and `/admin/scenarios/<number>/edit` compose on the same map, where a counter is
the same small grey square, so the composing gets **the board's own button**, first in its bar and
carrying the same sign. Clicking it draws the map and the palette together, and clicking it again
puts the photographs back.

**The choice is one choice for the two pages.** Where it is kept (`localStorage`, under
`tenebrae.pawnStyle`), what the address says about it and what the button announces are all in
`static/pawns.js`, which both pages load; each page keeps only the redrawing of what it has on
screen. A face chosen while playing is therefore the face the composing opens on, and a counter
does not change appearance because one walked from the game to the editor. **`?icons=1` in the
address** still decides when it says anything — `/admin/scenarios/6/edit?icons=1` opens the battle
of Reissland with its two armies drawn — and the chooser writes the face in use into the address it
leaves for, so a link copied from there is worth copying.

There, **the whole box is tinted** rather than only what is laid: a piece taken from the palette is
dressed the moment it lands, and waiting on the server then would show its photograph first.

**The palette wears the face too**: one picks there what one lays on the map, and a list of
photographs beside a map of drawings would have to be read twice. Its labels do not change — each
entry keeps the counter's own name beside the drawing.

Both pages understand the same parameter — `?icons=1`, `?icons=0` — and, like the debug log with
`?debug=1`, **keep what they were asked**: one opens a page on a face, and it is still that face on
the next load. Said nothing, the address leaves the stored choice alone.

**The card keeps the photograph**, whichever face the board wears: the icon is a reading aid on the
map, and the card is where the counter itself is read.

The icons are read **the first time they are asked for**, and not before: a player who never leaves
the counters fetches nothing, and what has been read is kept, so the swap back and forth is free. A
set that cannot be read at all leaves the counters alone rather than empty the board.

The choice is kept in `localStorage` under `tenebrae.pawnStyle`, as the panel's edge is, and
guarded like it: it belongs to this browser, not to the player and not to the game. The button
**keeps its sign** rather than swapping it — both bars are clipped on the right, and a second glyph
is not held to the width of the first — so what it says is in `aria-pressed` and in its tooltip. On
the board it sits beside the button that moves the panel, being of the same kind; on the scenario
page it opens the bar. Both bars are `overflow: hidden`, and a test holds that neither clips it.

`tests/application/test_pawns_browser.py` holds all of it, taking the counters and the armies it
works on from the three files rather than writing down what they hold: which counter is drawn and
which keeps its photograph, every icon named read from the server, every coloured army painted with
its own row and every blank one left the cardboard, the icons landing on the
counters' own squares at the counters' own size, the ghosts and the scene laid out again wearing
the face in use, the choice surviving the reload, the address deciding and being kept, and the
scenario page — the edit page laying its units drawn, a piece taken from the palette landing drawn,
the palette itself unchanged, and the chooser carrying the face over.

## The map is always the one that takes the click

The panel is drawn over the map, at the top-left corner by default, which is where a scenario often
has units:
the log column alone is 22rem wide and up to 40vh tall. It was swallowing the clicks aimed at the
counters underneath it — one saw the piece, one clicked it, and nothing happened.

**Everything laid over the map lets the pointer through.** The rule is carried by the panel
(`pointer-events: none` on `#panel` in `map.css`), not by each box: the card, the log column and
the refusal message are click-through without saying anything, and whatever is added to the panel
tomorrow is click-through by default. Two things take the pointer back (`pointer-events: auto`),
both because they carry a button and both small: the toolbar, whose reference size is documented in
`map.css`, and the log column's reduce button — the button alone, not the column around it. The
tooltips of the two admin pages already worked this way.

What it costs: the column can no longer be scrolled with the wheel, nor its text selected — the
wheel over it zooms the map, as it does everywhere else. That is the trade accepted: the map comes
first, and the most recent line, the one that is read, is at the top of the column anyway.

`tests/application/test_log_browser.py` holds the rule: what `elementFromPoint` finds in the middle
of the column is on the board and not in the panel, the toolbar's buttons and the column's reduce
button still take their clicks, and a counter placed on a square the column covers is still
selected by a click aimed at it.

It **reduces to its button**: the column is tall and it lies over the map, and one does not always
want to read it. The "−" at the top right of the box brings it down to itself and back ("+"), the
state being the class `reduced` on `#log` alone — the lines are what a move played rewrites, not
the box, so a reduced column stays reduced while the game goes on. A reload opens it again:
nothing is stored for it, neither in the browser nor on the server.

Once the button has been used, **the box no longer hides itself**, empty or not. A server restarted
has an empty memory, and the stream hands that empty log over at the reconnection: hiding the box
then — which is what an empty log did — took the button away with it, and nothing could bring the
column back. Untouched, an empty column still does not appear.

It arrives **through the stream**, and through it alone: `refreshTheLog` is called only at start-up
and from `resumeTheGame`. A move played is published to every subscriber, including the tab that
has just played it — its own line therefore comes back to it by the same path as the other
player's, and no route's response has to carry it.

What the column **does not say**: a move played by hand. The server does not log `POST /move` — it
never has — whereas it logs the AI's. Combat, for its part, is told on both sides.

## Hovering a unit

The map opens fitted to the window, where a piece is about fifteen pixels: neither its drawing nor
its figures can be read there. **Hovering a unit fills its card**, a box that is not placed
anywhere on the map but **under the bar of zoom buttons**, in the same panel (`#panel`) and aligned
on its left edge. Neither of them moves.

- **The card's area is always there**, and empty as long as nothing is hovered: leaving a piece
  clears its contents rather than removing the box (`emptyTheCard` in `map.js`, the `empty` class
  being what says which of the two states it is in). The area is the player's, and the log column
  under it no longer travels up and down as the pointer crosses the map.
- **Empty is not blank: the box then names the square under the pointer.** Its coordinates
  (`1,26,-27`) go on `#card-extra`, the very line a hovered piece shows its own square on, so that
  the eye reads the square in the same place whether or not a unit is standing on it. Only that
  line comes back into sight — `visibility` is inherited, and `#card.empty.square #card-extra`
  overrides the hidden card around it — so the box neither grows nor moves. It is the geometry
  that answers, through the `hexagonOfPixel` a click already goes through: what is read is the
  square a click would take, and the server is asked nothing. Off the scan, where the board is
  wider than the image at the fit scale, the line goes blank rather than count hexagons that are
  not on the map.
- **Its width is fixed once and for all**, at start-up, to the widest of the cards the pieces in
  play give: `fixTheCardWidth` fills the box with each of them in turn, measures, empties it again
  and pins the largest of those widths. Nothing of it is painted, and the width is never measured
  again — a game opened on another set-up keeps it, and a name longer than any of these wraps
  inside the box rather than widening it. On a window too narrow to hold it, `max-width` keeps it
  inside the panel. The four lines a card always carries are reserved in height as well
  (`min-height` on `#card-text`), so that the empty box is the height of a filled one.
- **Hovering never queries the server.** Everything the card shows is already in the hidden field
  `#pieces`, counter values included; it is the same stance as the map-fixing page, where the 2280
  terrains go out at once.
- **The bar keeps the reference size that `map.css` documents**, and which the card can no longer
  touch. The card was at first *in* the bar, following the buttons; for that it needed a body of
  0.1875 rem — three pixels — so as not to lengthen it, which made it illegible. Moved down a
  notch, it **takes the bar's body** (0.85 rem) and a 48 px thumbnail.
- **The bar's size ratio is not to be modified.** `zoom.css` fixes it — body 0.85 rem, padding
  0.4/0.7 rem, buttons 0.15/0.6 rem, anchored 0.6 rem from the corner — and `map.css` documents it
  at the head of its section and takes care not to redefine it. `#panel` takes the anchoring over
  identically and the bar inside it simply becomes `position: static`.
- **One element per line**: the name, then the side and the square, then the symbol, then the six
  numeric values, then the remarks — stacked beside the thumbnail, which stays on the left. The six
  values fit on one line and **wrap on a narrow window**: the card then grows downwards, which it
  could not afford inside the bar.
- **The thumbnail serves to recognise the piece, not to read it**: its figures are spelled out
  beside it.
- **What the counter does not carry is rendered as a dash**, never as a zero: a piece with no fire
  does not fire, it does not fire "at 0". The remarks, for their part, are not a counter value but
  what the photograph leaves open — an illegible name, an incomplete framing: **their mention
  appears only if there is something to say**.
- - "Mouvement" is the budget the engine uses — the ground movement, failing that the flight one, 0
  for a marker (see `tenebrae/engine/README.md`) — and not the raw value `pions.json` sometimes
  leaves empty.
- **The panel is outside `#board`**: the zoom does not reach it, the card keeps its size at any
  scale. And it is **fixed in place**, out of the flow: nothing moves from one piece to another,
  and the map occupies the window as if it did not exist. It is fixed to one of the **two edges**
  of the window, the bar's first button moving it from one to the other (see "Moving the block of
  information"): the card hangs from the same edge as the bar, above the log, wherever the block
  is.
- **The card lets clicks through** (`pointer-events: none`) where the buttons take them: without
  which it would make the strip of map it covers unplayable.
- **The ghosts have no card**: they repeat the already selected unit, and covering the map with
  hovers all saying the same thing would teach nothing.

## Fixing the map — `/admin/map_fix`

Implementing movement showed that the transcribed map contains errors, and they only show to the
eye. This page displays `map.jpg`, states the terrain under the pointer, and fixes it with a click.

**The whole map goes out to the browser at once**, in the hidden fields — 2280 hexagons, some fifty
kilobytes. Hovering therefore asks the server nothing: it reads from the object received. Only
choosing a terrain makes a round trip.

| Hidden field | Contents |
| --- | --- |
| `#hexagons` | `"q,r,s" → terrain` for the 2280 hexagons, the main terrain alone |
| `#fixes` | the fixes already recorded, read from `map_fix.json` |
| `#applied` | those the engine loaded at start-up — a difference calls for a restart |
| `#terrains` | the 16 terrains, in the priority order of `tenebrae/game_box/map.md` |
| `#grid` | the same alignment as the board, without `piece_size` |

- **Zoom**: the same as the board's (see above) — the map opens fitted to the window, where a
  hexagon is 25 px: one does not judge a wood at that size.
- **Hovering**: the hexagon aimed at is highlighted and a box gives `q,r,s — terrain`, followed by
  `→ fixed terrain` if the square has already been taken up.
- **Clicking**: a dialog gives the map's terrain and sixteen buttons. Choosing the one the map
  already carries **removes** the fix — that is the way back.
- The fixed squares stay marked in red on the map, and the toolbar counts them.

| Route | Response |
| --- | --- |
| `GET /admin/map_fix` | the page |
| `POST /admin/map_fix` — body `{q, r, s, terrain}` | `{"key", "terrain", "original", "fixed": bool}` |

An unknown terrain or unreadable coordinates → 400; a hexagon off the map → 404.

Every fix is written straight away into **`tenebrae/game_box/map_fix.json`**, which contains only
the squares taken up:

```json
{
"29,5,-34": "colline"
}
```

`carte.json` and `carte_details.json` are **never touched**: they are produced by
`tenebrae/game_box/extract_map.py` and must stay that way (see `tenebrae/game_box/map.md`).

**The engine reads that file and lays it over the transcription**, once, at start-up (see
`tenebrae/engine/README.md`): the board of `/` and the moves are computed on the fixed map. Since
the overlay happens only at start-up, the toolbar announces "redémarrer le serveur pour jouer
dessus" as soon as the recorded fixes differ from those the engine loaded.

This page, for its part, always works on the **transcribed** map: `#hexagons` carries what the scan
gave, the fixes come separately, and the "original" terrain in the dialog stays the scan's. Without
that, after a restart, "Rétablir" would offer to reset the fix itself.

**The route is reserved** to the Discord accounts listed in `ADMIN_DISCORD_IDS` (see
`.env.example`). An empty list admits nobody, and the refusal says so: a security variable whose
absence would open everything would be a trap. A visitor with no account gets 401, an ordinary
player 403.

## Composing and editing a scenario — `/admin/scenarios`

The booklet's scenarios are fixed by hand, one JSON at a time (see `tenebrae/scenarios/README.md`).
This page composes one on the map instead: the box's pieces in a **palette** at the right of the
window, the map in the middle, and a click to lay each counter. What it saves is a **new file in
`tenebrae/scenarios/`**, in the very format the engine reads. The same page **edits** a scenario
on file (`/admin/scenarios/<number>/edit`): its pieces are on the map when the page opens, and
saving rewrites its file. That page is the only place where the application writes there.

Like the map-fixing page, it receives everything at once in hidden fields and asks the server
nothing until saving:

| Hidden field | Contents |
| --- | --- |
| `#pieces` | the display catalogue — the 121 photographs showing a single counter — in the shape of the board's placed units: `image`, `name`, `side`, `faction` and the counter's values |
| `#grid` | the same alignment as the board, `piece_size` included |
| `#hexagons` | `"q,r,s" → terrain` for the 2280 hexagons of the **fixed** map — the one the game is played on, where the map-fixing page works on the scan |
| `#forbidden` | the squares no unit can occupy: lakes, rivers, the rift (`UNINHABITABLE` in the engine) |
| `#scenarios` | the scenarios on file — `number`, `name`, `file`, `enabled` —, for the chooser in the toolbar |
| `#scenario` | when editing, the scenario opened: `number`, `name`, `max_turns`, `enabled`, `placement`; empty when composing |

- **The palette**, by faction with its side, scrolls on its own. A click takes a piece **in hand**
  — the toolbar says which — and every click on a free square lays it down again: fifteen orc
  infantry are fifteen clicks. A second click on the same palette piece puts it back.
- **A placed piece**, clicked, comes in hand in its turn: the next click on a free square moves it,
  "Retirer" — or the Delete key — removes it, a click on the piece itself puts it back. Escape
  empties the hand.
- **Hovering** highlights the hexagon and states `q,r,s — terrain`, and the occupant if any; a
  forbidden square is ringed in red and refuses the piece with a message.
- **The board's button, first in the bar**, turns the counters over to their drawn face — the map
  and the palette together — and `?icons=1` in the address asks for it too. The choice is the
  board's own, kept in the same place (see "The face the pawns show"), and the chooser writes it
  into the address it leaves for.
- **The counters are laid by the board's own code**: `static/pieces.js` and `pieces.css`, shared by
  both pages, centre the image on the hexagon and tilt it (see "The server's board"). Here the tilt
  is drawn by the page: the pieces are not yet in a game, and the file carries none.
- **The zoom** is the board's; the map fits into the frame beside the palette, not into the window.
- **"Enregistrer"** opens a dialog asking for the **title** (required) and the **number of turns**
  (empty for an undetermined one, as the booklet says of scenario no. 5), kept from one save to the
  next. The scenario's number is not asked for: it is the next free one after the booklet's five
  and the files present, so that a booklet scenario fixed later never collides with one composed
  here. Each save on `/admin/scenarios` is a new file.
- **The chooser**, in the toolbar, lists the scenarios on file — "nouveau scénario", then
  `n° 4 — La guerre des nains`, … — and opens the one picked on `/admin/scenarios/<number>/edit`:
  the same page, the file's pieces already laid, its title and turns already in the dialog, the
  title and the dialog saying which scenario is being modified. A piece the palette does not offer
  cannot be laid, and the page says so: a save would drop it. Saving there **rewrites the file**:
  the number stays, the title, the turns and the placement are replaced, and a new title renames
  the file.

| Route | Response |
| --- | --- |
| `GET /admin/scenarios` | the page, empty |
| `POST /admin/scenarios` — body `{name, max_turns, placement}` | `{"saved": true, "number", "name", "file", "units"}` — a new file |
| `GET /admin/scenarios/<number>/edit` | the page, the scenario's pieces on the map; 404 with a French `message` for a number no file has |
| `POST /admin/scenarios/<number>/edit` — the same body | the same answer — the scenario's file rewritten; 404 likewise |

`placement` is `"q,r,s" → piece key`, the engine's format. The route reads the request — a name, a
positive integer or `null` for the turns, every square on the map and fit to be occupied, every
piece one the palette offers — and the engine composes the file's values from it
(`tenebrae.engine.scenario.compose`): the `armees` derived from the pieces placed, alliance first,
named after their factions ("Nains", "Elfes et Nains"); the neutral pieces — spellcasters,
conjurations, markers — placed but belonging to no army. A request no scenario can be composed from
is refused with 400 and a French `message`, read in the dialog; a placement with no unit of a side
among them, since a turn needs a side to play it. An update is checked the same way, and a refused
one leaves the file as it was.

An update goes through `tenebrae.engine.scenario.recompose`: the armies are derived again from the
pieces placed, and what an army carried that the map cannot give — the instruction, the anchor,
the magic potential, the spellcaster, written by hand into a booklet scenario — is kept for every
side still present. The `source` stays what it was. The old file is removed once the new one is
written when the title changes, since two files with one number would be read as one.

What is saved is a set-up and nothing more: the turn limit is written in the file
(`nombre_de_tours`, read as `Scenario.max_turns`) without the engine yet ending a game on it. The
file's `enabled` is carried through a save unchanged — it is written by hand, not from this page —
and the chooser in the toolbar marks a disabled scenario `(désactivé)` rather than hiding it,
since re-enabling one means opening its file (see `tenebrae/scenarios/README.md`).

**The route is reserved** to the same accounts as the map-fixing page.

## Two players, two sides

A game brings together **two Discord accounts, one per side**: one holds the Dwarves (the
Alliance), the other the Orcs (the Darkness). The server refuses a move played by whoever's turn it
is not — that is the `active_side_required` decorator — and the browser turns off in advance the
buttons a refusal would await.

The table is a separate register, `tenebrae/engine/models/seats.py` — it is part of the game, not of
the web — held beside the board and the turn in the module global `SEATS`. It knows only Discord
identifiers, and defends a single invariant: **a side has at most one occupant**, and a seat is not
taken from whoever occupies it. The rule that a player holds only one side is elsewhere, in the
`POST /game/seat` route — that separation is what lets the test suite seat a single player on both
sides to play a game by itself.

| Route | Method | What it does | Who may |
| --- | --- | --- | --- |
| `/game/seat` | POST | sit down at the side in the body `{side}` | any logged-in account |
| `/game/seat/leave` | POST | give up one's seat; the game does not budge | any logged-in account |
| `/game/state` | GET | where the game stands — the stream's fallback, see below | everyone |
| `/stream` | GET | the event stream: the game pushed when it changes | everyone |

What is **public**: `/`, `/game`, `/game/<id>`, the map, the piece images, `/moves`, `/phase`,
`/combat/range`, `/combat/target`, `/game/scenarios`, `/game/state` and `/stream`. A passing visitor
therefore sees the list, opens a game, follows it live, and can consult what would be reachable, as
before. What requires **a seat at the active side**: `/move`, `/combat`, `/phase/next`.

`POST /game/new` requires **an account and nothing more**. It used to require a seat, and that made
sense while a game was started from the board by someone already at the table; it is started from
the list now, before the game exists to sit at, so the side comes from the form instead — and the
seats are **not** kept. A new game's table is its own: carrying over the table of the game the
process happened to be on would seat two strangers at a game nobody offered them (see "The list of
games").

The refusals return **401** when nobody is logged in, **403** when somebody is but does not hold
what is needed, with a `message` in French that the page displays under the toolbar. The rest of
the failures keep the silence they had, their refusals going to the log.

Logging out does not give up one's seat: one comes back to sit in it.

### The end of a game

**A combat that leaves a side without a single unit closes the game.** That is the booklet's first
victory condition — "to crush the opponent by annihilating their troops" — and the only one
transcribed; the engine counts (`tenebrae/engine/victory.py`), the application decides. The check
runs where units are removed, a combat resolved by `/combat` and the AI's turn, **before the move
is marked**, so that the browsers receive the sentence with the position it speaks of.

Two module globals hold it, beside `VERSION`: `GAME_IS_OVER`, and `WINNER` — the side left
standing, `None` where the last units of both fell in the same combat, which an exchange can do.
Both go into the saved game (`over`, `winner`, read back with `.get`: a game saved before they
existed resumes as one still being played), so a browser coming back to a won game finds it won.

**Nothing is played on a game that is over.** `while_the_game_lasts` guards the three routes that
play — `/move`, `/combat`, `/phase/next` — and answers 403 with `La partie est terminée.`. The way
out is a new game, opened from the list; the guard is not in `POST /game/new`'s way. A finished game
stays in the list, saying who won.

**The board says so where it says the phase.** A game that is over has no phase worth showing, so
`current_phase` puts the end in `label` — `Partie terminée — Nains l'emporte`, or
`… — personne ne l'emporte` — and adds `over` and `winner`. `map.js` shows that label in gold and
disables the two buttons that play, rather than let the player find out by being refused.

**A board is not a game.** `A_GAME_IS_ON` says whether the server has a game of its own on the
board — a set-up laid out, or a saved game resumed. A board somebody has placed counters on by
hand is a board: nothing on it is won, whoever is left standing. In production every board comes
from a set-up, so the flag is only ever down in the tests, which desert the map to look at one
rule on two counters (`put_the_game_away`, called by the `deserted_map` fixture).

`tests/application/test_victory.py` holds all of it, `tests/engine/test_victory.py` the counting.

### Playing against the AI

The second account can be a machine. The **"Jouer contre l'IA"** tick on the list's new-game form
sends `POST /game/new` with `{"against_ai": true}`, the number the scenario chooser shows and the
side the side chooser shows: the set-up is laid out, the creator is seated at the side they asked
for, and **every other side of that scenario goes to the AI**.

The side is asked for because there is no longer a seat to read it off. The button used to sit in
the board's table dialog, where the requester was already seated and the AI took what was left; a
game is opened from the list now, by someone holding nothing, so the form asks. What went with that
change: the two refusals those seats justified — "Aucun camp à confier à l'IA" and "Ce camp est
déjà tenu" — have nothing left to refuse, since a new game's table is empty until this request
fills it. A scenario no longer on offer is still refused, with 409, and before anything moves: the
request is read in full first.

The AI has neither a session nor a Discord account: it occupies its seat under the `ai.AI_PLAYER`
sentinel (`"ia"`, which no Discord identifier — strings of digits — can carry), which travels in
the seats dict like any other identifier — nothing more to save, nothing more to resume — and which
`the_table()` displays under the name "IA". A human cannot sit there — the seat is occupied — and
`active_side_required` can never pair a session with it.

Its turn is played **on the server side, within the request that hands it play**:
`let_the_ai_play()`, called at the end of `POST /phase/next` — and at the creation of the game, in
case the scenario opens on its side. The strategy lives in the engine (`tenebrae/engine/ai.py`, see
`tenebrae/engine/README.md`); the application only passes it the die (`roll_the_die`), saves and
logs. A single save at the end of the turn, so a save never lands on a phase held by the AI —
opening a game never has to make it play.

**Its turn is pushed as it is played, not when it is over.** The whole turn happens inside one
request, and one push at the end would land the board the AI left behind on every browser at once,
counters teleporting to where they ended up. So `let_the_ai_play` hands the engine two watchers
(`moving`, `fighting` — see `tenebrae/engine/README.md`): each move and each combat is logged and
marked the moment it is played, and **`PAUSE_BETWEEN_AI_ACTIONS`** — half a second — is waited
between two. The stream then delivers the turn action by action, as it would a human opponent's.

Three consequences worth knowing. `mark_a_move` gains callers beyond the two the rule named — the
AI's watchers publish without saving, the save still coming once at the end. The request that
handed play over **is held for the length of the AI's turn**: half a second per action is what
watching it costs. And the tests set the pause to nothing, the way they fix the die
(`current_game.PAUSE_BETWEEN_AI_ACTIONS`, an autouse fixture in `tests/application/conftest.py`);
one test puts a fiftieth of a second back to hold that the pause is taken **between** two actions
and not before the first.

### Following the opponent's game

The page holds an **open stream** to the server — `GET /stream`, Server-Sent Events — and never
asks it for anything again. It is the server that writes, at the moment the game changes, and to
everyone watching it at once. The browser therefore sees the opponent's move within a few
milliseconds, where the previous polling took up to three seconds and asked twenty useless
questions for one useful answer.

The channel is **one-way**, server → browser, and it stays so: everything the player does leaves as
a `POST` on the ordinary routes, exactly as before. The stream only serves to carry a move's result
to the **others**.

**The mechanism, in three pieces** (`tenebrae/application/stream.py`):

- one **subscriber** per open stream, that is, per tab watching the game;
- a **one-slot box** per subscriber — a `Queue(maxsize=1)` whose content is *replaced* rather than
  stacked. Nobody needs a stale state: a request that raises the version three times (that is the
  case of `/game/new`, which lays the scenario out again then lets the AI play) wakes the
  subscriber only once, and on the last state;
- `mark_a_move`, in `current_game.py`, which publishes. **It is the only point of publication**,
  and it is also the compulsory passage of everything that moves: no move can be played without
  the open streams learning of it.

**Why the snapshot is taken at the moment of publishing.** The board, the turn and the combat
register are module globals, and nothing protects them. If a stream's generator went and re-read
them on waking, it would read them from the thread serving *its* stream, while another thread might
be moving a piece. So we leave it nothing to re-read: the snapshot is taken once, in the thread
that has just written, and it is the snapshot that travels.

**What is composed per recipient.** Almost everything is shared — the pieces, the phase, the log —
but not the **table**: it tells each of them whether they are logged in, under what nickname, and
which sides they hold. It is the only part of the message the stream composes at the moment of
writing, for a player it re-reads from the repository each time (never cached: leaving one's seat
shows at the next message).

**The version number serves twice.** It rises by one at every move played, and it is also the
stream's **event identifier** — the one the browser sends back in `Last-Event-ID` when it
reconnects. The server then knows whether there is catching up to do: if the number matches, it
opens the stream on a plain comment; otherwise it sends the whole game. That is what makes a
restarted server, a cut network or a woken laptop catch up all by themselves, without a line of
code for it.

**A heartbeat** — an SSE comment, `: heartbeat` — crosses the connection every 20 seconds. Without
it, a firewall, a proxy or the browser would end up closing a connection it believes dead.

**A closed tab frees its place.** The page closes its stream on `beforeunload` and `pagehide`, and
the subscription is in any case removed as soon as the generator is closed, whatever happens.
Without that, every closed page would leave a box into which the server would go on depositing
every move played.

**The fallback is kept.** If the `EventSource` fails five times in a row — an intermediary cutting
SSE, a corporate proxy — the page closes the stream and falls back on the old polling of
`GET /game/state?version=N`, every three seconds. That route is still served for this: the game
slows down, it does not break.

Laying the scene out again must have **no visible effect** on what has not moved: that is why each
piece's tilt travels with it (see "Placing the pieces"). It comes from the server's board, which
keeps it from one message to the next; only a moved piece lies down again. For the same reason, the
"localiser" button's marker is kept by its **square** and not by its image: the scene laid out
again destroys every image and recreates them, and the button would go off at every move.

What all this will require the day it goes into production — a WSGI server, Nginx, timeouts, and
why a single worker — is in `DEPLOYMENT.md`, at the root. The places in the code concerned carry
the `TODO: PRODUCTION` marker.

### One game per process, several URLs

There is **one board, one turn and one table per process**, and that has not changed: `current_game`
holds them in module globals, and two tabs on the same game share them, which suits — both players
play the same game. What has changed is that there are now several games in base and each has an
address, so `GET /game/<id>` is **not a reading**: it takes the process onto that game, and takes it
off the one it was on. Anybody may do it — the board is public, as it always was.

A tab left on the game just left would otherwise go on showing a board that is no longer its own,
and the version says nothing about it: it counts the moves of the **process**, not of one game, so
even the `changed: false` answer of `/game/state` would be a lie. Hence:

- `shared_snapshot()` carries `game`, so it rides every SSE message, and `/game/state` carries it in
  **both** answers, the unchanged one included;
- `map.html` carries the game it was served for in `#game`, and `map.js` compares
  (`checkTheGame`): on a mismatch it closes the stream, stops the polling, stops applying anything,
  and shows `#displaced` — *"Une autre partie a été ouverte sur ce serveur…"*. That box does not
  fade like `#message`: what it says does not stop being true.

**It tells, it does not fight.** Reloading onto its own game would take the table back from whoever
has just opened theirs, and the two tabs would pull at it forever. So the displaced tab stops, and
the way back is the list.

Playing several games at once is a different feature and not this one: it means one board, one turn
and one table **per game**, and a broadcaster per game with them.

## The list of games — `/`

The first page one sees, and the first in the application with **no map on it**: no `zoom.css`, no
`pieces.css`, no `geometry.js`. It lists what `parties` holds — one card per game, most recently
played first — and carries the form that opens one more.

**It creates nothing.** As long as `/` was the map it laid a set-up out on an empty base, so every
arrival, an anonymous visitor's included, left a game behind them. A listing that did that would
fill the base with games nobody plays, so the creating stays where it is asked for: `GET /game`,
which wants a game to play, and `POST /game/new`, which wants a new one.

| Hidden field | Contents |
| --- | --- |
| `#games` | one entry per saved game: `id`, `scenario` and `scenario_name`, `turn`, `phase`, `army`, `units`, `over` and `end`, `sides` (each with its `army`, its `occupant` and whether it is `mine`), `mine`, and `played_at` |
| `#scenarios` | what `/game/scenarios` serves — the set-ups a new game may be opened on, each with its `armies`, which is what the side chooser is filled from |
| `#visitor` | who is looking: `connected`, `nickname`, `avatar`, `administrator`. **Not** the table: that is composed from the set-up being played, which is the business of a page showing a game and not of one listing them |

**No sentence is composed here.** The phase reads through `LABELS` (`tenebrae/engine/phase.py`), the
table `Turn.label` itself uses, and a finished game through `label_the_end`
(`logs/combat_sentences.py`), the sentence the board's own toolbar shows. `TURN` is never touched —
it holds the game in play, not the ones being listed — so the army names come from each card's
scenario, read from its file.

The scenarios are read here through `available_scenarios()` and not `enabled_scenarios()`: a game
under way on a set-up withdrawn since must still be able to say what it is being played on. A game
whose **file has gone altogether** is listed, greyed, with its number and no name, and it is not a
link: it cannot be laid out, and a link leading to a refusal is worse than none.

A card the visitor holds a side in carries `mine`, styled as the board's own table styles the side
one holds (`#4a3d30` on a pale border) — the eye already reads that pair as "this one is mine".

**The form**: the set-up, the side one takes, `Jouer contre l'IA`, and `Commencer`, which posts
`/game/new` and follows the `url` it gets back. The list is laid **in the page** and not fetched,
unlike the chooser that used to sit in the board's dialog: that dialog could be hours old, this page
was served a moment ago. The guard is the one that always did the work — `POST /game/new` reads the
files again and refuses a set-up disabled since, and the refusal is shown under the form.

**One connection control, one place.** The header's right-hand corner carries `Se connecter` for a
visitor (`#new-game-login`) and, for a player, their avatar, their nickname and `Se déconnecter`
(`#account-logout`) — one of the two, never both. The buttons therefore carry a `[hidden]` guard in
`home.css`: `hidden` is a rule of the lowest specificity there is, and the `display: inline-block`
of `button, .button` used to leave the way in on screen for a player already connected.

An **anonymous visitor** sees the list and can open any game to watch it; in place of the form they
get the line `Connectez-vous pour créer une partie`, rather than controls whose every use would be
refused. The way in itself is not repeated there: it is up in the header, where the way out is.

The board carries the way back: **`Les parties`**, first in the table dialog.

## Logging in through Discord

The OAuth2 flow comes in four steps, and everything that speaks to Discord is in
`discord_client.py`:

1. `GET /login` draws a `state` (`Connection.set_oauth_state`), puts it in the session and
   redirects to Discord;
2. the player authorises, Discord sends them back to `GET /login/return` with a code and the
   `state`;
3. the route **removes** the `state` from the session (`Connection.take_oauth_state`) and compares
   it with `compare_digest` — a replayed return therefore finds nothing left to compare against —
   then exchanges the code for a token and reads `/users/@me`;
4. `Connection.open` creates or updates the player in base and opens the session, and we come back
   to the board.

**When it breaks, the log says why.** From the start, `GET /login` compares the host requested with
that of `DISCORD_REDIRECT_URI` and, if they differ — the map opened on `localhost:5000` when the
URI says `127.0.0.1:5000` — writes that the cookie set here will not come back: the browser holds
those two hosts to be two sites. On the return, a `state` that does not pass returns 400, and the
log's "Login refused" line distinguishes the three cases, which are not cured the same way:
*absent from the session* — the cookie set on the way out did not come back: a different host
between the outward and return trips (`localhost` against `127.0.0.1` in `DISCORD_REDIRECT_URI`), a
`Secure` cookie over http, a session emptied meanwhile —, *absent from the request*, or *different
from the session's* (a replayed or forged return). The line carries the host requested and the
state of the session cookie — absent; present but **unreadable**, that is signed by another
`SECRET_KEY` (the key changed in `.env`, or two servers answer on the same host); or readable, with
the list of keys the session still carries, which says where that session came from when another
request rewrote the cookie between the outward and return trips. The keys alone, never the values
nor the states themselves. The two exchanges with Discord, for their part, are **not caught**: a
`DiscordError` comes back up as it is, with the status and the body of the response — that is where
Discord writes `invalid_grant` or `invalid_client` — and Flask traces its stack. A mute 502 saying
"Discord did not answer" left nothing to read.

`POST /logout` closes the session. It is a POST like everything that changes something here: a link
or an image from another site must not be able to log the player out.

**What the session carries** — and it is `models/connection.py` that decides, alone: the Discord
identifier, and the `state` for the length of one round trip. Nothing else, and above all not the
access token — Flask's session cookie is *signed, not encrypted*, and its contents can be read by
whoever holds it. The stored key names stay French (`joueur`, `etat_oauth`): they are already in
browsers' cookies. The nickname and the avatar are re-read from the repository at every request,
which keeps them up to date as soon as they change at Discord.

The cookie is `HttpOnly`, `SameSite=Lax` and `Secure` behind HTTPS (`SECURE_COOKIE=yes`). **`Lax`
and not `Strict`**: the return from Discord is a top-level navigation coming from another site, and
`Strict` would withhold the cookie — the session would look empty, the `state` would be nowhere to
be found, and the flow could never complete.

**The cookie is only rewritten by responses that modify the session** — opening, closing, setting
or taking back the `state` — and not at every response as Flask does by default as soon as the
session is permanent (`SESSION_REFRESH_EACH_REQUEST = False`). This is a bug lived through: a
request that left with the old session before `/login` — a fallback poll, a stream reconnection
from another tab — answered afterwards, and its cookie, without the `state`, overwrote the one
`/login` had just set; the return from Discord then found nothing left to compare against. The log
put it thus: "authentication state absent from the session (host localhost, session cookie
readable, session carrying _permanent, joueur)". What
is lost by it fits in one line: the cookie's expiry (31 days) runs from the login and not from the
last visit.

The scope requested is `identify` alone. Not `email`: the game would do nothing with it, and one
scope fewer is one consent fewer to ask for. The `email` field of `tenebrae.engine.models.player`
waits, just in case.

**No dependency was added for any of this**, and it is the same stance as for `extensions.py`,
which rewrote Flask-MongoEngine's interface rather than install a dead extension:
`flask.session` is enough for the session, `urllib.request` for the two HTTP calls.

### The seam that makes the flow testable

`create_app` hooks an **identity client** onto the application's extensions, exactly as it hooks
the repository: `DiscordClient` in play, `FakeDiscordClient` under the test configuration. The fake
one short-circuits nothing — it returns an authorization URL pointing at **our own return route**.
The browser follows it, comes back with a code and a state, and the real code then runs from
beginning to end. That is what makes it possible to exercise logging in inside Chromium without a
single packet leaving for discord.com.

`AUTHENTICATION` is **not** read from the environment, deliberately: a `.env` variable that unplugs
authentication is an open door that a typo is enough to leave gaping. Only `TestingConfig` sets
"fake".

### Setting up a Discord application

1. Open the [Developer Portal](https://discord.com/developers/applications) and **New
   Application**; give it a name.
2. **OAuth2** tab: note the **Client ID**, then **Reset Secret** to obtain the **Client Secret**
   (it is never shown again — copy it straight away).
3. Still in **OAuth2**, section **Redirects**, add the return URI **to the character**:
   `http://127.0.0.1:5000/login/return` in development. Discord compares it exactly: `localhost` is
   not `127.0.0.1` there, and one trailing `/` too many is enough to make the exchange fail.
4. Carry the three values over into `.env` (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`,
   `DISCORD_REDIRECT_URI`), and add a `SECRET_KEY`.
5. To allow oneself to fix the map: enable developer mode in Discord (Settings › Advanced), copy
   one's own identifier from one's profile, and put it in `ADMIN_DISCORD_IDS`.

The portal asks for **no scope to tick**: it is claimed by the authorization URL, and it is
`identify`.

## The set-up

The server no longer draws anything at random: it reads a set-up from `tenebrae/scenarios/` through
`tenebrae.engine.scenario` — no. 4 at start-up (`DEFAULT_SCENARIO`) — and lays it out when a game is
opened on it (`open_a_new_game`).

**Which scenario is played is part of the state**: `current_game.SCENARIO` and `SCENARIO_NUMBER` are
rebound by `switch_to_the_scenario()` when a new game is opened on another set-up, and opening a
saved game puts the server back on the scenario that game names (`resume_the_scenario()`). They are
therefore read through the module — `current_game.SCENARIO` — and never imported by name. The turn
follows: it is set up again on the new scenario's sides and army names.

**Choosing it.** The chooser is on the list of games (`/`), filled from the page it was served
with; `POST /game/new` reads the files again and refuses a number that is not among them (409, a
French `message` under the form). A scenario is offered unless its file carries `"enabled": false`,
written there by hand — see `tenebrae/scenarios/README.md`. Disabling one withdraws it from the
**new** games only: a game under way on it is resumed as it stood, and named as it stands on its
card.

`GET /game/scenarios` keeps its place though no page fetches it any more: it is the list of what a
new game may be opened on, as the server holds it now, and `tests/application/test_scenario_choice.py`
exercises it.

- - **The placement comes from the file, not from the server.**
  `tenebrae/scenarios/scenario-04-la-guerre-des-nains.json` gives "square → piece key"; the
  application adds to it only what the display needs — the image, the readable name, the movement
  and the side, all taken from the catalogue in `tenebrae/game_box/pions/`. The detail of the
  deployment and its caveats are in `tenebrae/scenarios/README.md`.
- **The starting position is reproducible.** A fresh game always puts the 48 units back on the same
  squares: that is what makes it possible to exercise a move twice in a row and get the same
  result. `POST /game/new` opens one.
- - **The movement is the counter's**: each piece carries its points, read off the photograph and
  stored in `tenebrae/game_box/pions/pions.json`. The **strength** now serves in combat; fire and
  range serve only for an archer's engagement distance.
- - **The side comes from the faction** (see `tenebrae/engine/README.md`): it decides who hinders
  whom. Here the dwarves are the alliance and the orcs the darkness, and the two masses face each
  other 3 squares apart.
- The overviews are still not served: the 4 photographs in `21-vues-d-ensemble/` and the 2 record
  sheets in `19-magiciens/` do not show a single counter, and `/pieces/…` refuses them. The
  scenario does not name them either.
- A square takes only one piece. What the board keeps from one reload to the next depends on
  persistence (see above).

## The debug log — `static/debug.js`

The board is played in a browser, and what goes wrong there leaves no trace: a piece that does not
move, a card that stays open, a stream that no longer delivers. `static/debug.js` gives the other
scripts a console log one can follow a whole game with, and **nobody sees it unless they ask for
it**: turned off, not a line is written and not a byte more is read from the network.

The four templates load it **first**, before every other script, and it hangs everything off
`window.tenebraeDebug`. Each file takes a logger of its own at load — `const trace =
debugScope("map.js")` — and speaks through it.

| Turning it on | |
| --- | --- |
| `/game?debug=1` | in the address bar; the choice is remembered in `localStorage` for the next loads. `/game` carries the query string through its redirect for exactly this — swallowed there, the parameter would say nothing |
| `/game?debug=0` | turns it off again, and forgets it |
| `tenebraeDebug.on()`, `.off()` | from the console, without reloading |
| `window.TENEBRAE_DEBUG = true` | set before the script, from a page that wants it on |
| `tenebraeDebug.level("info")` | the minimum level shown; "trace", "info", "warn", "error" |

A line reads `14:02:31.145 map.js · click on the board`, and what goes with it — a square, a
payload, a status — goes as a **second argument**, which the console lets one open and walk
through rather than as a string one has to read.

"trace" carries what happens by the hundred — the pointer over the map, a scroll, a wheel turn, a
hexagon converted into coordinates —, "info" what a game is made of — the clicks, the requests, the
selection, the phase, the stream —, "warn" everything refused, and "error" what breaks. Following a
game without the noise of the pointer is `tenebraeDebug.level("info")`.

The round trips with the server go through `trace.fetch(url, options)`, which writes the request
with its payload, then the status, the time it took and the answer's body. It reads a **clone** of
the answer, so the caller still reads the original as it always did, and it does not await that
reading: the answer comes back at the moment it would have come back without the log. Turned off,
`trace.fetch` **is** `fetch` — no clone, no line — and in both cases it returns what `fetch`
returns and throws what `fetch` throws, the caller's `catch` deciding as before.

Nothing else in the application knows this file exists: no route serves it anything, no
configuration turns it on, and the server is never told. It is the browser's own log, and it is
read in the browser — the game's log, the one that goes to `logs/battle_log.log` and to the page's
column, is another thing entirely (see "The log column").

## Tests

From the **repository root**, so as to cover the engine too:

```
make test
```

`make test` brings up a test MongoDB in a container itself — port 27018, database `tenebrae_test`,
separate from the game's — waits for it to answer, then runs the whole suite pointing it at it.
Every test runs against it — there is no base-less mode — and `conftest.py` empties it before each
test. `make mongo-stop` removes the container, which otherwise stays up from one series to the
next. `ARGS` passes arguments to pytest: `make test ARGS="-k persistence -v"`.

The suite also runs the two static checks, flake8 (`.flake8`) and mypy (`[tool.mypy]` in
`pyproject.toml`), as tests of their own (`tests/test_static_checks.py`): a line too long or a
type that does not add up fails it with the tool's report. `make lint` runs the two alone.

`make coverage` runs that same suite and reports what it covers of `tenebrae/` — the missing lines
in the terminal, the source coloured in `htmlcov/index.html`. Chromium is measured with the rest:
the browser tests reach the routes through the page that serves them, and dropping them can only
lower the figure. Adding `ARGS="--ignore-glob=*browser*"` drops Chromium, which turns the minutes
into seconds and under-estimates the application — that pass says where to look, not where one
stands.

**Nothing is checked by hand**: no server launched to go and look, no `curl`. What we want to
exercise is written as a test, and what shows in a page is exercised in Chromium through Playwright.

`tests/application/test_debug_browser.py` holds the browser's console and looks at what lands in
it: nothing at all on an ordinary load, the pages' own lines once `?debug=1` has been asked for,
the choice remembered from one load to the next, the levels, the round trips written down at both
ends — with the answer still readable by the caller, the log having read a clone of it, and a
`fetch` that fails still throwing — and, on the board, a move played the same with the log on as
without it.

`tests/application/test_broadcaster.py`, `tests/application/test_stream.py` and
`tests/application/test_stream_browser.py` cover the **SSE stream**, in three layers. The first
takes the broadcaster alone, without Flask or a browser: the one-slot box, three publications
coalescing into one wake-up, fan-out to several subscribers, and guaranteed removal — on a normal
exit, on an error, and on an abandoned generator, which is what happens when a tab closes. The
second takes the `/stream` route through the Flask client: mimetype and headers (`Cache-Control`,
`X-Accel-Buffering`), the opening comment to whoever is up to date and the whole game to whoever is
not, the `Last-Event-ID` prevailing over `?version` and the restarted server it catches up with, the
move pushed without anyone having asked for anything, the heartbeat, the **table composed per
recipient** — a seated player and an anonymous visitor receive the same game and two different
tables — the player re-read at every message, and ten streams opened then closed leaving nothing
behind them. The third opens Chromium: the page really holds an `EventSource`, it **never again**
polls `/game/state`, it calls nothing at all at rest, a move played outside — by an HTTP client
independent of the browser — arrives in less than a second and a half, two tabs see it together, a
visitor without an account sees it too, the "localiser" marker survives the scene being laid out
again, the fallback to polling settles in when `/stream` is cut, the page reconnects and catches up
on what it missed, and a closed tab frees its subscription.

The browser tests' server is **concurrent** (`threaded=True` in `tests/application/conftest.py` and
`tests/application/test_resume_browser.py`): since the stream, an open page holds a request in
progress as long as it lives, and a single-threaded server would serve nothing else.

`tests/application/test_map_fix.py` and `tests/application/test_map_fix_browser.py` cover the
map-fixing page — the second in Chromium: hovering, dialog, recording, zoom buttons. Both divert the
path of the fixes file to a temporary directory: **no test writes into `tenebrae/game_box/`**.

`tests/application/test_scenarios.py` and `tests/application/test_scenarios_browser.py` cover the
scenario page the same way: the hidden fields, the file written in the engine's format and read
back by it, each refusal with its message and no file written; and in Chromium the palette, laying,
moving and removing pieces, the square refused, the save dialog and the server's refusal read in
it. Both divert the scenarios directory: **no test writes into `tenebrae/scenarios/`**.

`tests/application/test_scenario_choice.py` and
`tests/application/test_scenario_choice_browser.py` cover the choice of the scenario a new game
opens on, and the `enabled` field that withdraws one: the list `/game/scenarios` serves, read from
the files at every request, the number `POST /game/new` accepts and the 409 it answers a disabled
or unknown one with — including one disabled between the chooser being filled and the click, which
is the whole point of the second reading — the board, the turn and the table that follow the new
set-up, the refusal that leaves the game exactly where it was and gives away no seat, and the saved
game resumed on its own scenario, disabled or not. In Chromium: the chooser on the list of games — what
it offers, the sides that follow the set-up chosen, a scenario leaving it at the next load once its
file disables it, the refusal shown under the form when the file is disabled after the page was
served, and the set-up chosen being the one laid out. Both work on a temporary **copy** of the
scenarios directory: no test writes into `tenebrae/scenarios/` here either.

`tests/application/test_games_list.py` and `tests/application/test_games_browser.py` cover the
**list of games** and what having several addresses for one process forces. The first without a
browser: the list is public and **opens no game** — the regression the landing page exists to avoid,
since `/` used to lay a set-up out on an empty base and so had every passer-by leave a game behind
them — every saved game listed most recently first, a card carrying its scenario, its turn, its
phase and its units, the occupants named and the free side and the machine each said as they are, a
finished game saying how it ended, a game whose scenario has left the disk listed without a name and
refusing to open, the date carrying its UTC offset — a naive one would read as the browser's own —
the games one holds a side in marked and no other, `/game/<id>` taking the server onto that game,
the same French 404 for an unknown identifier and for an address that is not one at all, the static
routes under `/game/` keeping their own rules against the dynamic one, `/game` sending to the last
game played and carrying its query string through the redirect, and — the one that is the point of
the whole change — **a move written into the game being played and into no other**, an older game
opened and played leaving the newer document exactly as it was.

The second, in Chromium: the empty base saying so, the cards on screen with their scenario, a card
opening its own game, only one's own games marked, the form opening a game and seating its creator
at the side they chose, the way back to the list in the table dialog, the dialog carrying neither
scenario chooser nor "contre l'IA" any more — and **two tabs**: one opens another game, and the
first says so and stops following, rather than reloading onto its own game and pulling the table
back and forth forever.

`tests/application/test_server.py` queries Flask without a browser: the contents of the hidden
fields — including the counter values the hover card reads there — the consistency of the
coordinates, the files served, the set-up served square by square — it must be the scenario's, and
the same from one load to the next — and the two movement routes, including the check that they add
nothing to the engine's rules, that the reach follows the placed piece's counter, that an opponent
in contact reduces it, that a friend does not, and that an accepted move really changes the server's
board. It also covers the **turn**: `#phase` in the page, `/phase/next` which skips magic and
alternates the players, `/move` refused outside the movement phase, `/combat/range` by distance, and
`/combat` which removes the right piece on a `DE` (die fixed by `monkeypatch` of `app.roll_the_die`),
falls the defender back on a `DR`, eliminates it when it has nowhere to go, and enters the fallen in
the game's register of casualties. The rule of **one combat per phase** has its own section there: an
attacker and a target refused at the second combat, a whole group of attackers marked at once, two
units of the same counter tracked apart, the `unavailable` lists served to the browser, and the
reset from one combat phase to the next then to the following turn. Every test there starts from a
**deserted map** — the `deserted_map` fixture clears the board, brings the turn back to its first
phase and empties the combat register, all three being shared from one request to the next. What the
scenario itself contains is exercised separately, in `tests/engine/test_scenario.py`; combat
resolution, in `tests/engine/test_combat.py` and `test_phase.py`.

`tests/application/test_board_browser.py` opens the page in Chromium with Playwright: the 48 pieces
loaded and centred to within a pixel, tilted by less than 5° — and **tilted once and for all**: a
move played outside the page makes the scene be laid out again through the stream, and the angles
must be the same, only a moved piece lying down again — a map that stays scaled after a resize, the
zoom — buttons, the wheel keeping its point under the pointer, pieces staying on their hexagon once
zoomed in, a hand-set scale that a resize does not undo — the hover card — the counter values of all
the units compared with the engine's catalogue, the mention of remarks appearing only when
warranted, the photograph, the square of a piece one has just moved, the card emptying on leaving
the piece without its area leaving with it, its one fixed width whatever it shows, staying empty on
a ghost, its elements stacked one per line, sitting **under** the toolbar
and aligned on its left edge, reading **at the bar's body size**, not making the bar grow — on a
narrow window as on a wide one — and not capturing clicks — the layout itself — the panel neither
overflowing the window nor scrolling sideways at 1400, 800 and 480 px, and the map it neither
displaces nor shrinks — then the full cycle click → ghosts → move, both fitted and zoomed in. The
expected ghosts are those the server's board computes — it runs in the same process, so it is read
directly — and one test places an opponent in contact to check that the click then shows fewer.
Finally the **turn and combat**: the phase label, "Phase suivante" which skips magic, movement
silent in the combat phase, the target highlighted in red, the full cycle — bring a Dwarf into
contact with an Orc, move to combat, designate target and attacker, "Attaquer", and see the
highlights fall away — and **one combat per phase**: the engaged units greyed out exactly where the
server's register enters them, the click that does not take them up again, and the greying that
falls at the next phase.

`tests/application/test_retreat_browser.py` follows a **fall-back on screen**, in the tab that
ordered the combat: the defender that gives ground moves, the friends it pushes move with it, the
unit with nowhere to go leaves the board, and the counter that falls back lies down at the server's
angle. The stream is **cut** there (`page.route(…, abort)`) on purpose: a scene laid out again would
put every counter right whatever the answer carried, and the file would check nothing. Its figures
are built on the map — a corner of bare plain, wide enough and inside the window — then saved and
the page loaded again on them, since nothing else would bring the tab a scene composed behind its
back.

`tests/application/test_persistence.py` is the one that looks into the base — at the documents
themselves — and plays the server's restart: memory emptied, only the base knows where the game
stood. It covers the opening of a game at the first load, resumption after that restart (the move
found again, the phase found again, the combat register found again), the elimination that does not
come back, the **tilts** written, resumed and rewritten on a move — and the save without that field
that stays resumable — a save whose scenario has no file discarded, `POST /game/new` which opens a second
document without erasing the first — including when both share the same date, the identifier
breaking the tie — the repository's round trip alone, and what only a real base shows: the placement
keys admitted as document keys, the dates that come back readable. Every other test file runs on
the same base, emptied before each test, and `GET /game` there lays the set-up out on the empty base
as `GET /` used to.

`tests/application/test_resume_browser.py` exercises resumption **as seen from the screen**, in
Chromium: move a piece then reload the page and find it at its new square, the phase likewise found
again, `POST /game/new` which puts the 48 units back, and the counters that a reload finds lying at
the same angle — the previous one for the motionless pieces, the new one for the moved piece — on
the shared server, so that the full chain is exercised as it really runs, without having to launch
the server oneself.

`tests/engine/test_seats.py` exercises the seating register alone, with no request and no
base: taking a side, the seat that is not taken from its occupant, the round trip of serialisation,
and a save from before players existed which simply leaves the table empty. It followed its subject
into the engine; `tests/application/test_connection_model.py` answers it on this side, and exercises
`Connection` alone: what the session carries and what it does not, the player re-read from the
repository at every request, an unknown identifier that becomes anonymous again, and the OAuth2
state removed as soon as it is taken back.

`tests/application/test_connection.py` unrolls the OAuth2 flow **in full** against the fake client:
the state drawn and checked, the one that does not match and the one that is replayed, the return
without a code, the player's refusal on Discord's page, Discord's error coming back up whole, the
player created then updated, and the access token that never enters the session. Then what the
server refuses: the anonymous visitor who sees the map but moves nothing, the player who does not
hold the active side, the one who has taken no seat, the second side refused to whoever holds one,
the seat that is not taken over, the two players each sitting at their own, the table of its own a
new game opens with, and map fixing reserved to the declared accounts.

`tests/application/test_discord_client.py` exercises `DiscordClient` alone, `urlopen` replaced in
the module: the token read from the answer, the HTTP error that carries over the status, the URL
called and the body of Discord's answer, the unreachable Discord that says which and why, and the
answer with no token.

`tests/application/test_connection_browser.py` does the same on screen: the button offering to log
in then showing the nickname, **the toolbar that does not grow by a pixel** once the avatar is in
place — it is this test that led to an avatar sized in `em` — the very long nickname that does not
push the buttons out of sight, the table dialog, the greying outside one's turn, the message a
refused move displays, and above all **two browsers open at the same time**: one passes its phase or
takes a seat, the other learns of it without reloading anything.

`tests/application/test_ai.py` exercises the game against the AI on the server side: creation
refused to the anonymous visitor, **allowed to a player holding no side** — one opens a game before
sitting down at it — the table of its own the new game opens with, the side the scenario has not,
the AI seated at what is left and shown as "IA" at the table, its opening turn played straight away
when it holds the Alliance, its turn triggered by the `POST /phase/next` that hands it play — the
die fixed by `monkeypatch`, as everywhere — and its seat that nobody can take. Two of those tests
were **turned round** rather than deleted when the game moved to the list: what a seat used to
justify refusing has nothing left to refuse. The strategy itself is exercised in the engine
(`tests/engine/test_artificial_opponent.py`); the persistence of its seat, in
`tests/application/test_persistence.py`. `tests/application/test_ai_browser.py` goes round again on
screen: the form's tick seating the machine at the side left over, the opening of the scenario
played by it before play comes back to the player, and the anonymous visitor offered the way in to
Discord in place of the form.

`tests/application/test_view.py` and `tests/application/test_view_browser.py` cover the **map
view**. The first without a browser: `#view` at `null` for the anonymous visitor as for whoever has
adjusted nothing, the view stored then returned, the anonymous visitor refused, no seat required,
six unreadable bodies refused with a 400, two players who do not share their view, the second
adjustment overwriting the first — and above all what it is **not**: the version does not rise,
nothing is deposited with a stream subscriber, and `/game/state` says nothing of it. The second, in
Chromium: the map opening fitted when nothing is stored, the zoom and the scroll each stored on
their own, the anonymous visitor storing nothing, the reload finding the scale **and** the point one
had at the centre, and the fitted view found fitted again — at the size of the new window, and not
at the old one's scale. What MongoDB makes of it is in `tests/application/test_persistence.py`.

**The whole suite plays logged in.** The `conftest.py`'s `client` fixture opens a session and seats
the test player **at both sides** — that is what lets the tests written before players existed
cross both sides within a single session, without rewriting a single one. The Playwright page
fixtures go through `/login` before opening the board: rather than fabricate a cookie, they unroll
the real flow, which the fake client closes on our own return route. To exercise a passing visitor,
take `anonymous_client`.

The browser tests require Chromium:

```
make browser
```
