# `tenebrae/engine/` — the heart of the game

The rules of *Ave Tenebrae* in Python, with nothing that touches the web: `tenebrae/application/`
only serves what this package decides. A move is never judged legal by the browser.

The code is English; the game data it reads is not — terrain names, piece keys and side names stay
French, as they are in `tenebrae/game_box/`.

| File | Contents |
| --- | --- |
| `hexagon.py` | the map read as a constant, and the `Hex` class |
| `piece.py` | the piece catalogue read as a constant, and the `Piece` class |
| `board.py` | the game state: which pieces are placed, where, on which side, and at what angle |
| `scenario.py` | the set-ups fixed in `tenebrae/scenarios/`, and the `Board` they yield |
| `phase.py` | the state machine of a turn: which side plays, and at what (`Turn`) |
| `combat.py` | combat resolution after the booklet's Table I |
| `combat_register.py` | the register of one combat per unit and per target, per phase (`CombatRegister`) |
| `retreat.py` | what becomes of a unit a combat forces to fall back: the chain of pushes, or its elimination |
| `casualties.py` | the units removed from play, kept for the count at the end of the game (`Casualties`) |
| `victory.py` | who has been annihilated: the booklet's first victory condition, counted |
| `ai.py` | the artificial opponent: the side the server plays on its own |
| `models/` | the game entities, one file per model: `Game`, `Player`, `Seats` |
| `repositories/` | their database access, one module per subject: `game.py`, `player.py` |

The first two are constants — the map and the counters have been printed since 1986. The third is
the engine's only mutable object: the positions do change. The fourth says where they start from.

## The game entities — `models/` and `repositories/`

Everything the game **keeps** is here, and not in the application: a saved game, a player, the
table saying who holds which side. That is an architectural rule of the repository, set out in the
root `CLAUDE.md` — the game logic resides entirely in the engine, the application handles only the
connection and the map view.

| Class | File | Mongo collection | What it holds |
| --- | --- | --- | --- |
| `Game` | `models/game.py` | `parties` | placement, tilts, phase, turn, combats already fought, seats |
| `Player` | `models/player.py` | `joueurs` | a Discord account the game knows: identifier, nickname, avatar |
| `Seats` | `models/seats.py` | — | side → Discord identifier; saved in `Game`'s `places` field |

The collection names and the stored field names stay French, pinned through `db_field`: renaming a
stored field would orphan the games and accounts already in base.

**One file per model**, and the `__init__.py` re-exports nothing: `Seats` needs only the standard
library, whereas the two documents require mongoengine. The precise module is therefore imported,
absolutely — `from tenebrae.engine.models.seats import Seats` — never a relative import.

The engine does **not** know the *connected* player. There is no session here, no cookie, no
request, not the least Flask import: the link between a visitor and their `Player` is held by the
application, in `tenebrae/application/models/connection.py`, which designates the player by their
`discord_id`. The dependency runs one way only.

```python
from tenebrae.engine.models.seats import Seats

table = Seats()
table.seat("alliance", "100000000000000001")
table.holds("100000000000000001", "alliance")  # True
table.is_free("tenebres")  # True
table.to_dict()  # {'seats': {'alliance': '1000...01'}}
```

Nothing speaks to MongoDB directly: everything goes through a **repository**, which exchanges only
state dicts — never a document.

| Repository | File | Role |
| --- | --- | --- |
| `MongoGameRepository` | `repositories/game.py` | one document per game, each played and saved by its own identifier; `games()` lists them, `load(id)` reads one, `save(id, state)` writes into that one and no other |
| `MongoPlayerRepository` | `repositories/player.py` | one document per known Discord account |

It is `create_app` that hooks them onto the application — and the routes know nothing of MongoDB.
The tests go through the same repositories, on the base `make test` brings up.

## The `Hex` class

```python
from tenebrae.engine.hexagon import Hex

origin = Hex(13, -4, -9)  # or Hex(13, -4): s follows from q + r + s = 0
origin = Hex.from_key("13,-4,-9")
Hex()  # an empty hexagon, with no position

origin.terrain  # 'plaine' — the main terrain
origin.elements  # ('plaine',) — everything the square carries, terrain first
origin.neighbours()  # the six adjacent hexagons still on the map
origin.distance(other)  # as the crow flies, in squares — regardless of terrain
origin.moves(5)  # a list of Hex objects reachable with 5 points
origin.to_dict()  # {'q': 13, 'r': -4, 's': -9, 'terrain': 'plaine'}
```

`moves()` is a Dijkstra walk bounded by the movement budget — that of the departing piece,
`Piece.movement_points` (see below); with no argument, the flat 5 points. The costs are
`fractions.Fraction` and not floats: a road is worth a third of a point, and a path of five points
must not drift on rounding.

Two keyword arguments add the opponent — `enemies` and `under_control`, sets of "q,r,s" keys (see
"Zones of control"). Without them, the map is held to be deserted and the walk knows nothing but
terrain.

