# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Nature of the repository

Archiving and transcription work around *Ave Tenebrae*, a fantasy wargame by François
Marcela-Froideval (Jeux Descartes, 2nd ed. 1986): turning raw sources (a scanned PDF, an archived
blog page, photographs) into Markdown documents and usable data, **and then making a game of it**.
The game exists: a rules engine in Python, a Flask server, a two-player game saved in MongoDB.

**The code is in English; the game content is not.** Identifiers, docstrings, comments,
documentation and **the log** are English. What stays French, and must stay French:

- - the **game data** — `tenebrae/game_box/` and `tenebrae/scenarios/`: file names, JSON field
  names, terrain names (`plaine`, `bois`, `montagne`), piece keys (`nains-01-5-infanteries`), side
  names (`alliance`, `tenebres`). This is 1986 material, transcribed as it stands; translating it
  would put a second version of the game between the code and its source. New slugs there follow the
  existing convention: no accents, no apostrophes (`morts-vivants-01-20-unites-de-squelettes.jpg`);
- everything the **player reads** — button labels, page titles, phase names, refusal messages,
  and the combat sentences (`COMBAT_MESSAGES`, `describe_the_ratio`), which the browser shows as
  much as the log does. The log's own lines — what the AI played, a login refused, a seat taken, a
  new game, a phase change — are **English**: they exist for whoever reads `logs/battle_log.log`,
  and the browser's column carries them along. A line built from both, such as
  `Phase: Phase de combat — Nains (turn 1)`, therefore mixes the two, and that is intended;
- the **Mongo collections and stored field names** (`parties`, `joueurs`, `vues`, `camp_actif`,
  `inclinaisons`, …), which the models pin through `db_field`: renaming a stored field would
  orphan the games and accounts already in base;
- the **session keys** (`joueur`, `etat_oauth`), which are already in browsers' cookies;
- `tenebrae/game_box/ave_tenebrae_regles_fr.md`, the transcribed booklet, which is the source
  itself. Its English translation, `ave_tenebrae_regles_en.md`, sits beside it: that is the file
  to read and cite in ordinary work, the French one being opened only to check a passage.

Commit messages are in English, as they always were.

## Structure

Everything the code needs lives under the `tenebrae/` package, everything that checks it under
`tests/`, which mirrors it directory for directory, and the raw sources under `material/`:

```
tenebrae/                       the repository
├── tenebrae/                   the package: nothing is installed, it is imported from the root
│   ├── game_box/               the game material — the source of truth
│   ├── engine/                 the rules, in Python
│   ├── scenarios/              the set-ups, one JSON per scenario
│   └── application/            the Flask server
├── tests/engine/, tests/application/
├── material/base_material/     the raw sources
├── conftest.py                 puts the repository on sys.path
└── Makefile, .env.example, README.md, DEPLOYMENT.md, todo.txt
```

Five directories carry the work, with very different statuses:

