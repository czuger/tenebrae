# `tenebrae/scenarios/` — the set-ups, fixed once and for all

The booklet describes each scenario in a sentence — "the dwarf army masses south of the volcano of
Toth" — and never says which counter goes on which square. The step from the sentence to the
hexagons is a work of interpretation: it was taken **once**, and its result lives here, one JSON
file per scenario. The engine only reads it (`tenebrae/engine/scenario.py`), and the application
lays it out on the map when `/` is loaded.

That is what replaced the random draw of ten counters: moves are now exercised on a known position,
the same at every reload.

The files and their field names are French, like all the game data: the engine reads them as they
stand.

| File | Scenario |
| --- | --- |
| `scenario-04-la-guerre-des-nains.json` | no. 4 — La guerre des nains: Dwarves against Orcs |
| `scenario-06-bataille-de-reissland.json` | no. 6 — Bataille de Reissland, composed on the map |

Scenarios 1, 2, 3 and 5 of the booklet are not fixed yet. Scenarios composed on the map, on the
application's `/admin/scenarios` page, take the numbers from 6 on (see "Scenarios composed on the
map").

## The format

Naming: `scenario-NN-<slugified-title>.json`, `NN` on two digits — that is where
`tenebrae.engine.scenario.available_scenarios()` takes the number from.

| Key | Contents |
| --- | --- |
| `numero`, `nom` | the scenario's number in the booklet and its title |
| `source` | where to read the scenario's text, in the transcription of the rules |
| `nombre_de_tours` | how many turns the game lasts; absent or `null` for "an undetermined number of turns", as the booklet says of scenario no. 5 — read as `Scenario.max_turns`, which nothing in the engine enforces yet |
| `enabled` | whether a new game may be opened on the scenario; absent means yes (see "Withdrawing a scenario") |
| `armees` | one entry per player, in player order (see below) |
| `placement` | `"q,r,s"` → piece key: **the set-up itself**, one unit per square |

Each `armees` entry carries the `joueur`, their `camp` (`alliance` / `tenebres`, the one
`tenebrae.engine.piece` gives to the faction), the name of the `armee`, the booklet's `consigne`
copied word for word, the `ancre` — the hexagon the deployment starts from, the one the instruction
designates —, the number of `unites` placed, the side's `magie` potential and its `jeteur_de_sorts`
(`null` if no counter represents it).

The piece keys are those of `tenebrae/game_box/pions/pions.json`; a counter named several times is
placed that many times, one square each — the box really does carry 15 orc infantry counters under a
single photograph.

## Withdrawing a scenario

`"enabled": false`, written **by hand** into a file, takes a scenario out of the chooser the table
dialog offers when a new game is started (`/game/scenarios`). There is no button for it: it is a
field of the file, edited like the instructions and the anchors.

- **Absent means enabled.** None of the files here carries the field, and none had to: a scenario
  is offered until it is disabled.
- **The files are read again at every request.** Setting the field takes effect at once — no
  restart, no reload of the page: the chooser is filled when the dialog opens, and the server
  checks the number again when the game is asked for.
- **A game under way is not interrupted.** Disabling withdraws a scenario from the **new** games:
  the game being played on it goes on, and reloading `/` resumes it as it stood.
- **It stays editable on `/admin/scenarios`.** Its chooser lists it with `(désactivé)` beside its
  name — hiding it would lock the file away, since re-enabling it means opening it — and a save
  keeps the field as it was.

## Scenarios composed on the map

The application's `/admin/scenarios` page (see `tenebrae/application/README.md`) lays pieces on the
map and saves the result here, as a new file in the same format — the only case where a program
writes into this directory. The values are assembled by `tenebrae.engine.scenario.compose`:

- **The number** is the next free one after the booklet's five and the files present: 6 for the
  first, whatever booklet scenarios are fixed or not. The booklet's numbers stay theirs.
- **The armies are derived from the pieces placed**: one entry per side present, alliance first,
  `armee` named after its factions ("Nains", "Elfes et Nains"), `unites` counted. What the map
  cannot give stays `null`: `consigne`, `ancre`, `magie`, `jeteur_de_sorts`. The neutral pieces —
  spellcasters, conjurations, markers — are placed but belong to no army.
- **The placement is written side by side**: the alliance, then the darkness, then the neutrals.
- `source` says the page and the day; `nombre_de_tours` is what was asked for when saving;
  `enabled` is `true` — a scenario just composed is offered.

A composed file is played like a fixed one; adjusting it by hand afterwards — an instruction, an
anchor, a magic potential — is the way to make it a scenario of the booklet.

## Scenarios edited on the map

The same page opens any file here on `/admin/scenarios/<number>/edit` — a fixed one as well as a
composed one — and rewrites it on save, through `tenebrae.engine.scenario.recompose`:

- **The number, the `source` and `enabled` stay.** A new title renames the file; the old one is
  removed. A scenario disabled by hand and then edited on the map stays disabled.
- **The armies are derived again** from the pieces placed — `armee`, `unites`, `joueur` — but what
  was written by hand into an army whose side is still on the map is kept: `consigne`, `ancre`,
  `magie`, `jeteur_de_sorts`. A side that left the map loses its entry; a side that arrives gets
  one with those four at `null`.
- **A piece the page's palette does not offer** — an overview photograph, for instance — is not
  laid and would be dropped by a save; the page says so when it opens the file.

Editing scenario no. 4 this way keeps its instructions, anchors and magic potentials, but the
reading of the map documented below is then no longer what the file holds.

## Scenario no. 4 — La guerre des nains