The map is read **once, at module import** — the board is printed, it does not change mid-game. It
is `tenebrae/game_box/carte_details.json` that is read, and not `carte.json`: the head of its list
gives the same main terrain, but it alone keeps the 58 roads and paths that the map's priority rule
hides under a wood or a massif. Without it, the northern black road would not exist for movement.

## The game map — the transcription, fixed

The automatic transcription contains errors, noticed by eye on the application's `/admin/map_fix`
page and written into `tenebrae/game_box/map_fix.json`. The engine applies them on top:

| Constant | Contents |
| --- | --- |
| `TRANSCRIBED_MAP` | `carte_details.json` as it stands — what `extract_map.py` produces |
| `APPLIED_FIXES` | `map_fix.json` as it was at start-up: `"q,r,s" → terrain` |
| `MAP` | the first overlaid with the second: **the map the game is played on** |

`apply_fixes(transcription, fixes)` is a pure function. A fix bears only on the **main terrain**:
it takes the lead in place of the one the map's priority put there, and the secondary elements
follow.

```
carte_details: ["bois", "route"]   +   map_fix: "colline"   →   ("colline", "route")
```

That is what lets a wood on the black road be fixed into a hill without cutting the road. A key the
transcription does not know is ignored: we do not create hexagons off the map.

Both files stay separate — `carte_details.json` comes out of the script and is never touched up —
and **the overlay happens only at start-up**: fixing the map while the server runs changes nothing
until it is restarted. The admin page says so.

## The `Piece` class

```python
from tenebrae.engine.piece import CATALOGUE, piece

cavalry = piece("reissland-02-8-cavaleries")
cavalry.strength  # 5 — top left of the counter
cavalry.movement  # 8 — top right
cavalry.fire, cavalry.range  # (None, None): it does not fire
cavalry.flight_movement  # None — the figure in brackets, when there is one
cavalry.special_abilities  # None — the letter at the top centre: "P", "s"…
cavalry.movement_points  # 8 — what movement consumes
cavalry.is_a_unit  # True — a marker would answer False
cavalry.side  # 'alliance' — 'tenebres' or 'neutre' for others
cavalry.exerts_a_zone_of_control  # True

Hex(1, 26, -27).moves(cavalry.movement_points)
```

The values come from `tenebrae/game_box/pions/pions.json`, read by eye off the 127 photographs in
`tenebrae/game_box/pions/` (see `tenebrae/game_box/pions/README.md`). Its field names are French,
and are read as such. The file is read **once, at import**: like the map, the counters are printed,
they do not change mid-game.

A value absent from the counter — or illegible on the photograph — is `None`, and `remarks` says
which. Only `movement_points` commits, because movement needs a number:

| The piece carries | `movement_points` |
| --- | --- |
| a ground movement | that movement, from 1 to 20 points |
| a flight movement only | that flight, for want of anything better — the single bat |
| no value at all | `MOTIONLESS`, that is 0: a marker does not move |

`is_a_unit` separates the 115 units from the 12 photographs that are not: the 6 markers, the
2 record sheets and the 4 overviews carry no numeric value.

### The sides

The side is **not** in `pions.json`: it is not printed on the counter. It comes from the "Camps"
section of `tenebrae/game_box/pions/README.md`, held here in `SIDES`, faction by faction:

| Side | Factions | Pieces |
| --- | --- | --- |
| `ALLIANCE` | Reissland, Empire Tharque, Templiers, Population, Empire de Lynn, Elfes, Nains, Dragons | 47 |
| `DARKNESS` | Yzent, Chaos, Non-humains, Orques, Sahuaguins, Morts-vivants, Démons, Juggernaut | 56 |
| `NEUTRAL` | Volants, conjurations, magiciens, markers, overviews | 24 |

`OPPONENTS` says who opposes whom: the alliance and the darkness, and nobody else. **The neutral
side has no opponent** — it hinders nobody and nobody hinders it. The scenarios would put more
nuance into it (the Empire de Lynn only enters at scenario 3, the Dwarves at 4, the Flyers at 5,
Yzent is an "ally of convenience"): the engine knows nothing of that.

## Zones of control

> Each unit exerts a particular influence over the six squares surrounding the one it occupies:
> those six squares constitute its "zone of control".

`zone_of_control(hexagons)` returns those squares, as "q,r,s" keys. `Hex.moves()` takes account of
them through its two keyword arguments:

| Argument | Contents | Effect |
| --- | --- | --- |
| `enemies` | the squares the opponent occupies | they are not entered: movement does not join combat |
| `under_control` | the squares its zones cover | they are entered at the terrain's rate, and one must stop there |

The booklet fits in three lines, and the walk in three rules:

| The rule | In the walk |
| --- | --- |
| "enter […] without spending additional points" | the square costs what its terrain costs |
| "it must stop as soon as it has entered" | a unit does not leave a controlled square |
| "one cannot pass from one zone to another without having left the first" | the origin square, the only controlled square one still progresses from, leads only to free squares |

