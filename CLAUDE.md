# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this is

Transcription and archiving of *Ave Tenebrae*, a fantasy wargame by François Marcela-Froideval
(Jeux Descartes, 2nd ed. 1986), and a playable game built on it: a rules engine in Python, a Flask
server, two-player games saved in MongoDB.

## Language: code in English, game content in French

Identifiers, docstrings, comments, documentation, commit messages and the log lines are English.
The following stay French and must not be translated:

- **Game data** in `tenebrae/game_box/` and `tenebrae/scenarios/`: file names, JSON fields,
  terrain names (`plaine`, `bois`), piece keys (`nains-01-5-infanteries`), side names
  (`alliance`, `tenebres`). It is 1986 material transcribed as it stands. New slugs follow the
  existing convention: no accents, no apostrophes.
- **Everything the player reads**: button labels, page titles, phase names, refusal messages,
  combat sentences (`COMBAT_MESSAGES`, `describe_the_ratio`). The log's own lines (AI move, login
  refused, phase change) are English, so a line such as `Phase: Phase de combat — Nains (turn 1)`
  mixes both, on purpose.
- **Mongo collection and field names** (`parties`, `joueurs`, `vues`, `camp_actif`, …), pinned
  through `db_field`: renaming one would orphan the existing games and accounts.
- **Session keys** (`joueur`, `etat_oauth`), already in browsers' cookies.
- `tenebrae/game_box/ave_tenebrae_regles_fr.md`, the transcribed booklet. Its translation
  `ave_tenebrae_regles_en.md` is the file to read and cite in ordinary work.
- `todo.txt` at the root: the user's working notes, theirs, in French.

## Layout

```
tenebrae/                       the package: nothing is installed, imported from the root
├── game_box/                   the game material — source of truth (has its own CLAUDE.md)
├── engine/                     the rules in Python, plus models/ and repositories/
├── scenarios/                  one JSON per fixed set-up (only no. 4 so far)
└── application/                the Flask server: create_app in app.py, routes/, logs/
tests/engine/, tests/application/   mirror the package
material/base_material/         raw sources: PDF, blog page, 144 photos — DO NOT USE (own CLAUDE.md)
conftest.py                     puts the repository on sys.path
Makefile, .env.example, README.md, DEPLOYMENT.md, todo.txt
```

Each directory has a README that is the reference for its details: `tenebrae/engine/README.md`,
`tenebrae/application/README.md`, `tenebrae/scenarios/README.md`, `tenebrae/game_box/map.md`,
`tenebrae/game_box/pions/README.md`, and `DEPLOYMENT.md` for production.

**Derived files and their sources.** Everything taken from `material/base_material/` already lives
in `tenebrae/game_box/`. Work reads and writes the derived files; the source is opened only to
check or complete a transcription, and the derived file is then updated.

| Derived file | Content |
| --- | --- |
| `game_box/ave_tenebrae_regles_fr.md` / `_en.md` | rules transcription and its translation |
| `game_box/map.jpg`, `carte.json`, `carte_details.json`, `carte_controle.jpg`, `map.md` | the map, its hexagon grid, the control image, its documentation |
| `game_box/map_fix.json` | terrain fixes recorded on `/admin/map_fix`, applied by the engine |
| `game_box/extract_map.py` | regenerates the three `carte*` files from `map.jpg` |
| `game_box/pions/` + `pions.json` | the 127 counter photographs, renamed, and their values |
| `scenarios/*.json` | fixed set-ups |

Secrets (MongoDB URI, Discord application, `SECRET_KEY`) live in `.env`, not versioned; see
`.env.example`. Without `SECRET_KEY` the application refuses to start.

## Architecture: four rules

1. **All game logic lives in the engine.** `Game`, `Player`, `Seats` and their repositories are in
   `tenebrae/engine/models/` and `tenebrae/engine/repositories/`. The engine imports nothing from
   the application: no Flask, no session, no request. A game can be played from an interpreter.
2. **The application models only what is not the game**: `models/connection.py` (the session, not
   persisted) and `models/view.py` (a player's zoom and centre, written by `repositories/view.py`).
   Both reference the engine's player by `discord_id` only and duplicate none of their data. The
   rest of the application is routes, authorization decorators and serialisation.
3. **One file per model, in a `models/` directory.** The `__init__.py` re-exports nothing, so that
   `Seats` can be imported without paying for mongoengine. Always import the precise module:
   `from tenebrae.engine.models.seats import Seats`.
4. **Absolute imports from the repository root, always.** No `from .x import`, no `import app`.
   Nothing is installed; `conftest.py` puts the root on `sys.path` and the server runs as
   `python3 -m tenebrae.application.app` from the root.

The base is never touched from a route: everything goes through a repository. Mongo collections
and `db_field` names stay as they are unless there is an explicit reason to change them.

Key facts about the application, detailed in its README: the routes are one blueprint per subject
under `routes/`, registered by `create_app`, and the game state — one game per process — lives in
the module globals of `current_game.py`; the game is played by two, one per side, through Discord
OAuth2 with no extra dependency; the second seat can go to the AI (`POST /game/new` with
`{"against_ai": true}`), which then plays its whole turn inside that request; each browser follows
the other's moves through SSE (`GET /stream`, `routes/stream.py` over the broadcaster of
`stream.py`), `mark_a_move` being the only point of publication; the log (`logs/`) goes to
`logs/battle_log.log` and to an in-memory queue shown in the page, hence the rule **log before
marking the move**. `/admin/map_fix` is reserved to `ADMIN_DISCORD_IDS`.

## Code style

- **Typing**: every function and method fully typed, `-> None` explicit. Use `Optional`,
  `list[str]`, etc. Avoid `Any`; when unavoidable, justify it in a short comment.