> Afin de répondre aux raids incessants des orcs, le chef nain Grundt ordonna à son armée
> l'attaque immédiate de l'Orcreich et l'extermination totale des orcs.

48 units: **18 dwarves** (player 1, alliance) against **30 orcs** (player 2, darkness). The dwarf
army — 5 infantry, 4 crossbowmen, 4 heavy crossbowmen and 5 phalanxes — and the orc army
**without reinforcements** — 15 infantry, 5 cavalry, 5 archers and 5 mounted archers.

**Only the units the engine can play are placed.** Both sides' leaders and the mage Vorgtd stay in
the box: the engine gives them no effect — no command, no combat bonus, no rally, no spell — and a
unit that does nothing more than another has no business in a battle line. Both sides therefore
fight on equal terms, by counter and by terrain. The three corresponding counters
(`nains-05-2-leaders`, `nains-06-1-mage-vorgtd`, `orques-08-1-leader`) stay in
`tenebrae/game_box/pions/`: putting them back the day the engine gives them an effect will only take
adding them to the placement.

### The deployment

Both armies line up in the corridor of plain that runs from the lake, in the north, to the
southern plains, between the hills to the west and the mountain massif that closes the east from
column 52 on.

**The dwarves are in three ranks**, on a front line given by hand: the seven hexagons running from
`50,-7,-43` to `45,-8,-37`. The order along that line is the instruction's — *infantry first,
phalanx next*:

| Rank | What holds it |
| --- | --- |
| The front line | the 5 infantry from `50,-7,-43`, then 2 phalanxes as far as `45,-8,-37` |
| Second rank | the other 3 phalanxes to the west, 3 heavy crossbowmen to the east |
| Third rank | the 4th heavy crossbowman and the 4 crossbowmen |

The crossbowmen, a missile arm, are therefore **all behind every contact unit**: not one of them is
as close to the orcs as the least infantry or phalanx.

**The orcs are more intermingled**, but their order of battle reads from south to north:

| From the dwarves | What stands there |
| --- | --- |
| The front | 14 infantry in two ranks, plus a garrison in the fort at `51,-13,-38` |
| Behind | the 5 archers on foot, right against the second rank of infantry |
| Further on | the 5 mounted archers, making the link |
| The lake shore | the 5 cavalry, **all of them**, on row 8 |

Everything the dwarves have in front of them within 4 squares is therefore orc infantry; the ten
archers form a single block behind it; and the five cavalrymen are the only units on the board to
border the water — that is what tells them apart from the mounted archers, just behind them.

### The anchors

The `ancre` is not the centre of a circle: it is **the point the deployment starts from**, and both
are occupied.

| Anchor | Hexagon | What holds it |
| --- | --- | --- |
| South of the volcano of Toth (dwarves) | `50,-7,-43` | the first hexagon of the front line, an infantry unit |
| The Orcreich (orcs) | `51,-13,-38` | the fort, held by an infantry garrison |

The two fronts stay **3 squares** apart, exactly: the first turn is for marching, not fighting.
Each army is in one block — each unit touches at least one other of its side — and none is placed
in a dead end.

The dwarves hold 15 squares of plain and 3 of path. The orcs hold plain (15), the hills coming down
from the lake (8), the path crossing the Orcreich (6) and the fort at `51,-13,-38` — that fort is a
fix recorded by hand in `tenebrae/game_box/map_fix.json`.

### Caveats on this set-up

As elsewhere in the repository, uncertainties are kept, not resolved.

- **The hexagons are not in the booklet.** "South of the volcano of Toth", "inside the Orcreich":
  the anchors and the shape of both armies are a reading of the map, not a datum of the game.
  Another reading would give another, equally admissible deployment.
- **The dwarf front line was given by hand**, by its two ends, and the rest of the deployment hangs
  off it. It comes neither from the booklet nor from the map.
- **The leaders and the mage are set aside for want of an effect in the engine**, and not because
  the scenario refuses them: the booklet gives a leader to each side and Vorgtd to the dwarves.
- **The orc minor necromancer is not placed** either, but for another reason: the scenario gives it
  to player no. 2 (20 magic points) and **no counter represents it** —
  `tenebrae/game_box/pions/11-orques/` contains none, and `19-magiciens/` has only two overviews.
- **Both magic potentials stay noted** in `armees` (45 for the dwarves, 20 for the orcs) even
  though the `jeteur_de_sorts` of both sides is `null`: those numbers come from the booklet, and
  they are what will have to be spent the day magic is played.
- **The orc reinforcements stay in the box** (`orques-05` to `orques-07`): the scenario does not
  provide for them.
- **Magic is not played**: no spell, no spending, no phase that does anything with it. That is why
  the mage stayed in the box, and not the other way round.
- **The victory condition is not modelled** — "the winner is the one who exterminates the other":
  the engine resolves combats one by one, but never says that the game is over.

## Tests

`tests/engine/test_scenario.py`, from the repository root:

```
python3 -m pytest tests/engine/test_scenario.py
```

It exercises the reading of the files, the announced numbers against the counters actually placed,
the shape of the two deployments, and consistency with the map: every square exists, no unit on
impracticable terrain, and each has at least one square to go to. **A terrain fix that would put a
unit in a lake would therefore show up here**, and not mid-game.

The shape of the deployment is exercised as it was asked for, and not copied out: the test redraws
the dwarf line between its two ends (`cube_line`) instead of listing its seven keys, and then
checks the order of battle by distances — the crossbowmen behind the contact units, the orc
infantry in front of everything else, the archers in a single block behind it, the cavalry alone in
bordering the lake.