A unit that **begins** its move under control therefore leaves it, but through a free square: the
figure of the booklet's example, where C goes round X1 to reach X2 and "will therefore spend 4
movement points instead of 2", is found as it stands in
`tests/engine/test_zone_of_control.py`.

## The `Board` class

```python
from tenebrae.engine.board import Board

board = Board([(Hex(1, 26, -27), piece("elfes-01-5-infanteries"))])
board.place(hexagon, piece)  # one square, one piece; remove() and clear() undo
board.piece_on(hexagon)  # the Piece placed there, or None
board.tilt_on(hexagon)  # the angle it lies at, in degrees
board.squares_held_by("alliance")  # the "q,r,s" keys of that side
board.opponents_of("alliance")  # those of the opposing side
board.zones_of_control_against("alliance")
board.movement_of(hexagon)  # the points of the placed piece
board.moves(hexagon)  # its destination squares, zones of control included
board.move(origin, destination)  # recomputes, applies, and says whether it happened
```

It is the board that brings the three together: the placed piece gives its movement and its side,
the side gives the opponents, the opponents give the zones of control.

- **The placed piece prevails.** `moves(hexagon, piece)` accepts a piece as a second argument, but
  it only serves to question an empty square — to find out where a given unit would go if it were
  put there. With no piece at all, the flat rate applies and, for want of a side, nobody is an
  opponent.
