# `tenebrae/application/` — the map displayed in the browser

A Flask application that serves `tenebrae/game_box/map.jpg`, **lays a scenario out on it** — no. 4,
"La guerre des nains", 18 dwarves against 30 orcs — and lets the browser do the geometry. Clicking
a piece shows as **ghosts** the squares it can go to; clicking a ghost moves it there. Hovering it
opens its **card**: its photograph enlarged and everything its counter carries.

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

A second page, `/admin/map_fix`, serves to fix the map transcription: it is the only place where the
application writes into `tenebrae/game_box/`, and only into a file of its own. The engine applies
those fixes at start-up — so the board is played on the fixed map. It is reserved to the accounts
declared in `ADMIN_DISCORD_IDS`.

The code is English; everything the player reads on screen is French, and so is the game data the
application serves.

## Running

From the root of the repository, with the pyenv virtualenv `tenebrae`:

```
python3 -m tenebrae.application.app
```

then <http://127.0.0.1:5000/> for the board, <http://127.0.0.1:5000/admin/map_fix> to fix the map.
The board **resumes the game where it was left** (see "Game persistence"); `POST /game/new` starts
it over.

A `.env` at the repository root is required (see `.env.example`): without `SECRET_KEY`, the
application refuses to start, and without the Discord credentials nobody can log in.

Dependencies: `Flask`, `mongoengine` and `python-dotenv` (plus `pytest`, `pytest-playwright` and
`mongomock` for the tests). **Authentication adds none**: the session rests on `flask.session`, and
the two calls to Discord on `urllib` from the standard library.

## Game persistence

The game is recorded in **MongoDB** at every move played — a move, a combat, a phase change — and
`GET /` resumes it. Only the game state goes there: the positions, the angle each counter lies at,
the current phase, what the combat phase has already consumed, and **who holds which side** —
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
an old save lie down once when it is resumed, and the first move played freezes their angles.

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
`tenebrae/application/config.py` reads them there once at start-up. `MONGODB_URI` and `PERSISTENCE`
for the database; `SECRET_KEY`, the three `DISCORD_*`, `ADMIN_DISCORD_IDS` and `SECURE_COOKIE` for
the players (see "Logging in through Discord").

**Playing without MongoDB**: `PERSISTENCE=none` in `.env`. The server then plugs in a repository
that keeps nothing, and the application behaves as it did before persistence — every load of `/`
lays the scenario's set-up out again. That is also what the test configuration does, which lets the
whole suite run without a database.

The **player** repository, on the other hand, then keeps **in memory** instead of keeping nothing.
The nuance matters: the game state already has a home in `app.py`'s module globals, a player has
none, and a repository keeping nothing would not impoverish the service — it would forbid it,
nobody being able to open a session any more, hence take a seat, hence play. The promise of
`PERSISTENCE=none` is kept in the same way: nothing outlives the server.

| Route | Effect |
| --- | --- |
| `GET /` | resumes the last game; failing that — an empty base, or a save of another scenario — lays the scenario out again and opens one |
| `POST /game/new` | lays the scenario out again and opens a new game, **without lifting the table**; with the body `{"against_ai": true}`, entrusts the opposing side to the AI (see "Playing against the AI"); returns `{"pieces": […], "phase": {…}}` and the table |
| `POST /view` — body `{scale, x, y, fitted}` | keeps where this player is on the map, and returns it as it stands; **login required, a seat not**; it is not a move played (see "Finding one's map view again") |

The previous games stay in base: `POST /game/new` erases nothing, it opens one more document, and
it is the most recent that `/` resumes.

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
| `#version` | the game's version number, by which the browser sees that the opponent has played |
| `#view` | where this player was on the map: `{scale, x, y, fitted}`, or `null` (see "Finding one's map view again") |
| `#initial-log` | the game log when the page opens: `[{time, text}, …]`, from the oldest line to the most recent (see "The log column") |

## The server's board

Zones of control require knowing **who occupies which square and on which side**: the server
therefore holds an `tenebrae.engine.board.Board`, rebuilt at every load of `/` and updated by
`/move`. Without it, the zones would be computed on stale positions from the first move on.

Beside the board, the server holds an `tenebrae.engine.phase.Turn` — the module global `TURN`: which
side plays, and at what. Board and turn are **resumed from the saved game** at every load of `/`, or
rebuilt from the scenario if there is none (see "Game persistence"). There is only **one current
game per process**: two tabs open on `/` share the same board and the same turn — which suits,
since both players play the same game.