- **Function size**: soft limit of 50 lines. Beyond that, split into well-named sub-functions with
  a single responsibility each. Prefer composition of small functions to nested logic.
- **Classes**: one public class per file, file named after the class in snake_case. Dataclasses
  used as plain containers and small classes tightly coupled to the main one (result objects,
  enums, config) may share its file.
- **Modules**: split by topic as soon as a file does too much; group into subpackages when a topic
  grows. `__init__.py` stays thin.
- Readability and small testable units over cleverness; explicit over implicit.

## Docstrings

- All functions and methods require a docstring in Google style (Args, Returns, Raises as
  applicable).
- Keep docstrings reasonably sized: short and to the point for simple functions, more detailed
  only when it adds real clarity.
- Do not restate the obvious information already conveyed by the function signature.

## Comments

- Do not add comments to explain straightforward or self-evident code.
- Add comments only when the logic is genuinely complex, non-obvious, or could be misread.
- Keep comments short and synthetic — a brief note on intent or reasoning, not a narration of
  what the code does.
- Avoid verbose or redundant comments; never caption the obvious.

## Tooling and checking

No packaging, no CI. Do not introduce any without being asked. The `Makefile` runs the tests.

**Every check goes through a test run by `make test`.** Never launch the application to see whether
it works: no server in the background with `curl`, no throwaway `python3 -c`. Whatever needs
exercising is written as a test beside the others. Browser checks are Playwright tests in
`tests/application/test_*_browser.py`, not a browser opened by hand.

| Command | What it does |
| --- | --- |
| `make test` | starts a test MongoDB in Docker (port 27018, db `tenebrae_test`), runs the suite |
| `make test-fast` | same without a base: tests needing MongoDB skip |
| `make test-browser` | Chromium tests only |
| `make lint` | flake8 then mypy alone; the suite runs both as tests (`tests/test_static_checks.py`) |
| `make coverage` / `coverage-fast` | the suite measured over `tenebrae/`; `htmlcov/index.html` |
| `make mongo-stop` | removes the container (it stays up between runs) |
| `make browser` | installs Chromium for Playwright |
| `make test ARGS="-k persistence -v"` | `ARGS` goes to pytest as is |

Coverage is measured over `tenebrae/` only; `.coveragerc` excludes the extraction script and the
`__init__.py` files. The figure is not a target: a line is covered because a test had a reason to
reach it. Measure with the browser tests in.

The map extraction script runs from `tenebrae/game_box/` (`cd tenebrae/game_box && python3
extract_map.py`), takes about ten minutes and 2 GB. Dependencies are in `pyproject.toml`
(PEP 735 dependency groups, `pip install --group dev`), installed in the pyenv virtualenv
`tenebrae` selected by the unversioned `.python-version`.

## The map data

Read `tenebrae/game_box/map.md` before touching it.

- Flat-top, odd-q offset grid, 57 × 40 = 2280 hexagons, cube keys `"q,r,s"` with `q + r + s = 0`.
- The engine lays `map_fix.json` over `carte_details.json` at start-up. **Never edit `carte.json`
  by hand**: a fix is recorded through `/admin/map_fix`, or the extraction script is corrected.
- `carte.json` keeps one terrain per hexagon by priority (built places > lake > mountain > hill >
  woods > rift > river > road > path > plain); `carte_details.json` keeps everything detected.
  Regenerate both together.
- Built places and the Rift of Tsaroth are hard-coded in `extract_map.py` (`MORGENSTERN`, `FORTS`,
  `CASTLES`, `TOWERS`, `ISLANDS`, `RUINS`, `VILLAGES`, `RIFT`); site fixes go there.
- `SEED_SIZE` and `SEED_ORIGIN` set the grid alignment; do not touch them without rechecking
  `carte_controle.jpg`. The numeric settings are tuned to this scan (6173 × 5102 px).
- Check a change on `carte_controle.jpg`, not by reading the JSON.
- Uncertainties are documented in the "Caveats" section of `map.md`, not resolved without a source.

## The rules files

`ave_tenebrae_regles_fr.md` is the booklet; `ave_tenebrae_regles_en.md` is its faithful
translation, section for section, same headings, tables and `---` separators. A correction lands
in both, French first. The English file only adds its header and, in brackets, the names the code
uses (combat codes, terrain keys). Conventions: text only, illustrations restated as ASCII or
tables; every booklet table becomes a Markdown table; spelling modernised (gothic "b" read as "v");
proper nouns and the combat codes (`AE`, `AR`, `DE`, `DR`, `EX`) kept as they are; `#` for the
major parts, spells titled with the casters' initials (`### Fireball — *M, N*`).

## The counter inventory

`tenebrae/game_box/pions/`: 127 renamed copies of the source photographs (originals stay intact),
in 21 numbered directories, named `NN-faction/faction-NN-<slug>.jpg`, plus `pions.json`. The README
there is the master index: every copy is listed with its source photograph. The source's doubts
(`(renforts ?)`, uncertain initials, illegible values) are kept with their question mark and
documented in its "Caveats" section; add new doubts there rather than settle them.

## Versioning

Everything is versioned, raw sources included. Excluded: `.env`, `logs/`, `.idea/`,
`__pycache__/`, `.pytest_cache/` (`.gitignore`) and `/.python-version` (`.git/info/exclude`, which
also holds three stale patterns that no longer match anything). `.DS_Store` is ignored nowhere.

## Commits

**Never commit on your own initiative.** Commit only on an explicit request for that commit
(`/commit` or "commit"); "version this file" means add it, not commit. Permission does not carry
over to the next time. Messages: one English sentence. `/commit` adds every file, `.DS_Store`
included, so glance at `git status` first.