- **A friendly square can be crossed but not taken.** The booklet allows the passage ("a unit may
  cross a square occupied by a unit of the same army") and forbids stacking: occupied squares are
  therefore removed from the destinations, not from the walk.
- **The counter lies askew, and stays that way.** `place` draws a **tilt** at random — a few
  degrees, `MAXIMUM_TILT` — which `tilts` returns per square and which `restore` takes back as it
  is. It is not a rule from the booklet, but it is part of the game state: it is saved with the
  positions, and it only changes on a move, since `move` places the piece again. A board read back
  does not replay that draw — otherwise the pieces would spin at every page reload.

### Reading a movement computation — the debug trace

`moves` returns a list of squares and says nothing of how it got there. On the module's own logger
it tells the whole of it, step by step: the piece and its budget, what the walk was told to avoid,
and one line per square it reached — its distance from the origin, its terrain, and the reason it
is **not** offered when it is not.

```
moves from 6,5,-11: elfes-01-5-infanteries (alliance), movement points: 4
moves from 6,5,-11: enemy squares refused: 1, under an enemy zone of control: 6
moves from 6,5,-11: squares reached by the walk: 41, free to be taken: 40
moves from 6,5,-11:   5,5,-10 at 1 (plaine)
moves from 6,5,-11:   5,6,-11 at 1 (plaine) - occupied by a friend: crossed, not taken
moves from 6,5,-11:   6,4,-10 at 1 (plaine) - under an enemy zone of control: entered, not left
```

When both apply to a square — a friend standing in an enemy zone — the line says the zone: it is
the zone that stops the walk there, the friend only keeps the square from being taken.

It is **the engine's logger and not the game log**: `tenebrae.engine.board`, where the player's
column reads `tenebrae.log` (`tenebrae/application/logs/battle_log.py`). Nothing of it reaches the
browser, which is the point — a move is recomputed at every click, and by the AI for every unit of
its turn.

The engine chooses no path: it is the application that gives this logger its file,
`logs/movement.log`, wired by `create_app` (`application/logs/movement_log.py`) and **open at
DEBUG** — there is no switch to find. Read from an interpreter with no application around, the
logger falls back to the root's level and says nothing, and `moves` does not even compose its lines
— `LOG.isEnabledFor` guards them:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

What it does **not** give is the cost paid for each square: `Hex.moves` walks with them and keeps
none — it returns the squares alone. The distance shown is the distance as the crow flies, which is
what a road or a wood makes differ from the cost.

## The scenarios

```python
from tenebrae.engine.scenario import scenario

war_of_the_dwarves = scenario(4)  # read from tenebrae/scenarios/scenario-04-….json
war_of_the_dwarves.armies  # one entry per player: side, instruction, anchor, magic
war_of_the_dwarves.sides  # ('alliance', 'tenebres')
war_of_the_dwarves.max_turns  # None: until one side is exterminated
war_of_the_dwarves.enabled  # True: a new game may be opened on it
war_of_the_dwarves.placement  # "q,r,s" → piece key
len(war_of_the_dwarves)  # 48 units
war_of_the_dwarves.board()  # a fresh Board, each piece on its square
```

The booklet describes a set-up in a sentence — "the dwarf army masses south of the volcano of Toth"
— and never says which counter goes on which square. The step from the sentence to the hexagons was
taken once and for all, outside the code, and lives in `tenebrae/scenarios/*.json`: **the engine
only reads that file**. The format, the detail of scenario no. 4 and the caveats that go with it are
in `tenebrae/scenarios/README.md`.

A file may be **withdrawn** from the set-ups a new game can be opened on by writing `"enabled":
false` into it by hand: `enabled_scenarios()` gives number → scenario for those still offered, and
that is what the application's `/game/scenarios` serves. The field is absent from every file
written before it existed and read as `True` there, so nothing had to be added to the scenarios
already fixed. Every call reads the files again — the field is honoured without a restart — and
disabling withdraws a scenario from the **new** games only: a game under way on it goes on, and
`scenario(number)` still reads it.

`board()` returns a **fresh** `Board` at each call: two games do not share their positions. A piece
key unknown to the catalogue, or a square off the map, stops the read — better a refused scenario
than an army quietly cut short.

The engine also **composes** one: `compose(name, placement, max_turns, source)` assembles the values
of a new file from `"q,r,s" → piece key` — the armies derived from the pieces placed, alliance
first, the next free number after the booklet's five —, and `path_for(number, name)` names the
file. `recompose(existing, name, placement, max_turns)` does the same for a scenario already on
file: its number, source and `enabled` kept — a scenario disabled by hand and then edited on the
map stays disabled —, and what its armies carried that the map cannot give (`HAND_WRITTEN`:
instruction, anchor, magic potential, spellcaster) carried over for every side still present. A
composed scenario is enabled. Neither writes anything: the application's `/admin/scenarios` page does, into
`tenebrae/scenarios/`.

## Movement cost

After the booklet's *Terrain table* (`tenebrae/game_box/ave_tenebrae_regles_en.md`):

| Terrain | Entry cost |
| --- | --- |
| `plaine`, `village`, `ville`, `ile`, `tour` | 1 point |
| `bois`, `colline`, `ruines` | 2 points |
| `route` → `route` | ⅓ of a point ("ROUTES × 3") |
| `chemin` → `chemin` | ½ point ("CHEMINS × 2") |
| `lac`, `riviere`, `faille`, `fort`, `chateau` | impassable |
| `montagne` | impassable, except from a hill or another mountain, or by a way crossing it |

The way's rate holds only if it is followed from one square to the next: "if a unit has to take a
road during a move, and it is not on that road at the start of its move, it must first use the
number of movement points required by the nature of the terrain separating it from the road".

The counters run from 1 point (the protoplasmic demons) to 20 (the demigod Azolhim); 4 is the
commonest value, carried by 35 pieces. What that gives on the plain, in squares reached:

| Points | Squares reached on the plain |
| --- | --- |
| 2 — the Yzent ram | about twenty |
| 4 — the Empire's infantry | about sixty |
| 5 — the old flat rate | from 60 to 100 |
| 8 — the Reissland cavalry | over two hundred |
| 20 — the demigod Azolhim | a thousand, that is two hexagons of the map out of five |

In the heart of a wood, where each square costs 2 points, count three to four times fewer.

## The game phases

```python
from tenebrae.engine.phase import Turn

turn = Turn(("alliance", "tenebres"), {"alliance": "Nains", "tenebres": "Orques"})
turn.label  # "Phase de mouvement — Nains"
turn.phase_type  # "mouvement" — never "magie"
turn.allows_movement("alliance")  # True
turn.advance()  # steps to the Dwarves' combat; magic is stepped over by itself
turn.number  # 1, then 2 when the sequence comes round again
```

The booklet (`tenebrae/game_box/ave_tenebrae_regles_en.md`, "Game phases") fixes the order: each
player goes through **movement → magic → combat**, then it is the next player's turn, round and
round. `Turn` holds that cursor. The **magic phase is not implemented**: `advance()` skips it, it is
never the current one. `allows_movement` / `allows_combat` say whether a given side may act now —
that is what the application consults to block a move outside its phase.

`Turn` knows neither the board nor the pieces: it only orders the phases. The application keeps one
instance of it, reset at every load of the map, beside its `Board`.

## Combats

```python
from tenebrae.engine.combat import fight, in_range, resolve

in_range(attacker_hex, attacking_piece, target_hex)  # distance ≤ 1, or ≤ range if the piece fires
resolve([12, 4], defending_piece, defender_hex, roll=3)  # → "DE", "AE", "EX", "AR", "DR"
result = fight(board, target_hex, [attacker_hex], roll=3, casualties=casualties)
result.outcome, result.eliminated, result.ratio, result.die
result.retreats   # what each unit forced to fall back did (`retreat.py`)
result.moves      # [(origin, destination), …] — every unit that gave ground, in order
result.breakdown  # the computation piece by piece, or None if nothing could be resolved
```

The booklet's **Table I** (`§ Combats`) is transcribed as it stands in `TABLE_I`: the strength
ratio in columns (from 1-5 to 6-1), the die roll in rows. The attackers' `strength` is added up,
set against the defender's — **rounded in the defender's favour**, bounded — the die is rolled, and
the cell is read.

`strength` is **the only counter value combat consumes**; it serves both for attack and for
defence, as on the counter. The *Tableau des terrains* adds two modifiers, applied from the
**defender's** terrain: its strength is multiplied (× 2 in a village, ruins, a river, a lake; × 3
in mountains, a fort, a castle; × 2 in woods for Elves only), and the attacker gains **+ 2 on the
die** if the defender holds a hill or a wood.