| Directory | Role |
| --- | --- |
| `material/base_material/` | **Raw sources. Carries a `CLAUDE.md` saying "DO NOT USE THE CONTENT OF THIS DIRECTORY".** The rules PDF, the archived blog article, the 144 photographs. Not to be drawn on for ordinary work: everything taken from it already lives in `tenebrae/game_box/`. We come back only to check or complete a transcription, and then the derived file is updated. |
| `tenebrae/game_box/` | **The game material. Carries a `CLAUDE.md` saying "THIS DIRECTORY CONTAINS THE SOURCE OF TRUTH".** Transcribed rules, the map and its hexagon grid, the extraction script, and `pions/` (the inventory of the 127 counters + `pions.json`). This is where the game's code must read and write. |
| `tenebrae/engine/` | **The rules, in Python.** Two constants read at start-up — the map (the transcription overlaid with the fixes from `map_fix.json`) and the piece catalogue (`pions.json`) — then seven modules: `hexagon.py` (`Hex`: neighbourhood, terrain costs, moves, zones of control), `piece.py` (`Piece`: the counter's values, side), `board.py` (`Board`: who occupies which square, and at what angle the counter lies there), `scenario.py` (`Scenario`: a set-up read from `tenebrae/scenarios/`), `phase.py` (`Turn`: movement → magic → combat, round and round), `combat.py` (the booklet's Table I, and `CombatRegister`) and `ai.py` (the artificial opponent: targeting, marching, concentration of attacks — and the `AI_PLAYER` sentinel for its seat). Beside them, **the game entities**: `models/` (`Game`, `Player`, `Seats` — one file per model) and `repositories/` (their database access, one module per subject). Nothing of the web here — no Flask, no session, no request; the standard library is enough for the rules, mongoengine serving only the two documents and their repositories. See `tenebrae/engine/README.md`. |
| `tenebrae/scenarios/` | **The set-ups, fixed once and for all**, one JSON file per scenario of the booklet. The booklet says "the dwarf army masses south of the volcano of Toth"; the step from the sentence to the hexagons was taken by hand, and this directory keeps the result. Only no. 4 is fixed to date. See `tenebrae/scenarios/README.md`. |
| `tenebrae/application/` | **The server.** A Flask application (the `create_app` factory) that shows the map, a scenario's set-up (no. 4), and serves the moves and combats computed by `tenebrae/engine/`. It reads `tenebrae/game_box/` and `tenebrae/scenarios/`. It writes in two places: `tenebrae/game_box/map_fix.json`, through the `/admin/map_fix` route, and **MongoDB** — the current game (positions, piece tilts, phase, combat register, and who holds which side), saved at every move and resumed when `/` is loaded, plus the known **players**. The base is never touched from a route: everything goes through a repository (`tenebrae/engine/repositories/` for the game, `tenebrae/application/repositories/` for the rest), and the reference data stays in files. It models two things, and only what is not the game: the **connection** (`models/connection.py`) — the link between a Flask session and the engine's player, designated by their Discord identifier — and the **map view** (`models/view.py`, written by `repositories/view.py`), that is, the scale and the point each player had at the centre, returned at the next load so that a refresh no longer undoes their zoom. The game is played **by two, one player per side**, identified through **Discord OAuth2**: the map stays public, moves require being logged in and occupying the active side, and `/admin/map_fix` is reserved to the accounts in `ADMIN_DISCORD_IDS`. The second side can be **entrusted to the AI** (`POST /game/new` with `{"against_ai": true}`): the server then plays its whole turn — through `tenebrae/engine/ai.py` — within the request that hands it play. Authentication cost **no dependency at all** (`flask.session` and `urllib`). Each browser follows the other's game through an **SSE stream** (`GET /stream`, the broadcaster being in `stream.py`): the server pushes the game when it changes, and `mark_a_move` is the only point of publication. `/game/state` is still served as a fallback. The **game log** travels with it: it is written into `logs/battle_log.log` — at the root of the repository, rotating every thousand lines, three archives kept behind it — **and** into a bounded in-memory queue, which the page shows as a column under the unit card — hence the "log before marking the move" rule. See `tenebrae/application/README.md`, and `DEPLOYMENT.md` at the root for what the stream will require in production. |

`todo.txt` (at the root) carries the user's working instructions. It is theirs, and stays French.

The secrets — the MongoDB connection, the Discord application, `SECRET_KEY` — live in `.env` at the
root, **not versioned**: see `.env.example`, which `tenebrae/application/config.py` reads once at
start-up. Without `SECRET_KEY`, the application refuses to start rather than draw one at random.

## Architecture

Four rules, and they are not negotiated case by case.

**The game logic resides entirely in the engine, never in the application.** The game and the player
*as game entities* are in `tenebrae/engine/models/`, along with the seating table; their database
access is in `tenebrae/engine/repositories/`. The engine imports **nothing** from the application:
no Flask, no `session`, no `request`, no notion of a web user. A game can be played from an
interpreter, with no server. The dependency runs one way only — the application imports the engine.

**The application models only what is not the game**, and does so in `tenebrae/application/models/`,
with its own `tenebrae/application/repositories/` when there is a base to write. Two models to date:
`connection.py` — the session, none of which is persisted — and `view.py`, the scale and the point
of the map a player had at the centre. The view is here and not in the engine because **the engine
does not know that an image exists**: a game can be played from an interpreter, where zoom means
nothing; a piece's tilt, on the other hand, belongs to the board — both players see it the same
way, whereas a view belongs to one pair of eyes. Both models **reference the engine's player by
their identifier** (`discord_id`, a string) and duplicate none of their data: no nickname, no
avatar, no date. The player is re-read from the repository at every request. The rest of the
application is web orchestration — routes, authorization decorators, serialisation towards the
templates — and nothing else.

**One file per model, all the models in a `models/` directory.** A file grouping two model classes
is to be split. The `__init__.py` of those directories documents and re-exports nothing: `Seats`
needs only the standard library, and re-exporting the documents beside it would make mongoengine a
cost for whoever only wants a seating register — as it would for the application mounted without
persistence, which is built today without it. So the precise module is always imported: `from
tenebrae.engine.models.seats import Seats`.