Beside them, the module global `SEATS` (`tenebrae/engine/models/seats.py`) keeps who holds which
side. Unlike the board and the turn, it is **not** rebuilt at every load of `/`: starting a game
over sends nobody away from their seat.

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
| `POST /phase/next` | the next phase, same shape; logged |
| `GET /combat/range?cq=&cr=&cs=&aq=&ar=&as=` | `{"in_range": bool, "available": bool, "message": str\|null}`; a refusal goes to the log |
| `GET /combat/target?cq=&cr=&cs=` | `{"available": bool, "message": str\|null}`; a refusal goes to the log |
| `POST /combat` — body `{"target": {q,r,s}, "attackers": [{q,r,s}, …]}` | see below |

`GET /` carries `#phase`; the JavaScript takes from it the toolbar's label and **what a click
does**: in the movement phase, only the active side shows its ghosts; in the combat phase,

1. a click on an **opposing** unit → the server (`/combat/target`) says whether it can still be
   taken; if so, it becomes the target, highlighted in **red**;
2. a click on one of one's **own** units → the server (`/combat/range`) says whether it is in range
   (distance ≤ 1, or ≤ its firing range) and whether it has not already attacked; if so, it joins
   the attackers, highlighted in **gold**; if not, nothing moves and the refusal is in the log;
3. "Attaquer" (visible as soon as there is a target and an attacker) → `POST /combat`;
4. "Annuler", or a new click on the target → the selection empties and the highlights fall away.

`POST /combat` revalidates everything on the server side — phase, the target's side, each
attacker's range, and the phase register — rolls the die (`app.roll_the_die`, isolated for the
tests), resolves through `tenebrae.engine.combat.fight` and applies the result:

```json
{"resolved": true, "outcome": "DE", "message": "Combat résolu : Défenseur Éliminé",
 "eliminated": [{"q": 1, "r": 26, "s": -27, "terrain": "plaine"}], "roll": 4, "die": 4, "ratio": [3, 1],
 "unavailable": {"attackers": [{"q": 0, "r": 26, "s": -26, "terrain": "plaine"}], "targets": []}}
```

Only the outcomes `AE`, `DE` and `EX` remove pieces; the retreats (`AR`, `DR`) change nothing.
`{"resolved": false, "message": …}` when it is not the combat phase, when the target is not an
opponent, when it has already been attacked, or when no attacker is valid.

### One combat per unit and per phase

The booklet limits each unit to one attack per phase, and each target to one attack per phase even
by different attackers. The count is kept **on the server side** by the module global `REGISTER`
(`tenebrae.engine.combat.CombatRegister`), beside `BOARD` and `TURN`:

- it is **emptied at every phase change** (`POST /phase/next`) — so between the Dwarves' combat
  phase and the Orcs', and at the next turn. `GET /` resumes it from the save, or empties it if it
  lays the scenario out again;
- a combat **fought** enters all its attackers and its target in it, **whatever its outcome**: a
  retreat, which the engine leaves without effect, has engaged its units all the same;
- a combat **refused** (no valid attacker) enters nothing.

`unavailable` — carried by `#phase`, `GET`/`POST /phase…` and the response of `POST /combat` — gives
the **squares** of that register that still carry a piece, so that the page can grey those units out
(`.piece.unavailable`). The register designates units by their square and not by their counter: see
`tenebrae/engine/README.md` § "One combat per unit and per phase" for what that assumes.

**The log is written in two places at once** — one line per event: a phase change, a seat taken, a
unit out of range, a combat result in French, the AI's moves.

A combat writes **two**: the ratio computation, then its outcome.

```
Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4
Combat résolu : Défenseur Éliminé
```

The computation first, the outcome next — the browser's column reading the other way round from
the file, that is what puts the outcome at the top and its breakdown just below. The sentence is
composed by `describe_the_ratio`, from the numbers `combat.RatioBreakdown` kept (see
`tenebrae/engine/README.md` § "The breakdown of the computation"): the engine builds no sentence,
and the application recomputes nothing. The **defender's terrain is always named**, including when
it multiplies nothing — it is what one came for; the three terms, for their part, are only spelled
out when there is a detail to spell out (a lone attacker, a neutral terrain and a die that nothing
raises are written as a single number).