Chance stays at the edge of the engine: `roll` is **passed as an argument**, never drawn here. It
is the application that rolls the die (`app.roll_the_die`), which lets the tests fix it.

### The breakdown of the computation

The ratio cannot be read off the board: between the strength printed on the counters and the Table
I column, the defender's terrain plays **twice**, and nothing shows it once the combat is resolved
— a 12 against an 8 gives 1-1 on the plain and 1-2 in the mountains. `RatioBreakdown` therefore
keeps everything that went into the computation:

```python
breakdown = result.breakdown
breakdown.strengths            # [12, 8] — each attacker's strength, not only their sum
breakdown.attacking_strength   # 20
breakdown.target_strength      # 8, as it is on the counter
breakdown.terrain              # "montagne", the defender's terrain
breakdown.multiplier           # 3
breakdown.defending_strength   # 24
breakdown.roll                 # 4, the die as it fell
breakdown.die_bonus            # 0 (2 in woods or hills)
breakdown.die                  # 4, the die as the table reads it — added, then brought between 1 and 6
breakdown.ratio, breakdown.column, breakdown.outcome
```

`break_down(...)` builds it, and it is **the only place in the module where the defender's terrain
is consulted**: `resolve` and `fight` both go through it, and therefore cannot say two different
things about it. `result.ratio` and `result.die` are the breakdown's.

**What is known before the die**, and what the die adds, are two classes and not one.
`StrengthRatio` is the weighing — the strengths, the defender's terrain and its multiplier, hence
`attacking_strength`, `defending_strength`, `column` and `ratio`; `RatioBreakdown` **is one**, with
the roll and the terrain's die bonus on top, hence `die` and `outcome`. A weighing becomes a
breakdown by `with_the_die(die_bonus, roll)`, and by nothing else.

```python
weighed = combat.weigh(board, target_hexagon, attacker_hexagons)   # None: nothing to weigh
weighed.ratio, weighed.attacking_strength, weighed.defending_strength
weighed.outcomes        # ("DR", "DR", "DR", "DR", "DR", "AR") — one per face of the die
weighed.die_read_at(1)  # the row of Table I that face is read on, the terrain's bonus counted
```

`outcomes` lists the **faces of the die**, not the rows of the table. On a hill the ground adds 2
to the throw, so a 1 is read on the third row and three of the six faces on the sixth: the row read
as it stands would announce outcomes that cannot happen there. The die bonus therefore belongs to
the weighing — the ground gives it, not the throw — and `RatioBreakdown` adds only the roll.