**No relative imports, ever, and no bare module names either.** No `from .module import ...` nor
`from ..package import ...`, and no `import app` or `from config import ...`: always the whole path
from the repository root (`from tenebrae.engine.repositories.player import MongoPlayerRepository`,
`from tenebrae.application.models.connection import Connection`). Nothing is installed — it is the
root `conftest.py` that puts the repository on `sys.path`, and the server is launched from the root
as `python3 -m tenebrae.application.app`. A relative import, or a bare module name resting on a
directory that happens to be on the path, would break depending on where one launches from.

Renaming a mongoengine collection, on the other hand, is asked for: the existing schemas
(`parties`, `joueurs`, `vues`) stay compatible as long as nobody has an explicit reason to change
them. The same holds for stored field names, which the models pin through `db_field`.

## Versioning

**Everything is versioned, raw sources included.** It was the other way round at the start of the
project — the 28 MB of `material/base_material/` were excluded — and the documentation carried a
long warning about it: it no longer has any reason to be. The repository weighs some forty megabytes
and owns it; a fresh clone arrives complete, transcriptions **and** sources, and retouching a
transcription requires nothing else.

What stays out of git is short, and fits in two files:

| File | What it excludes | Why |
| --- | --- | --- |
| `.gitignore` | `.env` | the secrets: the MongoDB connection, the Discord credentials, `SECRET_KEY` |
| | `logs/` | the execution traces (`battle_log.log` and its archives), specific to one machine |
| | `.idea/`, `__pycache__/`, `.pytest_cache/` | local tooling and caches |
| `.git/info/exclude` | `/.python-version` | the pyenv virtualenv is a local choice |

`.git/info/exclude` also keeps three **stale** patterns — `/images/`, `/ave_tenebrae_regles.pdf`,
`/vintageboard-1-ave-tenebrae.html` — which targeted the root before the sources were moved into
`material/base_material/`. They no longer match anything and no longer protect anything: the files
they named are tracked today. Without effect, then, but misleading to read.

A single point of vigilance remains: **`.DS_Store` is ignored nowhere**, and the `/commit` skill
adds every file. Check `git status` before committing.

## The derived files and their sources

The relationship between the two has not changed, even though everything is now versioned: we read
and write in the derived files, and only go back to the source to check.

| Path | Role |
| --- | --- |
| `material/base_material/ave_tenebrae_regles.pdf` | Scanned rules booklet, 16 pages |
| `material/base_material/vintageboard-1-ave-tenebrae.html` | Archived blog article ("Vintageboard 1", R-One Chaff, irlboardgames.blogspot.com); contains the breakdown of the counter sheets |
| `material/base_material/images/` | 144 photographs of the box, the map and the counter sheets |
| `tenebrae/game_box/ave_tenebrae_regles_fr.md` | Transcription of the rules, in French, as the booklet stands |
| `tenebrae/game_box/ave_tenebrae_regles_en.md` | English translation of that transcription, section for section — **the rules reference for the code** |
| `tenebrae/game_box/map.jpg` | The game map (10 MB) |
| `tenebrae/game_box/carte.json` | 2280 hexagons, `"q,r,s"` → terrain |
| `tenebrae/game_box/carte_details.json` | `"q,r,s"` → every element of the hexagon |
| `tenebrae/game_box/carte_controle.jpg` | The map tinted by terrain, for checking by eye |
| `tenebrae/game_box/map.md` | Documentation of the map transcription |
| `tenebrae/game_box/map_fix.json` | Terrain fixes recorded by eye on `/admin/map_fix`, applied by the engine |
| `tenebrae/game_box/extract_map.py` | Regenerates `carte.json`, `carte_details.json` and `carte_controle.jpg` from `map.jpg` |
| `tenebrae/game_box/pions/` | Inventory of the 127 counters (renamed copies) + `pions.json`, the counter values |
| `tenebrae/scenarios/*.json` | Fixed set-ups, one per scenario |

## Tooling

No packaging, no CI. Do not introduce any without being asked. The only scaffolding is the root
`Makefile`, which serves to run the tests.

### Checking: always through a test, never by hand

**Every check goes through the test suite, run by `make test`.** This is a rule, not a preference:

- **Never launch the application to see whether it works** — no
  `python3 -m tenebrae.application.app` in the background followed by `curl`, no throwaway
  `python3 -c`. That kind of check cannot be replayed, proves nothing to anyone else, and leaves
  servers and containers behind it.
- **What we want to exercise is written as a test**, beside the others, so that it can be tried
  again. A new feature therefore arrives with its tests; a check one felt like running once is
  worth keeping.