- `logs/battle_log.log`, **the file**, at the repository root. It is the second place where the
  application writes to disk, after `/admin/map_fix`; the whole of `logs/` is ignored by git. It is
  **rotating**: after `LINES_PER_FILE` lines (a thousand) it is set aside as `battle_log.log.1`,
  the archives shifting behind it up to `LOGS_KEPT` (three) — that is at most four thousand lines
  kept, the oldest archive being erased next. The threshold is counted in **lines** and not in
  bytes (`RotatingLog`, which redefines `RotatingFileHandler`'s `shouldRollover`): it is in lines
  that this log is read, one per game event. The counter picks up from what the file already
  carries, so that a server restarted ten times in a day does not write ten times a thousand lines
  into the same file;
- a **bounded in-memory queue** (`InMemoryLog`, `LINES_KEPT` lines), which the browser turns into
  its column. It is a *handler* plugged onto the same logger, and not a call added beside each
  `LOG.info`: there is only one point of writing, and the column cannot say anything other than the
  file.

The lines kept leave with the game: `shared_snapshot` carries them, so the SSE stream and
`GET /game/state` do too, and `GET /` gives them straight away in `#initial-log`. Hence the rule
the routes follow: **log before marking the move**. `mark_a_move` photographs the game, log
included; a route that logged after saving would push the browsers an account one move behind.
`tests/application/test_log.py` checks it route by route.

## The log column

The log reads **in a column under the card**, in the same panel (`#panel`) and of the same make as
the bar and the card: same box, same background, same font size. Nothing moves — the panel grows
downwards, the bar does not budge.

It reads **the other way round from the file**: the server gives its lines from the oldest to the
most recent, the column shows the last one at the top, where the eye returns. One therefore sees
what has just happened without doing anything, and nothing scrolls anything in the player's stead;
the scrollbar (`max-height: 40vh`) is for ancient history. Empty, the column does not appear.

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
on its left edge. The card appears and disappears under the bar; neither of them moves.

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
  and the map occupies the window as if it did not exist.
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

What is **public**: `/`, the map, the piece images, `/moves`, `/phase`, `/combat/range`,
`/combat/target`, `/game/state` and `/stream`. A passing visitor therefore sees the game — and
follows it live — and can consult what would be reachable, as before. What requires **a seat at the
active side**: `/move`, `/combat`, `/phase/next`. `POST /game/new` only requires being seated:
starting over is not a move, and **the seats are kept** — they are the same two people, and
emptying them would lock out the very person who has just clicked.

The refusals return **401** when nobody is logged in, **403** when somebody is but does not hold
what is needed, with a `message` in French that the page displays under the toolbar. The rest of
the failures keep the silence they had, their refusals going to the log.

Logging out does not give up one's seat: one comes back to sit in it.

### Playing against the AI

The second account can be a machine. The **"Nouvelle partie contre l'IA"** button in the table
dialog — visible when one is seated and the other side is there to give: free, or already held by
the AI — sends `POST /game/new` with the body `{"against_ai": true}`: the scenario is laid out
again, and the side the requester does not hold is entrusted to the AI. A side held by another
human is not there to give — 409, nobody is thrown out, and the set-up is not rebuilt.

The AI has neither a session nor a Discord account: it occupies its seat under the `ai.AI_PLAYER`
sentinel (`"ia"`, which no Discord identifier — strings of digits — can carry), which travels in
the seats dict like any other identifier — nothing more to save, nothing more to resume — and which
`the_table()` displays under the name "IA". A human cannot sit there — the seat is occupied — and
`active_side_required` can never pair a session with it.

Its turn is played **on the server side, within the request that hands it play**:
`let_the_ai_play()`, called at the end of `POST /phase/next` — and at the creation of the game, in
case the scenario opens on its side. The strategy lives in the engine (`tenebrae/engine/ai.py`, see
`tenebrae/engine/README.md`); the application only passes it the die (`roll_the_die`), saves and
logs. A single save at the end of the turn: the version rises, and the browser sees the AI's moves
at once through the stream, as it would see a human opponent's. A save therefore never lands on a
phase held by the AI — "/" never has to make it play.

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
- `mark_a_move`, in `app.py`, which publishes. **It is the only point of publication**, and it is
  also the compulsory passage of everything that moves: no move can be played without the open
  streams learning of it.

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

The server no longer draws anything at random: it reads the set-up of scenario `SCENARIO_NUMBER` (4)
from `tenebrae/scenarios/` through `tenebrae.engine.scenario`, once at start-up, and lays it out
again at the first load of `/` — or at each, if persistence is unplugged.

- - **The placement comes from the file, not from the server.**
  `tenebrae/scenarios/scenario-04-la-guerre-des-nains.json` gives "square → piece key"; the
  application adds to it only what the display needs — the image, the readable name, the movement
  and the side, all taken from the catalogue in `tenebrae/game_box/pions/`. The detail of the
  deployment and its caveats are in `tenebrae/scenarios/README.md`.
- **The starting position is reproducible.** A fresh game always puts the 48 units back on the same
  squares: that is what makes it possible to exercise a move twice in a row and get the same
  result. `POST /game/new` — and, without persistence, a simple reload — brings it back.
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

## Tests

From the **repository root**, so as to cover the engine too:

```
make test
```

`make test` brings up a test MongoDB in a container itself — port 27018, database `tenebrae_test`,
separate from the game's — waits for it to answer, then runs the whole suite pointing it at it.
Without Docker, `make test-fast` runs the same suite without a base: the tests requiring a real
MongoDB skip themselves. `make mongo-stop` removes the container, which otherwise stays up from one
series to the next. `ARGS` passes arguments to pytest: `make test ARGS="-k persistence -v"`.

`make coverage` runs that same suite and reports what it covers of `tenebrae/` — the missing lines
in the terminal, the source coloured in `htmlcov/index.html`. Chromium is measured with the rest:
the browser tests reach the routes through the page that serves them, and dropping them can only
lower the figure. `make coverage-fast` measures the same thing without a base, as `test-fast` is to
`test`; adding `ARGS="--ignore-glob=*browser*"` drops Chromium as well, which turns the minutes
into seconds and under-estimates the application further — that pass says where to look, not where
one stands.

**Nothing is checked by hand**: no server launched to go and look, no `curl`. What we want to
exercise is written as a test, and what shows in a page is exercised in Chromium through Playwright.

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

`tests/application/test_server.py` queries Flask without a browser: the contents of the hidden
fields — including the counter values the hover card reads there — the consistency of the
coordinates, the files served, the set-up served square by square — it must be the scenario's, and
the same from one load to the next — and the two movement routes, including the check that they add
nothing to the engine's rules, that the reach follows the placed piece's counter, that an opponent
in contact reduces it, that a friend does not, and that an accepted move really changes the server's
board. It also covers the **turn**: `#phase` in the page, `/phase/next` which skips magic and
alternates the players, `/move` refused outside the movement phase, `/combat/range` by distance, and
`/combat` which removes the right piece on a `DE` (die fixed by `monkeypatch` of `app.roll_the_die`)
and touches nothing on a retreat. The rule of **one combat per phase** has its own section there: an
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
warranted, the photograph, the square of a piece one has just moved, the card closing on leaving the
piece, not appearing on a ghost, its elements stacked one per line, sitting **under** the toolbar
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

`tests/application/test_persistence.py` is the only one to plug in persistence, on **mongomock** —
an in-memory MongoDB: no server is required, and the file skips itself if mongomock is not
installed. It covers the opening of a game at the first load, resumption after a simulated restart
(the move found again, the phase found again, the combat register found again), the elimination that
does not come back, the **tilts** written, resumed and rewritten on a move — and the save without
that field that stays resumable — a save of another scenario discarded, `POST /game/new` which opens
a second document without erasing the first — including when both share the same date, the
identifier breaking the tie — and the repository's round trip alone. Everywhere else the test
configuration installs the **null repository**: the other test files see no database, and `GET /`
there lays the set-up out again as before.

`tests/application/test_resume_browser.py` exercises resumption **as seen from the screen**, in
Chromium: move a piece then reload the page and find it at its new square, the phase likewise found
again, `POST /game/new` which puts the 48 units back, and the counters that a reload finds lying at
the same angle — the previous one for the motionless pieces, the new one for the moved piece. Each
test there runs **twice** — on mongomock, and on the real MongoDB as soon as `MONGODB_URI_TEST`
designates one that answers, which `make test` does — so that the full chain is exercised as it
really runs, without having to launch the server oneself.

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
the seat that is not taken over, the two players each sitting at their own, the seats kept by `POST
/game/new`, and map fixing reserved to the declared accounts.

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
refused to the anonymous visitor, to the player with no seat and when the other side is held by a
human, the AI seated and shown as "IA" at the table, its opening turn played straight away when it
holds the Alliance, its turn triggered by the `POST /phase/next` that hands it play — the die fixed
by `monkeypatch`, as everywhere — and its seat that nobody can take. The strategy itself is
exercised in the engine (`tests/engine/test_artificial_opponent.py`); the persistence of its seat,
in `tests/application/test_persistence.py`. `tests/application/test_ai_browser.py` goes round again
on screen: the button hidden from whoever is not seated, the opposing side entrusted to the AI with
one click, and the opening of the scenario played by it before play comes back to the player.

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