`weigh` is the **one** place where a combat's forces are collected off the board — an attacker with
no legible strength does not count, an absent target or one with no legible strength is no combat
at all — and `fight` starts there. That is what lets the game show a ratio **before** the attack is
ordered (the toolbar's `Ratio : 3/1 (36/12)`, `GET /combat/ratio`) without the forecast and the
resolution being free to disagree: they are the same weighing, read once.

The engine builds **no sentence**: it returns numbers and a terrain name. Putting it into French is
the application's business (`describe_the_ratio` in `tenebrae/application/logs/combat_sentences.py`), which makes it
the log line `Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4`.

**The five outcomes change the board.** `fight` removes the pieces the three eliminations name —
`AE` (attacker eliminated), `DE` (defender eliminated), `EX` (the defender and part of the
attackers, see below) — and makes the units fall back
on the two retreats, `AR` and `DR`, which are a rule of their own: `retreat.py`, below. Whichever
way a square is emptied, it comes back in `result.eliminated`; the fall-backs themselves are in
`result.retreats`, and the units removed from play are entered in the game's register of casualties
(`casualties.py`). Two exemptions from the booklet are applied before falling anybody back: "a unit
firing missiles can in no case suffer a retreat or exchange result" — read as covering the unit
that is firing, so an **attacker** that fires, never a missile unit assaulted in its own square —
and a defender in a fort or a castle does not suffer `DR`.

**The advance after combat is played, on demand.** The booklet: "the attacking unit may, if it
wishes, occupy the hex abandoned by the defender, and this without regard to zones of control or to
its own movement limits", the decision being "announced immediately after the combat". `fight`
therefore takes it as an argument — the player has announced it by pressing `Attaquer et avancer`
rather than `Attaquer` — and `advance_after_combat` plays it **last**, once the square has been
cleared or given up, moving the counter by hand rather than through `Board.move`, which would weigh
the zones of control and the movement points the booklet sets aside. `result.advance` carries
`(origin, destination)`, and `square_after` follows it, so the combat register counts the unit on
the square it took. Two readings, both in the caveats below: which square, and which unit.

**The exchange takes as few attackers as it can.** The booklet has `EX` remove the defender "along
with attacking units totalling a strength at least equal"; **which** units it leaves open, and
`exchanged_attackers` reads it as *the fewest counters that reach that total*. Taking the strongest
first gives exactly that minimum — no *k* counters can total more than the *k* strongest — and ties
go by square key. So a dwarf of 12 answers for an archer of 2 on its own, and the two dwarves
beside it walk away; five elves of 7 against an orc of 8 lose two of their number and no more.

Three things follow. The strength to reach is the defender's **as printed on its counter**: the
terrain multiplier is what the ratio is worked out on, and an exchange trades units, not positions.
A unit that fires and a unit with no legible strength are never picked — the first is exempt from
the exchange, the second cannot help reach a total. And the reading has a price: the fewest
counters are the biggest ones, so a general standing among its infantry is what an exchange takes,
where counting strength rather than counters would have spent the infantry instead.

### Retreat or elimination — `retreat.py`

```python
from tenebrae.engine.retreat import fall_back, fall_back_together

outcome = fall_back(board, hexagon)          # the board is modified in place
outcome.moves          # [(origin, destination), …] — the retreating unit first, its pushes after
outcome.destination    # where it got to, or None
outcome.eliminated     # the square it fell on, for want of anywhere to go
outcome.pushed         # how many friends had to give way
```

> A unit that finds itself unable to fall back (presence of a lake, a river or an enemy zone of
> control) is removed from play, unless it is surrounded by friendly units. In that case, it pushes
> one of those units and takes its place. This simultaneous falling back of one or more units must
> make the retreating unit fall back by seeking the least movement and by pushing back as few
> friendly units as possible.

Three rules in one sentence, and the third is a search: pushing the nearest friend may cost three
displacements where pushing another would cost one. `shortest_chain` therefore looks for the whole
chain and not its first link — a **breadth-first walk** from the retreating unit, hopping from
friend to friend, stopping at the first free square that can be stood on. A breadth-first walk
finds the shortest chain, and a chain of *k* links is *k* units falling back, the retreating one
included: the same walk satisfies "the least movement" and "as few friendly units as possible" at
once, without weighing one against the other. Ties are broken by square key, as everywhere in the
engine: two identical games fall back identically.

A square can be stood on if it is **on the map**, habitable — `UNINHABITABLE`, the engine's reading
of "a lake, a river", the Rift of Tsaroth included — and free of enemy control. Nothing else: a
retreat is not a movement, it spends no points, so terrain cost and the mountains' access rule have
no say in it.

`fall_back_together` makes a whole group give ground — the attackers of an `AR` — one after
another, in square order, each seeing the board as the one before it left it.

### The fallen — `casualties.py`

```python
from tenebrae.engine.casualties import Casualties

casualties = Casualties()
casualties.record(hexagon, piece, taken_by="tenebres")
casualties.points_taken_by("tenebres")   # the booklet's total
casualties.points_lost_by("alliance")    # the same count, read the other way
```

> Eliminated units are kept by the player who eliminated them, to establish their total of points at
> the end of the game.

The booklet counts them for the **eliminator**; a unit is also, and as plainly, a loss for the army
it came from. The register therefore keeps the fact and not the reading of it: each entry says
which piece fell, on which square, on which side it fought and which side took it. It is the third
thing a game keeps beside its board, along with the turn and the combat register, and it is kept
the same way — a plain object, serialised into the saved game by `repositories/game.py`, knowing
nothing of MongoDB. A unit has no identity of its own here, so an entry names the piece and the
square, and nothing more.

### One combat per unit and per phase

The booklet limits each unit to **one attack per phase** — alone or within a group of attackers —
and each target to **one attack per phase**, even by different attackers. `CombatRegister` is the
register that keeps that count:

```python
from tenebrae.engine.combat_register import CombatRegister

register = CombatRegister()
register.can_attack("1,26,-27")  # True
register.record(["1,26,-27"], "2,26,-28")
register.can_attack("1,26,-27")  # False — it has had its turn
register.can_be_targeted("2,26,-28")  # False — it has been taken
register.reset()  # new combat phase: everyone is free
```

Three choices read in it:

- **It keeps squares**, as "q,r,s" keys, and not piece keys. One counter stands for several units
  and `CATALOGUE` returns only one object for it; the square designates only one. The only thing
  that moves a unit during a combat phase is a fall-back, and the caller enters the square it holds
  **after** the combat — `CombatResult.square_after`, which follows a unit through the retreats of
  its own combat. Without that, the register would mark a square its unit has left (see the
  caveats).
- **A combat counts as soon as it is fought**, whatever its outcome: a retreat engages its units
  just as much as an elimination — a unit that gave ground has had its turn.
- **It knows nothing of the turn nor of the board** — it is the caller that empties it. The
  application does so at every phase change (`POST /phase/next`), which covers moving from one
  combat phase to the other as well as the next turn.

## The artificial opponent — `ai.py`

```python

from tenebrae.engine import ai

ai.play_turn(board, turn, register, roll=roll_the_die)  # movement, combat, play handed back
```

The booklet assumes two players around the map; `ai.py` takes the place of the second. It only
**chooses**: every move goes through `Board.move`, every combat through `fight`, every availability
check through `CombatRegister` — no rule is duplicated there, and an illegal decision is refused as
it would be for a human.

The strategy comes down to three points:

- **Targeting is shared** by movement and combat: `target_priority` sorts the opposing squares by
  distance as the crow flies, then by effective defending strength — the counter's strength
  multiplied by the terrain occupied — then by square key. That is where a future difficulty
  setting would live: changing that sort changes the whole AI.
- **Each unit marches to its engagement range** (`combat_range`: contact, or the firing range) and
  stops there — an archer in position does not stick to its target, an infantry in contact stays
  there.
- **The attacks concentrate**: every available unit within range of a target engages it together,
  in a single combat. Below parity (`MINIMUM_RATIO`, column 1-1 of Table I), the AI declines —
  that is the only difficulty knob.

`play_turn` plays the movement phase, steps over the phase as a player would — `Turn.advance()` and
the combat register emptied — plays the combat phase, and hands play back. The die stays at the
edge of the engine: `roll` is a **callable**, called once per combat fought. Every tie-break is
made by square keys: at equal die, two identical games replay identically — that is what makes the
AI testable (`tests/engine/test_artificial_opponent.py`).

**The turn can be watched as it is played.** `play_turn` takes two optional callables — `moving`,
called with `(origin, destination)` the moment a move is applied, and `fighting`, called with
`(target, attackers, result)` the moment a combat is fought — so that a caller sees the turn go by
rather than only the board it left behind. The board is already moved when a watcher is called: a
caller pushing a position from there pushes the one just reached. What a watcher does — log the
action, push it to a browser, wait between two — is the caller's business: nothing here waits for
anything, or knows who is watching. Omit them and the AI plays exactly the same turn.

On the application's side, the AI occupies its seat under the `AI_PLAYER` sentinel (`"ia"`, which
no Discord identifier — strings of digits — can carry) and is displayed under `AI_NAME`. The
engine, for its part, knows nothing of this: `play_turn` plays the active side, whichever it is.