- **The browser is Playwright** (`tests/application/test_board_browser.py`,
  `test_map_fix_browser.py`, `test_connection_browser.py`, `test_resume_browser.py`): that is where
  a page is opened, a piece clicked, a reload made. Not in a real browser opened by hand.

| Command | What it does |
| --- | --- |
| `make test` | brings up a test MongoDB in a Docker container (port 27018, database `tenebrae_test`), waits for it to answer, then runs the whole suite |
| `make test-fast` | the same suite without a base: the tests requiring a real MongoDB skip themselves |
| `make test-browser` | the Chromium tests only |
| `make coverage` | the whole suite, measuring what it covers of `tenebrae/`: the missing lines in the terminal, the source coloured in `htmlcov/index.html` |
| `make coverage-fast` | the same measurement without a base, as `test-fast` is to `test`; `ARGS="--ignore-glob=*browser*"` drops Chromium too, for a quick pass |
| `make mongo-stop` | removes the container (it stays up between two `make test`) |
| `make browser` | installs Chromium for Playwright |
| `make test ARGS="-k persistence -v"` | `ARGS` is passed to pytest as it stands |

The tests live in `tests/engine/` and `tests/application/` (pytest + Playwright, at the user's
request), mirroring the package they exercise, and are run **from the root** — the root
`conftest.py` puts the repository on `sys.path`, no package being installed, and every test imports
its subject by its full path (`from tenebrae.application.app import create_app`). `python3 -m
pytest` therefore works too, but without the base: prefer `make test`.

**Coverage is measured over `tenebrae/`, never over `tests/`**, and `.coveragerc` sets out what is
left out and why: the map extraction script, which no test may launch, and the `__init__.py` files,
which carry a docstring and re-export nothing. The figure is not a target to be met — a line is
covered because a test had a reason to exercise it, never so that the percentage should rise — but
a line nobody reaches is worth knowing about, and that is what the report is read for. Measure with
the browser tests in: dropping them can only lower the figure, and a report is worth reading only
if what it calls unreached really is.

The other executable is the map extraction script, to be run **from `tenebrae/game_box/`** (it works
in relative paths):

```
cd tenebrae/game_box && python3 extract_map.py
```

Dependencies (`requirements.txt`): Pillow, numpy, scipy for that script, Flask, mongoengine and
python-dotenv for the application, pytest, pytest-playwright and mongomock for the tests; the
engine uses only the standard library for its rules — its two documents and their repositories
require mongoengine, and nothing else. They are installed in the pyenv virtualenv `tenebrae` that
`.python-version` (at the root, not versioned) selects automatically; `python3` is enough.
The extraction script runs for about ten minutes and takes some 2 GB of memory.

## `tenebrae/game_box/carte.json` — the hexagon grid

`tenebrae/game_box/map.md` is the reference: coordinate system, alignment geometry on `map.jpg`, the
vocabulary of the 16 terrains, the priority rule, the table of named places, method and caveats.
Read it before touching the map data.

- A **flat-top, odd-q offset** grid, 57 columns × 40 rows = 2280 hexagons; cube keys `"q,r,s"` with
  `q + r + s = 0`.
- **The game map is not `carte.json` alone**: the engine lays `map_fix.json` over
  `carte_details.json` at start-up (`TRANSCRIBED_MAP` + `APPLIED_FIXES` → `MAP`). A fix replaces
  the main terrain and leaves the secondary elements. Fixing the map is therefore **never** done by
  editing `carte.json`: it is recorded in `map_fix.json` through `/admin/map_fix`, or the
  extraction script is corrected.
- `carte.json` gives **only one terrain per hexagon** (priority: built places > lake > mountain >
  hill > woods > rift > river > road > path > plain); `carte_details.json` keeps everything that
  was detected. Both files must stay consistent: regenerate them together with the script, never
  edit one by hand.
- The classification is automatic **except for the built places and the Rift of Tsaroth**, read
  under a magnifying glass and hard-coded in `extract_map.py` (`MORGENSTERN`, `FORTS`, `CASTLES`,
  `TOWERS`, `ISLANDS`, `RUINS`, `VILLAGES`, `RIFT`). A site fix is made there, not in the JSON.
- Two seed constants (`SEED_SIZE`, `SEED_ORIGIN`) initialise the grid alignment. The least-squares
  fit then converges on its own, but they remain necessary for the column and row numbering to come
  out right: do not touch them without rechecking `carte_controle.jpg`.
- The script's numeric settings are tuned on this precise scan (6173 × 5102 px) and are not
  generic.
