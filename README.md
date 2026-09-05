# Ave Tenebrae

*Ave Tenebrae* is a fantasy wargame by François Marcela-Froideval, published by Jeux Descartes
(2nd edition, 1986): two armies, a hexagon map, 127 sheets of cardboard counters.

This repository does two things. It **archives** the game — the rules booklet transcribed into
Markdown, the map recorded hexagon by hexagon, the photographed inventory of the counters and the
values printed on them — and it **turns it into a playable game**: a rules engine in Python and a
Flask server where two players, identified through Discord, move and fight each other in turn on
the map in the browser.

The code and documentation are in English; the game content is not. The rules booklet, the map
vocabulary, the counter data and everything the player reads on screen stay in French — they are
the 1986 material, and translating them would put a second version of the game between the code
and its source. The game is not finished: movement and combat work, magic does not.

## Structure

```
tenebrae/                       the repository
├── tenebrae/                   the code and the game material, one package
│   ├── game_box/               the game material — the source of truth
│   ├── engine/                 the rules, in Python
│   ├── scenarios/              the set-ups, one JSON per scenario
│   └── application/            the Flask server and the map in the browser
├── tests/                      the test suite, mirroring the package
│   ├── engine/
│   └── application/
├── material/base_material/     the raw sources — not to be drawn on
├── conftest.py                 puts the root on sys.path: nothing is installed
├── Makefile                    runs the test suite (and its MongoDB)
└── .env.example                the configuration to copy to .env
```

Everything the code needs sits under the `tenebrae/` package, and everything that checks it under
`tests/`, which mirrors it directory for directory. Nothing is installed: the root `conftest.py`
puts the repository on `sys.path`, and every import is written from there —
`from tenebrae.engine.hexagon import Hex`, `from tenebrae.application.app import create_app`.
Never a relative import, never a bare module name.

### `material/base_material/` — the raw sources

The PDF of the booklet (16 scanned pages), an archived blog article giving the breakdown of the
counter sheets, and 144 photographs of the box, the map and the counters. **No work happens here**:
everything drawn from it lives in `tenebrae/game_box/`. We only come back to check a transcription.

### `tenebrae/game_box/` — the game material

The repository's source of truth. The code reads here, and nowhere else. Its file names and its
vocabulary are French: this is 1986 material, transcribed as it stands.

| File | Contents |
| --- | --- |
| `ave_tenebrae_regles_fr.md` | the transcribed booklet: rules, magic, spells, scenarios, tables |
| `ave_tenebrae_regles_en.md` | its English translation, section for section — the one to read and cite |
| `map.jpg` | the game map, scanned |
| `carte.json` | 2280 hexagons, `"q,r,s"` → one terrain |
| `carte_details.json` | the same, but with **every** element of each square |
| `map_fix.json` | the terrain fixes recorded by eye, applied by the engine |
| `carte_controle.jpg` | the map tinted by terrain, to check the transcription by eye |
| `map.md` | how the map was transcribed, and what remains uncertain |
| `extract_map.py` | regenerates the three map files from `map.jpg` (about ten minutes) |
| `pions/` | 127 counter photographs filed by faction, `pions.json` (the counter values) and their index |

### `tenebrae/engine/` — the rules and the game entities

Python with nothing of the web in it: **no Flask import, no notion of a session or a request**.
The rules need only the standard library; only the two persisted entities (`models/game.py`,
`models/player.py`) and their repositories require mongoengine. The map and the piece catalogue are
read **once, at import**: the board is printed, it does not change mid-game.

| Module | Contents |
| --- | --- |
| `hexagon.py` | `Hex` — neighbourhood, terrain costs, moves (Dijkstra), zones of control |
| `piece.py` | `Piece` — the counter's values, and the side of its faction |
| `board.py` | `Board` — who occupies which square; the engine's only mutable object |
| `scenario.py` | `Scenario` — a set-up read from `tenebrae/scenarios/`, and the board it yields |
| `phase.py` | `Turn` — movement → magic → combat, for each player, round and round |
| `combat.py` | the booklet's Table I |
| `combat_register.py` | `CombatRegister` — one combat per unit and per target, per phase |
| `models/` | the game entities, **one file per model**: `game.py`, `player.py`, `seats.py` |
| `repositories/` | database access to those entities: `game.py`, `player.py` |

`tenebrae/engine/README.md` details each class, the terrain costs, the zones of control, and the
list of rules from the booklet that are not played yet.

### `tenebrae/scenarios/` — the set-ups

The booklet says "the dwarf army masses south of the volcano of Toth" and never says which counter
goes on which square. The step from the sentence to the hexagons was taken **once, by hand**, and
its result lives here, one JSON per scenario. Only no. 4, "La guerre des nains", is fixed.

### `tenebrae/application/` — the server

A Flask application (`create_app`) that shows the map, lays the scenario out on it, and serves
whatever the engine decides. **The browser never judges the legality of a move**: clicking a piece
asks the server where it can go, and the server answers from `tenebrae/engine/`.

- The game is played **by two, one player per side**, identified through **Discord OAuth2**. The
  map stays visible without an account; playing requires being logged in and holding the active
  side.