## The end of a game — `victory.py`

```python

from tenebrae.engine import victory

victory.annihilated_sides(board, ("alliance", "tenebres"))   # → ["tenebres"]
```

The booklet's "Object of the game": *"To crush the opponent by annihilating their troops; or else
to fulfil the scenario's victory conditions."* The second half is out of reach — the conditions
differ from scenario to scenario, several count ground held or a capital taken, and none is
transcribed — so what is held here is the first, which every scenario shares: **a side with no unit
left on the board has been crushed.**

`troops_of` lists the squares where a side still has a unit, and `annihilated_sides` names those,
among the sides a set-up fields, that have none. Troops, not pieces: a marker left on the map is
neutral and fights nobody, and a counter with nothing printed on it is not a unit (`Piece.is_a_unit`)
— a side can be annihilated with its markers still lying about.

**The module counts; it does not decide.** A board carrying no unit of either side is an empty
table as much as a mutual annihilation, and only the caller knows which: it is the application that
holds whether a game is being played at all (`A_GAME_IS_ON` in `current_game.py`).

## Caveats on the interpretation

As for the map and the counter inventory, doubts are kept, not settled.

- **The ruins' "× 2" is read as a surcharge**, whereas the same column of the table notes "× 2" for
  paths and "× 3" for roads, where the factor multiplies movement. Taking the ruins for fast
  terrain makes no sense; they are therefore treated like woods and hills, at 2 points.
- - **Rivers and walls are hexagon terrains**, not edges: that is how they were transcribed (see
  `tenebrae/game_box/map.md`). The bridges not being recorded, no river is crossable — including the
  access to Morgenstern.
- **The hills are an interpretation of the scan**, not a drawn terrain: access to the mountains
  depends directly on them. 42 of the 128 mountain hexagons border a hill or carry a way; the
  others stay unreachable on the ground.
- **Forts and castles are impassable**, for want of knowing whom they belong to: the booklet opens
  them "by combat or through allies", which requires a game state.
- **A unit placed on a lake, a river or the rift goes nowhere**: those terrains are no more
  occupied than they are crossed. Forts and castles, on the other hand, can be garrisoned: one
  leaves them, one does not enter them.
- **A fix bears only on the main terrain.** A road wrongly detected under a wood survives that
  wood's fix and stays practicable at ⅓ of a point: `map_fix.json` cannot remove a secondary
  element. That is settled in `tenebrae/game_box/extract_map.py`.
- **Combat reads only the strength.** `pions.json` also carries fire and range: `combat.py` uses
  them only for an archer's engagement range, never for fire resolved separately. A missile attack
  follows the same Table I as a melee.
- **Flight is not a rule**, only a number. Flying units move on the ground, with their ground
  movement; the bat, whose ground movement could not be read on the photograph, moves by its flight
  (2 points) under the same terrain rules. Flying over a lake or a mountain remains impossible.