- **Uncertainties are kept, not resolved**: the "Caveats on the transcription" section of `map.md`
  documents the hills (absent from the map, hence interpreted), the rivers treated as hexagon
  terrain instead of edges, the vague extent of the ruins of Ghaarth, an illegible village name.
  Add any new doubt there rather than settle it without a source.
- Check a change by looking at `carte_controle.jpg`, not by rereading the JSON.

## `tenebrae/game_box/ave_tenebrae_regles_fr.md` and `_en.md` — the rules, and their conventions

The booklet exists twice: `ave_tenebrae_regles_fr.md` is the transcription, and stays in French
because it *is* the booklet; `ave_tenebrae_regles_en.md` is its English translation, and **is the
source of truth for the code**: a rule is read there, a docstring or a README cites it there (with
its English section title: "Game phases", "Combats", "Terrain table"). The French file is opened
only to check a passage against the booklet, and the scenario JSONs, being French game data, keep
pointing at it.

**The two files mirror each other section for section**: same headings, same tables, same order,
same `---` separators, so that a place in one is found at the same place in the other. A
correction therefore lands in both — a transcription fix in the French file first, then its
translation. The translation is faithful, oddities included: where the booklet contradicts itself
or is vague, the English says the same thing and does not settle it. The only additions of the
English file are its own header and, in brackets, the names the code uses (the combat codes of
Table I, the terrain keys of `carte.json`).

Conventions common to both (set out in each file's own header):

- **Text only**: the booklet's illustrations are not reproduced, but their informative content is
  restated — the "Anatomy of a counter" diagram is rendered as an ASCII block *and* as a table, the
  counter symbols as a table of two double columns with Unicode approximations (`⊠ Infantry`,
  `↑ Phalanx`) or a description in brackets when no glyph will do (`(winged creature) Flyers`).
- **Every table in the booklet is converted into a Markdown table** (never into preformatted text).
- **Modernised spelling**: the booklet is set in gothic type where the glyph "b" stands for "v";
  the French text is restored to modern French, and the English translates that.
- **Proper nouns keep their original form** in the translation: Orvarth, Tsaroth, Ghaarth,
  Morgenstern, Orcreich, Reissland, Yzent, Val de Froy, Krak de Reiss. The combat codes (`AE`,
  `AR`, `DE`, `DR`, `EX`) are the booklet's and the engine's, and are not translated.
- Structure: `#` for the major parts (Rules, Special units, Magic, Book of spells, Purchase
  points, Scenarios, Terrain table — Règles, Unités spéciales, Magie, Livre des sortilèges, Points
  d'achat, Scénarios, Tableau des terrains in French), `##`/`###` below. Spells carry in their
  title the initials of the casters allowed: `### Fireball — *M, N*` (M = mage, C = cleric,
  N = necromancer).
- `---` separators between the major sections.

## `tenebrae/game_box/pions/` — the counter inventory

127 counter photographs, copied from `material/base_material/images/` (the originals stay there
**intact**; this directory contains only renamed copies) and filed into 21 numbered directories by
faction or purpose, after the breakdown given by the blog article. `pions.json` is added to them:
the values read by eye off the counters, which `tenebrae.engine.piece` reads at start-up.

- Naming: `NN-faction/faction-NN-<slugified-description>.jpg`, the numbering reflecting the order
  of presentation in the source. These names are data, and stay French.
- - `tenebrae/game_box/pions/README.md` is the master index: a summary of the 21 directories, the
  breakdown into sides (Alliance / Darkness / neutral), then one table per faction associating each
  file with its contents **and with its source photograph**. Every new copy must be added to those
  tables with its provenance.
- **The source's uncertainties are kept, not resolved**: the `(renforts ?)` labels and the
  interpretations of initials (`K` = kobolds?) keep their question mark, and the "Caveats on the
  inventory" section at the end of the README documents the known gaps (the missing photograph
  of the Chaos heavy cavalry, the non-human initials unexplained by the rules, five illegible
  movement values). Do not settle those points without a source; add to that section if new doubts
  appear.
- The final section lists the 17 images deliberately not reproduced (covers, map views, the blog's
  furniture).

## Commits

**Never commit on your own initiative.** It is the user who decides when and what to commit: leave
the work in the working tree and tell them about it. Commit only on an explicit request for that
commit — invoking `/commit`, or saying "commit". An instruction such as "version this file" means
"add it to the repository", not "commit". Permission given once does not hold for the next time.

Short messages in English, one sentence. The project's `/commit` skill produces a one-sentence
message, adds every file and commits: "every file" really does mean every, `.DS_Store` included if
it is lying around. A glance at `git status` beforehand.
