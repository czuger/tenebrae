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
| `MongoGameRepository` | `repositories/game.py` | the most recent game prevails; the previous ones stay in base |
| `NullGameRepository` | `repositories/game.py` | keeps nothing: the game state already lives in the server's module globals |
| `MongoPlayerRepository` | `repositories/player.py` | one document per known Discord account |
| `InMemoryPlayerRepository` | `repositories/player.py` | the accounts of the current run; keeping nothing would forbid playing |

It is `create_app` that chooses the pair, from `PERSISTENCE` — and the routes know nothing of that
choice.

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

## The scenarios

```python
from tenebrae.engine.scenario import scenario

war_of_the_dwarves = scenario(4)  # read from tenebrae/scenarios/scenario-04-….json
war_of_the_dwarves.armies  # one entry per player: side, instruction, anchor, magic
war_of_the_dwarves.sides  # ('alliance', 'tenebres')
war_of_the_dwarves.placement  # "q,r,s" → piece key
len(war_of_the_dwarves)  # 48 units
war_of_the_dwarves.board()  # a fresh Board, each piece on its square
```

The booklet describes a set-up in a sentence — "the dwarf army masses south of the volcano of Toth"
— and never says which counter goes on which square. The step from the sentence to the hexagons was
taken once and for all, outside the code, and lives in `tenebrae/scenarios/*.json`: **the engine
only reads that file**. The format, the detail of scenario no. 4 and the caveats that go with it are
in `tenebrae/scenarios/README.md`.

`board()` returns a **fresh** `Board` at each call: two games do not share their positions. A piece
key unknown to the catalogue, or a square off the map, stops the read — better a refused scenario
than an army quietly cut short.

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
result = fight(board, target_hex, [attacker_hex], roll=3)
result.outcome, result.eliminated, result.ratio, result.die
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

The engine builds **no sentence**: it returns numbers and a terrain name. Putting it into French is
the application's business (`describe_the_ratio` in `tenebrae/application/app.py`), which makes it
the log line `Rapport 2-1 : attaque 12 + 8 = 20 contre défense 8 × 3 = 24 (montagne) — dé 4`.

**Only three outcomes change the board**, and `fight` applies them by removing pieces: `AE`
(attacker eliminated), `DE` (defender eliminated), `EX` (both). `AR` and `DR` — the retreats — are
read but left without effect, for want of a retreat rule. See the caveats below.

### One combat per unit and per phase

The booklet limits each unit to **one attack per phase** — alone or within a group of attackers —
and each target to **one attack per phase**, even by different attackers. `CombatRegister` is the
register that keeps that count:

```python
from tenebrae.engine.combat import CombatRegister

register = CombatRegister()
register.can_attack("1,26,-27")  # True
register.record(["1,26,-27"], "2,26,-28")
register.can_attack("1,26,-27")  # False — it has had its turn
register.can_be_targeted("2,26,-28")  # False — it has been taken
register.reset()  # new combat phase: everyone is free
```

Three choices read in it:

- **It keeps squares**, as "q,r,s" keys, and not piece keys. One counter stands for several units
  and `CATALOGUE` returns only one object for it; the square designates only one. Nothing moves
  during a combat phase, so the equivalence is exact for as long as the register lives (see the
  caveats).
- **A combat counts as soon as it is fought**, whatever its outcome: a retreat, which the engine
  leaves without effect, engages its units just as much as an elimination.
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

On the application's side, the AI occupies its seat under the `AI_PLAYER` sentinel (`"ia"`, which
no Discord identifier — strings of digits — can carry) and is displayed under `AI_NAME`. The
engine, for its part, knows nothing of this: `play_turn` plays the active side, whichever it is.

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
- **Combat stops at the three eliminations.** `AR` and `DR` — the retreats — are not played, so
  there is no retreat, no elimination for want of a retreat, and no advance after combat. `EX`
  removes **all** the attackers, without the booklet's "strength at least equal" filter. Neither
  cavalry charge (× 2), nor phalanx (× 3), nor day/night alternation, nor missile troops' immunity
  to retreat: the counter's strength and the defender's terrain are the only factors.
- **One combat per unit and per phase, counted by square.** The rule is kept (see `CombatRegister`
  above), but the register designates units by their **square**, for want of a unit identity in the
  engine: one counter stands for all the units it represents — `orques-01-15-infanteries` is placed
  fifteen times in scenario no. 4 — and `CATALOGUE` returns only one object for it. The equivalence
  holds because nothing moves during a combat phase and the register is emptied between two; it
  would fall the day movement and combat mixed within the same phase.
- **Stacking is not handled beyond one unit per square**: the booklet allows 3 units in a town, a
  village or a citadel, and counts neither leaders nor magicians. The board places only one piece
  per square.
- **The zones of control weigh only on movement.** Their other effects — the ban on retreating into
  them, the unit eliminated for want of a retreat, the invisibility that ignores them — assume a
  retreat rule that does not exist. Every unit remains a ground unit.
- **The AI marches as the crow flies.** `moves()` returns the reachable squares, not the cost of
  paths; the AI therefore chooses the square that reduces the cube distance, which can make it
  stall against a lake instead of going round it the short way. It plays neither withdrawal, nor
  garrison, nor magic — it advances, always — and its parity threshold is a choice of caution, not
  a rule from the booklet.