- It is **saved in MongoDB** at every move — positions, phase, combats already fought, and who
  holds which side — and resumed when `/` is loaded.
- - Each browser follows the other's game through an **event stream** (`/stream`, Server-Sent
  Events, in `tenebrae/application/stream.py`): the server pushes the game when it changes, instead
  of being asked for it. The player's moves still leave as `POST`s, as before.
- `/admin/map_fix` serves to fix the map transcription, reserved to the accounts declared in
  `ADMIN_DISCORD_IDS`. It is the only place where the application writes into `tenebrae/game_box/`.
- `/admin/scenarios` composes a scenario on the map — pieces taken from a palette, laid with a
  click — and saves it as a new file in `tenebrae/scenarios/`; opened on
  `/admin/scenarios/<number>/edit`, it rewrites an existing one. Same accounts.

It models **only the connection** (`models/connection.py`) — the link between a Flask session and
the engine's player, designated by their Discord identifier — and the **map view**
(`models/view.py`), the scale and the point each player had at the centre. The game, the player
and the seating table are part of the game, and live in `tenebrae/engine/models/`.

`tenebrae/application/README.md` details the routes, the display, the phases, combat and logging in.

## The models

Everything the game keeps is in the engine; the application keeps only the connection and the map
view. One file per model, in a `models/` directory (see `CLAUDE.md`, "Architecture").

| Class | Module | Mongo collection | File |
| --- | --- | --- | --- |
| `Game` | engine | `parties` | `tenebrae/engine/models/game.py` |
| `Player` | engine | `joueurs` | `tenebrae/engine/models/player.py` |
| `Seats` | engine | — (travels in `Game`'s `places` field) | `tenebrae/engine/models/seats.py` |
| `Connection` | application | — (Flask's signed session cookie) | `tenebrae/application/models/connection.py` |
| `View` | application | `vues` | `tenebrae/application/models/view.py` |

The collection names stay French, as do the stored field names: renaming them would orphan the
games and accounts already in base. Only the Python side is English — the models pin the old names
through `db_field`.

`Seats` and `Connection` are not mongoengine documents, and therefore have no collection: the
seating table is saved **with the game**, in its `places` field (side → Discord identifier), and
the connection has no storage other than Flask's signed cookie, which lives on the player's
machine.

`Connection` designates the engine's `Player` by their `discord_id`, never by a Mongo reference:
it is the only link between the two worlds, and it runs one way only — the engine imports nothing
from the application.

Database access to them goes through a repository, never through a route:
`tenebrae/engine/repositories/game.py` and `tenebrae/engine/repositories/player.py`.

## Installing

```
python3 -m pip install --group dev   # pip >= 25.1; add --group map to regenerate the map
cp .env.example .env       # then fill in SECRET_KEY and the Discord credentials
```

Without `SECRET_KEY`, the application refuses to start, and without a MongoDB to reach at
`MONGODB_URI` nothing can be played: the game is saved there at every move.

## Running

```
python3 -m tenebrae.application.app
```

Then <http://127.0.0.1:5000/> for the list of saved games — a game is picked up or opened there —
<http://127.0.0.1:5000/game> for the one most recently played, and <http://127.0.0.1:5000/admin/map_fix>
to fix the map.

## Checking

Every check goes through the test suite — we do not launch the server to see whether it works.

| Command | What it does |
| --- | --- |
| `make test` | brings up a test MongoDB in Docker, then runs the whole suite |
| `make test-browser` | the Chromium (Playwright) tests only |
| `make lint` | flake8 then mypy alone; the suite runs both as tests |
| `make coverage` | the whole suite, and what it covers of `tenebrae/` (`htmlcov/index.html`) |
| `make browser` | installs Chromium for Playwright |
| `make mongo-stop` | removes the test container |

The tests live in `tests/engine/` and `tests/application/`, and are run from the
root. A test follows its subject: `tests/engine/test_seats.py` exercises the seating
register, `tests/application/test_connection_model.py` the connection model.

## Where to read next

| File | Subject |
| --- | --- |
| `tenebrae/game_box/ave_tenebrae_regles_en.md` | the game rules, translated from the booklet |
| `tenebrae/game_box/ave_tenebrae_regles_fr.md` | the booklet transcribed as it stands, in French |
| `tenebrae/game_box/map.md` | how the map was transcribed, and its caveats |
| `tenebrae/game_box/pions/README.md` | the inventory of the 127 counters |
| `tenebrae/engine/README.md` | the engine's classes and the interpretation of the rules |
| `tenebrae/scenarios/README.md` | the format of the set-ups |
| `tenebrae/application/README.md` | the server, the display, the phases, logging in through Discord |
| `DEPLOYMENT.md` | what the event stream will require behind a real server |
| `CLAUDE.md` | the repository's working conventions |

## Sources

The original material is Jeux Descartes' (1986); it is archived here for study and is not
redistributable. The breakdown of the counter sheets comes from the article "Vintageboard 1" by
R-One Chaff (irlboardgames.blogspot.com), kept in `material/base_material/`.