- **Five movement values could not be read** on the counter's photograph (a cropped counter, an
  illegible figure): they are noted in `pions.json` and repeated in the caveats of
  `tenebrae/game_box/pions/README.md`.
- **Every unit exerts a zone of control**, whereas the booklet exempts leaders and spellcasters,
  demons and ordinary undead — only the three demon princes and the three lords on dragons exert
  one among them — and units holding a fortress. Those exceptions are readable in `pions.json`
  (`symbole`, `faction`): applying them would take only a filter, and not having done so yet is a
  choice.
- **"A zone is not exerted beyond a river, but crosses bridges."** Inapplicable as things stand:
  rivers are transcribed as hexagon terrains and not as edges, and no bridge is recorded. A zone of
  control therefore crosses everything.
- **The side is the faction's**, regardless of the scenario, and **the neutral side has no
  opponent**: flyers, conjurations and markers stop nobody and are stopped by nobody.
- **A scenario is only a starting position.** `scenario.py` places the pieces and stops there: no
  reinforcements, no victory condition. The game turn does now exist — `phase.py` — but it lives
  beside the scenario, not inside it, and the magic potential the booklet gives each side stays
  recorded without anything spending it.
- **Magic is not played.** The magic phase is provided for in the booklet's sequence;
  `Turn.advance()` steps over it without doing anything. Spells, magic potential, spellcasters and
  special abilities (fear, paralysis, protection rolls) are waiting.
- **The advance after combat occupies a square left by an elimination too, and that reading is
  ours.** The booklet names the **retreat** alone: "when the outcome of a combat forces the
  defender to retreat, the attacking unit may […] occupy the hex abandoned by the defender". A
  defender that is eliminated abandons its hex just as thoroughly, and `DE` and `EX` are read here
  as leaving it open to the same advance. Reading the sentence narrowly would make the attacker
  able to follow a unit that gives ground and not one it has just destroyed.
- **"The attacking unit" is one unit, and a group does not say which.** Several units make a single
  combat, and the booklet's advance is in the singular. The one that advances is the **first
  attacker designated** that can — still standing, and beside the square: a unit firing from three
  hexes away occupies nothing. The player therefore chooses it by the order of their clicks.
- **The rest of the combat modifiers are not played.** Neither cavalry charge (× 2), nor phalanx
  (× 3), nor day/night alternation: apart from the two exemptions from retreat — an attacker that
  fires, and a defender in a fort or a castle — the counter's strength and the defender's terrain
  are the only factors.
- **The missile exemption goes to the attacker, and that reading is ours.** "A unit firing missiles
  can in no case suffer a retreat or exchange result" is applied to the unit that is firing: an
  attacker, since `fires_missiles` holds a missile unit to fire in every combat it declares. A
  catapult assaulted in its own square therefore suffers `DR` like any other defender, and only a
  fort or a castle holds it. Reading the sentence the other way would make a missile unit
  unmovable by any assault, and would leave a `DR` the table gave without any effect at all.
- **A fall-back is read narrowly, and three readings are ours.** The booklet names three
  impediments and no more, so a unit falls back into any habitable square on the map that no enemy
  controls, whatever the terrain costs. From there: the ban on falling back into an enemy zone of
  control **does not lift because a friend is standing there**, so such a friend is not pushed
  either; the "simultaneous falling back" of a group is played one unit after another, in square
  order, each seeing the board as the one before it left it; and a unit **already pushed** by a
  comrade's chain has given its ground and does not give it twice.
- **The fallen are kept, the victory is not counted.** `casualties.py` registers every unit removed
  from play and totals the strengths, for the eliminator as for the army that lost them; no
  scenario declares a winner on that total, and nothing reads it back yet.
- **One combat per unit and per phase, counted by square.** The rule is kept (see `CombatRegister`
  above), but the register designates units by their **square**, for want of a unit identity in the
  engine: one counter stands for all the units it represents — `orques-01-15-infanteries` is placed
  fifteen times in scenario no. 4 — and `CATALOGUE` returns only one object for it. The equivalence
  holds because nothing moves during a combat phase and the register is emptied between two; it
  would fall the day movement and combat mixed within the same phase.
- **Stacking is not handled beyond one unit per square**: the booklet allows 3 units in a town, a
  village or a citadel, and counts neither leaders nor magicians. The board places only one piece
  per square.
- **The zones of control weigh on movement and on retreat**, which is the whole of what the booklet
  gives them here: the ban on falling back into them, and the unit eliminated for want of anywhere
  else, are applied (`retreat.py`). The invisibility that ignores them waits on the special
  abilities; every unit remains a ground unit.
- **The AI marches as the crow flies.** `moves()` returns the reachable squares, not the cost of
  paths; the AI therefore chooses the square that reduces the cube distance, which can make it
  stall against a lake instead of going round it the short way. It plays neither withdrawal, nor
  garrison, nor magic — it advances, always — and its parity threshold is a choice of caution, not
  a rule from the booklet.
