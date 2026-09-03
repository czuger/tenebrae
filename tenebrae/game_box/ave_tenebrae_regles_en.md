# Ave Tenebrae

*A game by François Marcela-Froideval*

> English translation of the rules booklet (`ave_tenebrae_regles.pdf`, 16 pages), made from the
> French transcription kept beside it in `ave_tenebrae_regles_fr.md`. The two files mirror each
> other section for section: same headings, same tables, same order, so that a passage can be
> checked against the booklet by opening the French file at the same place. The original text is
> set in gothic type; its spelling was restored to modern French before translation. The
> illustrations are not reproduced; the tables are converted into Markdown tables.
>
> The translation follows the transcription faithfully, oddities included: where the booklet
> contradicts itself or is vague, the English says the same thing. Proper nouns keep their
> original form (Orvarth, Tsaroth, Ghaarth, Morgenstern, Orcreich, Reissland, Yzent, Val de
> Froy, Krak de Reiss). The names the code uses — the terrains of `carte.json`, the combat results
> of Table I — are given in brackets where they appear.
>
> The rules never detail the contents of the counter sheets: see `pions/README.md` for the complete
> inventory of the units, filed by faction and by purpose.

---

## Introduction

Ave Tenebrae is a strategic simulation of the fantasy kind, played by two players; but it can also
be played by up to four.

Dawn rises over the ruins of the third province of the Tharque Empire. All around you, flames and
heaps of corpses. The forts are thrown down, the villages razed, the forests ablaze: it is the end
of civilisation.

The black dawn rises, and already you hear in the distance the victorious troops hailing the
Magiocrat Ovarth, chanting two words that fill you with horror: "Ave Tenebrae". You, Commander in
Chief of the armies of the Empire, have failed. You could not hold back the howling hordes, the
demonic armies and the ceaseless flood of the undead. Because of you, the Empire, which can no
longer resist, is going to be wiped out, and your name will be cursed for ever by every descendant
of the Empire. Yet merciful Gods have taken pity on you and, slowly, a strange fog forms around you,
and through it, instinctively, you see your dead soldiers rise again, and slowly you see time run
backwards to the moment when the gates that vomited forth the foul armies of the Magiocrat close
again.

Around you everything is as it was before, and then you hear a mighty voice thunder in the sky: your
Gods, giving you one chance, the last. Time has been turned back and now you must succeed where you
had failed; but take care, for any failure will bring your annihilation for ever, because if the
Gods are sometimes merciful, they rarely forgive failure.

Dawn rises and with it, distant gates open. The howling horde draws near, but this time you are
ready.

---

# Rules

## Components

The game comprises a map; a rules booklet; several sheets of counters and a few play aids.

- **The map**: it represents part of the region of the Dreamrifts, controlled by the Magiocrat and
  the Empire, along with various small kingdoms or peoples.
  A grid of hexagons is overprinted on the map, which will ease the movement of the counters and
  the reckoning of distances. Each hexagon represents a distance of about 1 km.
- **The counters**: they stand for the various units that face each other on the map; each counter
  bears several indications that determine its various potentials: combat, movement, fire, firing
  range, special abilities, unit type, etc.

### Blank map

A blank hexagon sheet is supplied so that you can create your own battlefields for your own
scenarios. Other blank hexagon sheets are easily found in shops.

### Anatomy of a counter

```
        Special abilities
                 |
      +----------v----------+
      |   7      p      3   |  <- Attack and defence strength (left) / Movement (right)
      |      +---------+    |
      |      |   [X]   |    |  <- Identification (symbol of the unit type)
      |      +---------+    |
      |   7     (8)     3   |  <- Missile combat strength (left) / Missile range (right)
      +----------^----------+
                 |
     Flying movement (figure in brackets)
     (unless a letter: non-human type) or G: guard
```

| Position on the counter | Meaning |
| --- | --- |
| Top, centre | Special abilities (letter) |
| Top, left | Attack and defence strength |
| Top, right | Movement |
| Centre | Identification (symbol of the unit type) |
| Bottom, left | Missile combat strength |
| Bottom, right | Missile range |
| Bottom, centre (in brackets) | Flying movement — unless a letter: non-human type, or **G**: guard |

## Symbols

| Symbol | Meaning | Symbol | Meaning |
| --- | --- | --- | --- |
| ⊠ | Infantry | ⚔ (catapult) | Catapults |
| ▭ | Cavalry | ⊞ | Templars |
| ⧅ (rider + arrow) | Mounted archers | (rat) | Rats |
| ↗ (arrow) | Archers | (skull) | Skeletons |
| ↑↑↑ | Infantry (tridents) | (bat) | Bats |
| ↑ | Phalanx | (wolf) | Wolves |
| (winged creature) | Flyers | (crawling demon) | Protoplasmic demons |
| (light chariot) | Light chariot | ⑂ (trident) | Demons |
| (heavy chariot, framed) | Heavy chariot | (group of figures) | Population |
| (dragon) | Dragons | (ram) | Battering ram |
| (skull) | Zombies | ⚓→ | Crossbow |
| (ghoul's face) | Ghouls | ⚓⇉ | Heavy crossbow |
| ● | Earth | ▲ | Fire |
| ■ | Air | ⚡ | Water |
| **PA** | Paralysis | **D** | Rout |
| **M** | Vorgtd | (coat of arms) | Huluth |
| ● (solid disc) | Azolin (or Hazolin) | | |

---

## Phases of the game

### Placement of the pieces

This varies according to the scenarios (see scenarios).
Determine the placement yourself for your own scenarios.

### Game phases

The course of the game is divided into several turns, themselves divided into several phases in the
following order:

1. Movement phase of the 1st player
2. Magic phase of the 1st player
3. Combat phase of the 1st player (resolution of the combats)
4. End of the 1st player's actions
5. Movement phase of the 2nd player
6. Magic phase of the 2nd player
7. Combat phase of the 2nd player (resolution of the combats)
8. End of the 2nd player's actions

If there are more than 2 players, slot them into one of the two phases (see the Ave Tenebrae
scenario).

### Object of the game

To crush the opponent by annihilating their troops; or else to fulfil the scenario's victory
conditions.

---

## Movement

During their active phase, each player moves as many units as they wish, within the limit of the
movement points allotted to each unit.

The number of points needed to move one hex varies with the nature of the terrain (shown by a colour
on the map). Access to the mountains requires passing through the hill hexes that border them. Where
there are no hill hexes, a mountain range is inaccessible.

Units enter towns freely, provided the hexes that border them are themselves accessible.

If a unit must take a road during a move, and if it is not on that road at the start of its move, it
must first spend the number of movement points required by the nature of the terrain separating it
from the road.

During a move, a unit may pass through a hex occupied by a unit of the same army.

## Zones of control

Each unit exerts a particular influence on the six hexes surrounding the one it occupies: these six
hexes make up its "zone of control".

It has particular properties:

- a unit may enter an enemy zone of control without spending extra points, but it is not allowed to
  move within it: it must therefore stop as soon as it has entered;
- one can only pass from one zone of control to another after leaving the first;
- a zone does not extend across a river, but does cross bridges;
- it is forbidden to retreat (see combats) into an enemy zone of control.

**Example:** unit **C**, standing in the zone of control of **A**, cannot reach hex **X2** by way of
hex **X1**, which is also in the zone of control of **A**. It will have to leave the zone, go round
**X1** and enter the zone again at **X2**. It will therefore spend 4 movement points instead of 2.

- Units placed in fortresses have no zone of control.

## Stacking

It is not possible to place more than one unit in the same hex; except for town, village or citadel
hexes, which may hold 3 units.

Leaders and magicians do not count as units and may therefore be stacked without difficulty.

However, no more than 2 leaders or spellcasters may be stacked with a unit (except in the case of a
castle, a citadel or a town).

---

## Combats

To give battle, the attacking unit must be at a certain distance from the attacked unit. Namely:
adjacent hexes for infantry and cavalry, one or two hexes apart for archery. Several units of the
same army may attack a single enemy unit; each attacking unit having to meet the proximity
conditions.

**Table I: results table**

| Die \ Ratio | 1-5 | 1-4 | 1-3 | 1-2 | 1-1 | 2-1 | 3-1 | 4-1 | 5-1 | 6-1 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **1** | AR | AR | DR | DR | DR | DR | DR | DE | DE | DE |
| **2** | AE | AR | AR | DR | DR | DR | DR | DR | DE | DE |
| **3** | AE | AE | AR | AR | DR | DR | DR | DR | DE | DE |
| **4** | AE | AE | AR | AR | AR | DR | DR | DR | DR | DE |
| **5** | AE | AE | AE | AR | AR | AR | DR | DR | DR | EX |
| **6** | AE | AE | AE | AR | AR | AR | AR | EX | EX | EX |

The codes are the booklet's own (*attaquant éliminé*, *attaquant recule*, *défense éliminée*,
*défense recule*, *échange*) and are kept as they stand: the engine uses them.

- **AE** (attacker eliminated): the attacking units are removed from play.
- **AR** (attacker retreats): the attacking units fall back one hex.
- **DE** (defender eliminated): the defending units are removed from play.
- **DR** (defender retreats): the defending units fall back one hex.
- **EX** (exchange): the attacked units are removed from play, along with attacking units
  totalling a strength at least equal.

Combat being declared, the points of the attacking units are added up, then the points of the
defence. The ratio of the points is worked out, expressed by placing the attacker as numerator and
the defender as denominator. This strength ratio can run from 1/5 (that is, 1 against 5) to 6/1 (6
against 1). The ratio is always rounded in the defender's favour. For example: 10/4 counts as 2
against 1. The attacker then throws the die. The number obtained is modified, where applicable, by
the nature of the terrain (see terrain effects on combat) or by certain conditions specified further
on. On Table I, at the crossing of one of the columns (showing the strength ratio) and one of the
rows (matching the result of the die roll) is given the outcome of the combat.

Combats must obey the following rules:

- a given unit may only be attacked once during the same phase;
- a given unit (or group of units) may only attack a single enemy unit during the same phase;
- several units of the same army may join to attack an enemy unit, but this action makes up a
  single combat, and so involves a single die roll;
- the results of the combat apply immediately, before the start of the next phase.

A unit firing missiles can in no case suffer a retreat or exchange result; the same holds for a mage
casting a ranged attack spell.

A unit defending in a castle or a citadel does not suffer **DR** results (defender retreats);
however it may suffer them if it is defending a rampart, in which case the enemy unit may gain a
footing on the rampart during its advance after combat.

### Advance after combat

When the outcome of a combat forces the defender to retreat, the attacking unit may, if it wishes,
occupy the hex abandoned by the defender, and this without regard to zones of control or to its own
movement limits. The decision whether or not to occupy the opponent's hex must be announced
immediately after the combat.

### Retreat or elimination of a unit

A unit that finds itself unable to fall back (presence of a lake, a river or an enemy zone of
control) is removed from play, unless it is surrounded by friendly units. In that case, it pushes one
of those units and takes its place. This simultaneous falling back of one or more units must make
the retreating unit fall back by seeking the least movement and by pushing back as few friendly
units as possible.

Eliminated units are kept by the player who eliminated them, to establish their total of points at
the end of the game.

---

## Special abilities

On certain counters a small letter appears at the top, between the two figures of the counter's
first line. This letter represents the special ability that this monster possesses: these special
abilities are a possibility belonging to the unit, applicable constantly until that unit is
eliminated. The various special abilities are fear, paralysis (for the Ghouls) or the use of magic.
These abilities will always be treated like magicians' spells, and are applied only in the event of
combat or of an advance of these units towards a defender.

Note that certain cavalry counters bear the fear symbol; this serves to reflect the terrible effect
that the sight of an extra-heavy cavalry charge produces on defending units.

But phalanxes, the other heavy cavalry units and magicians are not affected by this possibility.
Demons and the undead are, for their part, immune to this kind of fear.

### Special abilities (dragons)

Dragons may, once only per unit, over the whole course of the battle, make an attack at 4 against 1
whatever the strength of the defending unit. All results apply.

## Saving throws

Certain units must, in particular circumstances, roll saving throws. These saving throws symbolise a
unit's resistance or survival in the face of a magical attack or of fear. Saving throws differ with
each type of unit. The saving throws are as follows:

| Unit type | Saving throw |
| --- | --- |
| Non-humans | 1, 2, 3, 4 succeed |
| Humans | 1, 2, 3, 4, 5 succeed |
| Mages and Elves | roll 2 dice; on a double (2-2, 4-4, 1-1, etc.) the saving throw is failed |
| Dragons and conjured creatures | as humans |

If the saving throw is failed, apply the result of the spell or of the special ability in full.

Paralysed units have no saving throws against eradicate spells or walls of mist, and are
automatically destroyed by fires.

Templar units are not affected by the paralysis of the undead (Ghouls).

---

# Special units

## Demons

*(Five counters of Demon Princes illustrated, engraved with cabalistic signs.)*

Some decades ago, Orvarth, to strengthen his power, made a pact with the seven demon princes; they,
in exchange for many sacrifices and for his soul, swore to help him make the black order reign on
Earth.

So that this should come to pass, Orvarth was given incantation formulas that allow him to command
the demons. These incantations break down into two rituals: the first frees the demonic legions
which, led by three major demons, will then carry out every wish of the Magiocrat. The second
incantation causes hordes of protoplasmic demons to spring from the chasm of Tsaroth; these, though
enormously slow and stupid, nonetheless have a very considerable power of destruction. Both rituals
must be performed in Orvarth's tower. It is chiefly this power over the infernal legions that makes
the mage Orvarth so feared and so dreaded by his contemporaries.

- **Invocations**: To invoke the demons, the Magiocrat must go to his tower. The invocation of the
  legions costs 100 magic points, which may only be spent by the Magiocrat. The invocation of the
  protoplasmic demons costs 50 magic points, which likewise may only be spent by Orvarth. Once
  activated, the demons will set off at the will of the player who invoked them.
- **Characteristics**: The legions will have the black roads as their starting points, whereas the
  protoplasms will appear along the whole length of the Rift of Tsaroth.

Apart from those with special abilities (fear), demons behave like normal units, except that they
exert no zones of control, though they suffer their effects.

There are three major demons, each represented by a counter engraved with a cabalistic sign. These
three counters are the only ones able to exert a zone of control, for they represent creatures with
a will of their own. There must always be three free hexagons between the demon units and the other
non-human units of the Mage's troops. The only exception: the undead, who, given their nature, may
mix with the demons on the battlefield without being in the least affected, and for good reason.
Conversely, the undead do not affect the demons.

However, the body of demons must stay united and always fight as a single block. The same holds for
the protoplasmic demons. If allied and non-human units (the Magiocrat's regular troops) intermingle,
treat the effects as for the undead.

- **Special rules**: If they wish to break the conjuration of the demonic legions, the magicians of
  the Empire must spend double the magic points needed to invoke them. The magicians need not be in
  a precise place; however, they must be within 10 hexes of the cohorts of the undead.

***

## Dragons

The forces of the Empire may, if they wish, ask for the help of the dragons that live within their
kingdom. For this, each turn, one of the Empire's magicians must spend 20 magic points (the energy
needed to call the dragons). From that moment, the player representing the Empire will have to roll
a 6-sided die. If a 1 comes up, the dragons will appear immediately at the edge of the map near the
capital. They possess several special abilities, fear and breath (see special abilities).

The Magiocrat's troops also have three dragons; they serve as mounts for the princes of the undead.
However, these dragons, less powerful than the golden dragons, have no special characteristic.

***

## The undead

*(Counters: **W**, Ghoul, Skeleton, Zombie.)*

The infernal pact that binds the Magiocrat to the powers of darkness gives him certain powers;
among them that of commanding the dead to leave their graves to carry out his wishes. For this, he
must perform a complicated ritual, in the middle of the Black Lake on Skull Island. On the chosen
day, at nightfall, the Magiocrat goes to the island; at midnight, he begins the great ritual and
utters the terrifying incantations that will open the "gates of death" and free from the ancient
ruins of the town of Ghaarth the cohorts of the undead, who from then on can only obey his almighty
will blindly.

- **Invocations**: To invoke the undead, the Magiocrat must go to the sanctuary of the dead, in the
  middle of the Black Lake. The invocation of the undead costs 80 magic points, which may only be
  spent by the Magiocrat. Once activated, the undead will set off at the will of the player who
  invoked them, from the ruins of the town of Ghaarth, on which their counters will appear. Apart
  from those with special abilities (fear and paralysis), the undead behave like normal units,
  except that they exert no zones of control, though they suffer their effects.

There are three lords of the undead, represented by a counter marked with a **W**. These three
counters are the only ones that may exert a zone of control, for they represent creatures with a
will of their own. There must always be three free hexagons between the undead units and the other
non-human units of the Magiocrat's troops (with the exception of the demons). If for any reason,
retreat or oversight, this case should arise, the troop (or troops) concerned would immediately
suffer intense fear; they would then be routed in the opposite direction, to the full extent of
their movement potential. Furthermore, the army corps of the undead can never be split: it must
always fight as one united block.

- **Special rules**: The undead can only fight at night; as soon as dawn breaks, their counters
  must be turned over (face down) on the precise spot where they stood before sunrise. The terrain
  is then considered normal (if it is plain = plain, if it is forest = forest). When night falls,
  the undead have the ability to reappear on the precise spot where they were (turn them face up)
  and to move and fight normally.
  To break the conjuration of these units, at some moment of the night the magicians of the Empire
  must be able to spend double the magic points needed to invoke them. They need not be in a
  precise place to do so; on the other hand, they must be within 10 hexes of the cohorts of the
  undead.
  For the special abilities, see the chapter "special abilities".

---

# Other units

## Cavalry

*(Counters: cavalry, mounted archers.)*

- It can in no case attack a citadel;
- The charge is a particular case of a unit's movement and combat strength: whenever a cavalry unit
  uses its movement potential to the full (6 hexes) in a straight line, and moreover the last hex
  it ends on is adjacent to an enemy unit, it is a charge. This doubles the cavalry's attack
  potential (4 × 2 = 8).

***

## Phalanxes

Phalanxes, thanks to their particular formation, have their defence potential tripled when they
suffer a cavalry charge. They are insensitive to the fear a heavy cavalry charge may cause.

***

## Non-humans

The magician uses many non-human troops to attack the forces of the Empire.

The non-human troops, whose different races are represented by counters of different colours, can in
no case be mixed and must fight by corps (units of the same colour). If, for any reason, these units
are mixed with other allied units, or if they are separated by more than 3 hexes from another unit
of their group, these units must then roll a saving throw against paralysis (identical to the
spell).

During the night, these units fight with a bonus of −1 to the die in attack.
During the day, however, they have a penalty of +1 to the die in attack.

***

## Templars

The Templars are immune to fear. As soon as they appear on the map, if there are demon or undead
units within 5 hexes, those units will immediately go and fight them, for, the Templars
representing Good in its essence, the demons have but one goal left: to destroy them. Likewise, the
Templars' target will be, before anything else:

1. the troops of Yzent;
2. the demons and the undead. However, if the latter are attacked, they will strike back.

Note that if, at any moment, the Templar troops lose half or more of their strength (number of
units), the survivors will then see their strength multiplied by 2.

***

## Juggernaut

*(Counter: catapult and battering ram.)*

The Juggernaut is a monstrous invention of Lord Whismerhill, specially devised to destroy enemy
fortifications. This machine is lent to the Magiocrat for the occasion. Its combat potential is
enormous. It has enormous power and a built-in battering ram identical in its effects to that of
Yzent. This enormous machine, which looks like a mighty ship on wheels, appears to the eyes of those
who look at it as a horrible monster of titanic size. This machine has the special ability of
inspiring fear.

***

## Battering ram

This counter serves to destroy the gate or the ramparts. When, during a combat phase, the ram is
adjacent to the gate or the rampart, roll a die. On a roll of 1, the gate or the rampart is
destroyed. Then place a destruction marker.

The defending units will no longer have the defence bonus that the protection of the rampart gave
them.

The forces of Yzent also have 3 siege engines that can hurl blocks of stone at a distance.

***

## Sahuagins

The Sahuagins are an aquatic race subject to the Magiocrat, and live in the Black Lake. They
intervene when an enemy unit comes within 6 hexes of the Black Lake. Note that the Sahuagins are
doubled when they fight or defend in a hex of aquatic terrain.

***

## Yzent

The forces of Yzent, hereditary enemies of the Viscount of Reissland, have but one goal: to wipe out
his troops, so as to control his kingdom. Blocked until now by the enormous fortress that protects
the border, they have provided siege engines to destroy that wall.

***

## Magiocrat

*(Counter: 30 / **P** / 20 — **M** — 15 / 10.)*

The counter representing the Magiocrat can never be permanently destroyed. Should it be eliminated
from play at any moment, this counter would reappear 2 turns later at a place of its choosing.

---

# Leaders

**Leader counters and their symbols:**

| Symbol | Leader / group |
| --- | --- |
| ☾ / ⧜ / ≋ | Demon princes |
| **W** | Undead lords |
| **W** (stylised) | Whismerhill |
| Coat of arms **T** | Lullth |
| Coat of arms (crown) | Gruntd |
| Coat of arms (sun) | URM |
| Coat of arms (cross) | PARSIFAL |
| Coat of arms (cross) | WHILLEM |
| Coat of arms (lightning) | RESSLAND |
| Coat of arms (tree/leaf) | ELENDIL |
| Coat of arms (crescent) | CORDR |
| Coat of arms (crescent) | OVGNORD |
| Coat of arms (crescent) | NURM |
| Coat of arms (bat) | YZENT |
| Coat of arms (bat) | RENT |

A leader counter represents a chief or a warrior of very great renown, present with their retinue
on the battlefield.

A leader's influence is not negligible; in that it allows the unit stacked with them not to suffer
the effects of fear.

When a leader counter suffers a retreat result, roll a saving throw (as for a spellcaster); if it is
failed, then the leader has been captured by one of the attacking units; otherwise they may retreat
normally.

Spellcaster counters, on the other hand, may always fall back, unless they are completely
surrounded, in which case they may choose to give themselves up as prisoners.

A leader counter and a spellcaster counter have no zone of control.

## Capture

A leader or a magician may be captured in certain cases. The capturing player may then choose to
kill their opponent, to ransom them or to keep them prisoner.

The price of a ransom in crowns is 10 % more than the leader's purchase cost.

Capture does not matter in certain scenarios, but it may in one of your campaigns.

---

# Magic

The part played by magic in "Ave Tenebrae" is preponderant. However, only certain counters
representing spellcasters may use it, with the exception of certain mythical creatures (dragons,
demons…) or certain particular leaders.

Each of these counters has close-combat or ranged attack characteristics and a movement potential,
as well as a symbol serving to identify it.

The magic potential of a creature represented by a counter, however, never appears on the counter
itself but on a character sheet (see character sheet).

No spellcaster may hold more magic points than their initial potential. These magic points serve to
pay for the effort required by the conjuration of certain spells and rituals.

Each spell cast by a mage or the like costs a certain number of magic points, varying with the power
of the spell or its function.

These magic points are deducted from the conjurer's magic potential immediately after the spell has
been cast.

A table is supplied to help you manage your magic points.

**Important**, note that each turn, each conjurer recovers 20 magic points. This recovery takes
place at the end of each turn.

## Transfer

**Important**: The points of magic potentials may be transferred from lesser mages to greater mages,
so that the latter may use them for their conjurations, but these transferred points must never
exceed the limit of the conjurer's magic potential.

The transfer of energy must be made at the start of the magic phase, before any spell has been cast
by the side concerned. Take good care to tell the opposing player the direction of the transfer, who
benefits from it, and who makes it.

*E.g.:* In the Ave Tenebrae scenario, the transfer may be made from the minor mages towards the 2
major mages: namely Orvarth & Thornz.

**Important**: In certain scenarios, for certain rituals, expenditures of magic points may only be
made by certain mages and without help (transfers), which means that the transfer of energy cannot
apply in such cases. See the scenarios for the cases just mentioned.

At the end of the magic phase, unused points due to a transfer will be dissipated and not counted
for the next turn.

However, each conjurer's own points will be recorded and valid for the next turn.

## The Conjurers

There are three types of conjurers in Ave Tenebrae (2nd edition): Mages, Clerics and Necromancers.
Each of these types of spellcaster has a source of magic of its own, as well as conjurations
particular to it.

### Mages

Mages or magicians draw their power from complicated and obscure rituals that allow them to
transform or create at will things, beings or effects on the material plane, using the energy of the
mystic winds.

In the world of Ave Tenebrae, magicians are powerful and dreaded.

Magicians may use all the rituals preceded by the letter **M**.

### Clerics

Clerics or High Priests draw their power from arduous ceremonies and initiatory prayers that allow
them to forge at will the divine breath of the gods they represent.

They are often dreaded and obeyed; but they are, in general, less feared than the caste of the
mages, being readier to keep company with their faithful and with the living.

Clerics may use all the spells preceded by the letter **C**.

### Necromancers

Necromancers draw their power from inhuman and unnameable incantations that allow them to subject
to their will the foul and black forces of the infernal planes, and of the plane of negation.

They are unanimously feared and dreaded, and the mere presence of one of them is enough to freeze the
blood of the bravest, their bodies slowly changing into nothing but an indescribable mass of shadows
and dark flesh from which seeps the strange glow of two red eyes without pupils.

They cherish only darkness and suffering, on which they feed.

Necromancers may use all the spells preceded by the letter **N**.

---

# Book of spells

## Magic

In this new version of Ave Tenebrae, the part played by magic has been increased in two ways.

First, necromancers and clerics have been added to the class of mages.

Second, a great many new spells have been added (20 spells).

Spells are of two kinds: personal spells and mass spells.

Personal spells are reserved for spellcasters, whereas mass spells may be used to give a unit the
benefit of the spell.

Certain spells are reserved only for clerics or for magicians; necromancers, however, may use at
will the spells of clerics and the spells of mages; for more detail, see the paragraph
"spellcasters".

Spells preceded by a "**C**" are reserved for clerics, whereas spells preceded by an "**M**" are
reserved for magicians.

However, some of these spells, accessible to both classes, will be preceded by a "**C**" and an
"**M**".

## Spells and conjurations

Each magician may, if they wish, cast spells during their magic phase.

Magicians must imperatively be within a radius of 10 hexes of the target of the spells in order to
cast them (unless a spell specifies otherwise).

During their magic phase, a player may cast as many spells as they wish, as long as their strength
potential allows it.

The list of spells they may use, and their effects, are as follows.

## Spells and charms

### Invisibility — *M, N*

This spell allows the person or the unit to become invisible.

**Important**: Remember to note, each turn, the unit's movement on a sheet of paper, so that the
opposing player can check your moves in case of dispute, or once you have become visible again.

This spell does not allow passing over a hex occupied by an animated hex, but it does allow crossing
zones of control as if they did not exist.

**Important**: a unit or a mage becomes visible again as soon as they attack another unit or are
engaged in another combat.

**Cost of the spell**: 2 points, and for a unit 20 points.

### Protection from missiles — *M, N*

This spell allows a person or a unit not to be affected by non-magical missiles for one turn.

**Cost of the spell**: personal use 2 points; for a unit 10 points.

### Protection from fear — *C, N*

This spell allows the recipients not to be affected by fear, whether of magical origin or otherwise.

**Cost of the spell**: personal use 2 points; for a unit 5 points.

### See invisible — *M, N*

This spell allows the recipients to make out the invisible within a radius of five hexes around
them; thus cancelling, for them alone, the effect of an invisibility spell.

**Cost of the spell**: personal use 2 points; for a unit 5 points.

### Animate dead — *C, N*

This spell allows its invoker to bring a destroyed unit back to a semblance of life by turning it
into a zombie unit.

To be of use, this spell must be cast on the exact spot where a unit was destroyed. After the spell,
replace the unit concerned with an undead unit (zombie).

**Important**: There can be no more undead units present on the battlefield than there are counters
of that type in the game. If all the zombie units are therefore already in play, the spell will have
no effect.

A zombie unit created in this way will be under the control of its conjurer; however, it will behave
and have the same abilities as a normal undead unit, even towards the troops beside which it fights.

**Cost of the spell**: 20 magic points.

### Fireball — *M, N*

This spell allows its conjurer to create in a hexagon an enormous ball of fire that will attack any
unit present with a strength of 5 for every 10 magic points used in the conjuration.

A successful saving throw brings a shift of one column to the left in the resolution of the combat
on the table.

A protection from fire brings a shift of 2 columns to the left, cumulative with a saving throw.

This spell is cast within a radius of ten hexes.

**Cost of the spell**: variable; see above.

### Storm — *C, N*

This spell allows its invoker to conjure an immense storm over the combat zone; a storm that will
last as long as its invoker wishes.

**Effects**: During a storm, all movement is halved, missile fire has its effectiveness halved, and
all combats are shifted one column to the left (except those fought by aquatic troops, for whom the
reverse is true).

**Important**: troops stationed in a citadel are not affected by a storm, except for missile fire.

**Cost of the spell**: 80 magic points, not transferable (see magic).

### Protection from conjured units — *C, M, N*

This spell allows its invoker to create around themselves a powerful pentacle that will forbid
passage, or even the sight of what stands at its centre, to any conjured unit (born of, or
intervening thanks to, a spell).

Note however that this spell is static, and that any movement of the unit or of the magician
protected by it will cause the spell to dissipate. This spell is cast within a radius of 5 hexes.

**Cost of the spell**: personal use 5 points; mass use 20 points per unit.

### Circle of fear — *C, N*

This spell allows its conjurer to grant a unit or a person an aura of fear, such that any unit
attacked by it, or attacking it, must roll a saving throw to test its morale; if it fails, the unit
can then in no way attack and will stay where it is doing nothing; or, if it is attacked, it must
retreat immediately. Cast within a radius of 5 hexes.

**Cost of the spell**: personal use 10 points; mass use 20 points.

### Dragon's breath — *M, N*

This spell allows its conjurer to spit fire like a dragon and to attack a hexagon on the 1-1 column
per 10 magic points used; that is 6-1 if 60 magic points are used.

**Important**: The effects of this spell are shifted 2 columns to the left if the unit has a
protection from fire, and 3 if it succeeds in its saving throw. The spellcaster must however be in
contact to use the spell properly. Exchange results, as for all missile fire, do not apply to the
spellcaster.

**Cost of the spell**: variable with power, see above.

### Deparalysis — *C, N*

This spell allows its evoker to neutralise the effects of a paralysis spell or of the special
ability of the same name. This spell is cast in contact with the paralysed unit.

**Cost of the spell**: 3 points per defence point of the unit.

### Fanaticism; Berserks — *C, N*

This spell allows its conjurer to fanaticise a unit so completely that it will be, for the rest of
the combat, wholly insensitive to fear and to loss of morale; thereby making it twice as dangerous
in combat (attack and defence potential × 2 until the end of the combats).

However, a berserk unit (except Templar units) will be wholly incapable of retreating; on a retreat
result it will therefore be removed from play.

**Cost of the spell**: 4 points per attack and defence point of the unit.

### Negation of distance — *M, N*

This spell allows its user to make a unit move twice its movement potential. Cast within a radius
of 10 hexes.

**Cost of the spell**: 20 points per unit concerned.

### Phantasmal ram — *M, N*

This spell allows its evoker to conjure a mystic ram that will then attack a rampart or a wall like
a "battering ram" counter, except that the wall will then be destroyed on a roll of 1 to 2.

**Cost of the spell**: 20 points per turn.

### Demonic invocation — *M, N, C*

This spell allows the thaumaturge to invoke a demon unit, drawn at random from among the demon units
present in the game (if they are not already on the map); this unit will then obey its conjurer for
7 turns, after which it will always attack the unit nearest to it until it has been dissipated or
wiped out. **Important**: if a major demon counter has been drawn, these will, at the end of the
seven turns, immediately attack the magician who evoked them, unless the latter has a pact with them
(as does the magiocrat Orvarth).

The unit appears in front of the spellcaster and may act immediately.

**Cost of the spell**: 40 points per unit invoked.

### Invocation of the undead — *C, N*

Identical to the previous spell.

**Cost of the spell**: 30 points per unit invoked.

### Darkness — *C, N*

This spell allows its evoker to create an eclipse of the sun that will last as long as they wish.

Treat the effects of this spell as comparable to night.

**Cost of the spell**: 100 magic points (not transferable).

### Divine blessing — *C, N*

This spell allows the effects of fear to be cancelled for one turn for all the units of one side,
and gives a bonus of −1 to the die for every combat and saving throw against weapons (the others
save automatically).

**Cost of the spell**: 70 magic points (not transferable).

### Divine curse — *C, N*

This spell is exactly the reverse in its effects, apart from the fact that it does not cause fear
(note that the two spells cancel each other out).

**Cost of the spell**: the same as for the previous one.

### Protection from magic — *M, N*

This spell allows its conjurer to protect themselves against magic, with the exception of a
successful dispel spell. This protection also extends to magically evoked units, which will then be
unable to attack the person so protected.

**Cost of the spell**: 40 points.

### Dispel magic — *C, M, N*

This spell allows the effect of any spell to be dissipated; it must be cast within a radius of ten
hexes. This spell costs a third more magic points than the cost of the spell it means to cancel.
However, a six-sided die must be rolled to see whether the spell achieves its aim. If a 1 comes up on
the die, the spell has failed to dissipate the magic.

**Cost of the spell**: 1/3 more than the cost of the spell the invoker is trying to dissipate.

### Flight — *M, N*

Certain units, representing winged forces, are present in the game. These units are therefore not
subject, while flying, to the restrictions of terrain on movement.

The only exception is flying over the volcano of Toth (to cross it, roll a saving throw against
paralysis). If this saving throw fails, the unit is destroyed by its fall into the volcano.

Combats in flight are not possible. When they suffer a wind spell, winged creatures must roll a
saving throw or be removed from play, killed by a bad fall. If they succeed, they will stay where
they are and may cross the barrier during that turn.

Magicians, thanks to this spell, may move through the air; the cost is 1 magic point per movement
point, up to the magician's movement potential.

### Eradicate — *C, M, N*

This spell allows a unit or a magician to be disintegrated, if they fail their saving throws.

**Cost of the spell**: 4 magic points per 1 point of the defence potential of the targeted unit.

### Wall of flame — *M, N*

This spell allows a wall of flames to be created within a radius of 5 hexes around its creator, on
combustible terrain (woods and plains). If the wall is created in woods, roll a die; if the result
is 1, 2, 3 or 4, the hexagons in immediate contact catch fire. On the plain, the fire spreads on a
roll of 1.

Once created, the initial fire hexagon lasts 3 turns on the plain, and in the woods only stops if
the fire dies (no spreading by contact, roll each turn) or if there is nothing left to devour.

**Cost**: 15 points per hexagon set ablaze.

Units that have to suffer or cross a wall of flames are considered attacked at 2 against 1 on the
combat table; the results apply in full.

Moreover, if for any reason the Elven forest is attacked in this way, an Elven magician will appear,
a magician with a magic potential of 50 points. This magician, who stays only in the forest, is not
represented by a counter, for he is practically impossible to locate or attack. He may therefore,
during the magic phase, cast his spells from any point of a hex of the Elven forest, and this up to
the maximum range, even outside the forest. This mage cannot, however, cast spells from a burning
forest hex.

### Wind — *M, N*

The magician who casts this spell creates a sudden burst of wind covering a line of 5 hexagons, a
line that can push a wall of mist back 2 hexes, put out a fire (1, 2, 3, 4, 5 per burning hex equals
fire put out) or prevent, in the turn immediately preceding the casting of this spell, a missile
fire (arrows only) over the area protected by the line. Two walls of wind cast in the same turn
cancel each other out.

**Cost**: 40 magic points for a line of five hexagons.

### Fear — *C, N*

This spell allows units that fail their saving throws to be routed, by the whole of their movement
points, and this for one turn.

**Cost**: 1 point per defence point of the targeted unit or units.

### Conjuration — *C, M, N*

The game comes with a series of counters representing elementals of air, water, fire and earth, as
well as counters representing various creatures such as rats, bats or wolves. These counters
represent creatures that may be conjured magically to make them fight as the one who invoked them
wishes.

The cost of a conjuration is 2 points for each strength point of the unit. The creatures then appear
where the magician stands and may serve immediately. These creatures stay present for 3 turns, then
vanish. To conjure water and fire elementals, one must go either near a lake or a river for those of
water, or to the volcano of Toth for the fire elementals.

Counters are supplied to mark the start of an invocation.

### Paralysis — *C, N*

This spell allows units that fail their saving throws to be paralysed. These units can then neither
move nor defend themselves for one turn. Attacks directed against them will automatically succeed,
and the unit is then eliminated.

**Cost**: 2 points per defence point of the unit.

### Wall of mist — *M, N*

This spell allows a wall of mist to be created within a radius of five hexes around the mage who
creates it. Any unit that tries to cross this wall must roll a saving throw. If it succeeds, it may
then cross; otherwise it will be destroyed and dissolved by the gases.

**Cost**: 10 magic points per hex of mist.

### Dispelling an invocation — *C, M, N*

Conjured counters may be dissipated, provided that twice as much power is spent as those counters
cost to invoke.

**Important**: The protection of a spell generally lasts one turn; unless specified, for magic this
turn runs from the magic phase of one turn to that of the next turn for the same player (so be
provident about your defences, and note your protections and your magic point expenditures on a
piece of paper).

---

# Purchase points

## Determining the value of a unit

To allow you to create your own scenarios, or to fight battles with the troops of your choice, you
are given below a rule that lets you put a figure on the cost of a unit, which will let you fight
battles of 1,000, 2,000 or 3,000 crowns.

A purchase point is called a crown in the game, and corresponds approximately to a gold piece.

Certain units have a cost of between 8 and 20 crowns; these are standard units, representative of a
human or typical unit without much training or particular power.

### Purchasing a unit

The cost of a unit is determined as follows:

The base cost is two crowns per attack and defence point of the piece. To this is added:

| Modifier | Cost |
| --- | --- |
| Base | 2 crowns per attack and defence point of the piece |
| Unit mounted on a normal animal (horse, etc.) | + 1 crown per attack and defence point |
| Unit able to fire missiles (archers) | + 1 crown per attack and defence point |
| Special abilities | + 5 crowns per ability |
| Special movements | + 5 crowns per special movement |
| Demon or undead unit | + 10 crowns |
| Counter representing a dragon | + 20 crowns |

The purchase cost of a mage or a leader will be discussed under their respective headings.

***

**Example:** purchase of a standard human unit, defence and attack potential 4 × 2 = 8 crowns; + no
ability = 0. **Total value of the unit = 8 crowns.**

***

**Another example:** standard human cavalry unit:

- Attack and defence potential 5 × 2 = 10 crowns
- The unit is mounted, which makes 5 × 1 = 5 crowns
- The unit can charge + 5

**Total cost of the unit = 20 crowns.**

***

**Last example:** cost of the heaviest Templar cavalry unit:

- Attack and defence potential: 30 × 2 = 60 crowns
- The unit is mounted 30 × 1 = 30 crowns
- The unit can shoot arrows 30 × 1 = 30 crowns
- The unit has the special ability of charging: + 5 = 5 crowns
- The unit has the special ability of resistance to fear: + 5 = 5 crowns
- The unit can go berserk + 5 = 5 crowns

**The total cost of the unit will therefore be 140 crowns.**

***

As you can see, there is an enormous difference between the two cavalry units, a difference
explained by the many abilities and the power of the Templar unit, which perfectly reflects the cost
of the armour and the training of a heavy or extra-heavy cavalry unit.

This method of working out a unit's cost may seem complicated at first sight, but it makes it easy to
build an army from a fixed number of crowns, and makes sure that your opponent will have as much
chance as you of winning a battle, the two forces then being roughly equal.

**Important**: Note that any unit conjured during the course of the game by a magician costs nothing
in crowns but is paid for with magic points. Note that this ability, like that of casting spells, is
included in the purchase cost of a leader or a spellcaster.

***

## Cost of a spellcaster

The base purchase cost of a spellcaster is:

| Class | Base cost |
| --- | --- |
| Mage | 10 crowns |
| Cleric | 10 crowns |
| Necromancer | 20 crowns |

To this is added:

| Characteristic | Cost | Maximum |
| --- | --- | --- |
| Attack or defence point | 5 crowns | defence potential max. 20 |
| Movement point | 5 crowns | 15 |
| Ranged attack point | 5 crowns | 10 |
| Range point | 5 crowns | 10 |
| Special ability of a spellcaster | 50 crowns extra | — |
| Magic potential | 200 crowns per 20 points of potential | 80 magic points |

Once you have created your spellcaster, make a counter in their likeness and note their
characteristics and their magic points on a piece of paper.

You will notice that a spellcaster is very expensive, which is why we advise you to keep to the
maxima above.

However, nothing prevents you from making scenarios worth several thousand crowns, in which each
side may have many mages.

But do not forget that battles between armies are still the main purpose of this game.

***

## Cost of defensive works

Some of these symbols exist on the Ave Tenebrae map; the others (ditches, trapped ditch, wall) are
given as a guide for creating your own scenarios or campaigns on the blank maps.

| Work | Cost per hexagon | Effect |
| --- | --- | --- |
| Ditches | 10 crowns | The unit crossing it loses a turn. |
| Trapped ditches | 40 crowns | The unit crossing it must stop and suffer an attack at 2 against 1. It may pass if it succeeds. |
| Walls | 50 crowns | Defender × 2. |
| Ramparts | 100 crowns | Defender × 3. |
| Forts | 1000 crowns | Defence × 3 and no **DR** results apply. |

---

# Disputed points

When a dispute arises over the interpretation of one or more rules, settle it amicably, or agree on
the disputed point before playing.

Do not hesitate to change or add a rule: Ave Tenebrae is a game and has but one purpose, your
entertainment.

---

# Scenarios

## Scenario no. 1 — The battle (of the dawn of darkness)

This battle (see chronicle) is the most important battle to have shaken the empire in its whole
history.

**Course of play**: First, the forces of the Empire place their counters on the map, namely one
population counter on each town or village hex and 3 army counters in each citadel. The Empire
player will then place the rest of their garrison troops as they please within their borders.

The Magiocrat's human troops enter play through the Threshold of the Mists.

Distribution of the magician counters and of the magic potentials.

**Important**: the Magiocrat is considered a necromancer.

**Elves**: The Elves appear if a unit of the Magiocrat comes within 10 hexes of a hexagon of the
Elven forest. At that moment, all the Elven counters will appear anywhere in the forest, at the
player's choice.

**Viscounty of Reissland**: The Viscounty player will place their troops wherever they wish within
their kingdom, but must remember that their main objective is to prevent the passage of the forces
of Yzent.

**The black force**: The Magiocrat's troops are set up in the game as follows: the Orc troops are
initially placed within the walls of Orcreich. The other non-human troops enter play through the
Threshold of the Mists.

**Troops of Yzent**: The troops of Yzent arrive by the north-west side of the map and must force
their way through the fortifications of the Marches in order to try to destroy their hereditary
enemy (Reissland).

**Demons and the undead**: These enter play from the moment they are invoked. The demons enter by
the black road, whereas the undead spring from the ruins of the town of Ghaarth.

**The Sahuagins**: These enter play as soon as a unit of the alliance comes within 6 hexes of the
Black Lake. They will then fight under the Magiocrat's orders.

**Reinforcements of darkness**: These enter play if half of the regular (non-conjured) forces have
been wiped out, or if an enemy unit comes within 5 hexes of Orcreich.

**Reinforcements of the alliance**: These arrive as soon as a citadel is taken, or as soon as
roughly 1/4 of the Empire's territory is under the control of the forces of darkness.

The Empire's reinforcements then arrive at the start of the movement phase of the following turn.
With these forces, the Empire's magicians appear too.

If the Empire's troops cannot enter at the places named above, then bring them in at any point on
the edge of the map.

**The Templars**: The Templars appear from the 12th turn, or on the turn following the annihilation
of the forces of Reissland.

The Empire's reinforcements enter by the road of the Val de Froy or, if that area is under enemy
control, by the plain behind the capital. The Templars enter play at any point on the edge of the
kingdom of Reissland.

**Magic**: Each of these counters has a certain value in power potential; the most powerful
represents the mage Orvarth. The distribution of the various potentials is as follows:

| Side | Character | Magic potential |
| --- | --- | --- |
| Black forces | Orvarth | 100 magic points |
| Black forces | 5 counters (magicians) | 20 magic points |
| Alliance | Thornz | 80 magic points |
| Alliance | 4 counters (magicians) | 20 magic points |

The battle of the dawn of darkness is played in 32 turns or fewer. The alliance wins if it manages to
repel the invasions and keep its capital. The Forces of Darkness win by wiping out the enemy troops,
or by controlling and then destroying the capital.

---

## Chronicle of the lands of Dreamrift

In the year 7977 of the golden age, the black dawn rose. From everywhere in the world sprang hordes
of darkness that drowned in a deluge of fire, iron and blood the ancient civilisations that had
reigned for eight thousand years. Upon the Empire of Lynn fell the Lord of evil and darkness,
Whismerhill, who, after a terrifying battle, overthrew and killed the Emperor, while Lynn the
capital was reduced to ashes. Helped in this by the terrible Hazolhim, a powerful and dreadful mage,
son of Asmodeus; after the tables of the law had been broken by the new Emperor, he opened a
threshold that allowed communication with the infernal powers. This hallowed date is considered by
all historiographers as the beginning of the era of darkness.

After this victory, on every side, in every kingdom, revolts broke out, and black servants of the
Evil One threw their armies against the forces of Good. Orvarth's war is one of these many battles
that ravaged the world so that the new dawn should be established; and, in under 10 years, the black
tide had wholly engulfed the bastions of law and order: the temples were in ruins, the towns laid
waste, and where the iron grip of darkness did not reign, there was a bewildered world given over to
barbarism. The moment came when only two lands were left whose torch still defied the blackness: the
Kingdom of Sisigye and the mightiest of the mighty, the Tharque Empire.

It is the terrible battle that wiped out this Empire that I am going to tell you.

At dawn, the mighty armies of the Magiocrat attacked; they sprang from the mist as if out of
nothing; when the generals of the Empire saw them, it was too late. They were taken by surprise, and
their reinforcements were slow to arrive (by then it was too late). Already Orvarth the dark had
invoked the legions of the dead and the infernal cohorts.

When the Empire tried to make a stand with the weak garrison on the spot, they were swept away; the
reinforcements, arrived just in time, were slaughtered to the last man, despite the alliance of the
Elves. Close by, the forces of Yzent swooped, like birds of prey, on the armies of the Viscount of
Reissland, who, massed on the wall of the marches of Yzent, tried in vain to stem their onrush. And
when at last the Templars of Sisigye, under the leadership of their commander, arrived with their
mighty cavalry, it was truly too late; despite a fierce fight, they could not turn the situation
round and had to return pitifully, defeated, to their kingdom. It was often said that, had the
generals of the Empire waited for the reinforcements before throwing their troops into the battle,
the outcome of the fight would have been changed. But History is not written with such hypotheses,
and so the great Orvarth, strong with this first victory, was able to sweep unpunished over the
Empire, whose two other provinces fell without much difficulty.

Two years later, the Magiocrat's forces joined up before Tharkis with the forces of the alliance of
Braise, led by the dreaded Whismerhill and Wuthering Height. This was the start of a long siege,
which lasted a year, at the end of which the proud capital was wiped out. On that glorious day, the
alliance of Braise had won its greatest victory, and like a black shroud, the forces of evil had
spread over the World.

> *(Marlfriss the wise, chronicler of the Magiocrat, in the year Grale 8000 of the advent of
> Darkness.)*

### Game phases (scenario no. 1)

The course of the game breaks down into several turns, themselves divided into several phases; which
are, in order:

1. Movement phase of the Black Forces player;
2. Movement phase of the Yzent player;
3. Magic phase of the Black Forces player;
4. Combat phase of the Black Forces player;
5. Combat phase of the Yzent player;
   — end of the actions of the Black Forces player(s);
6. Movement phase of the Empire player;
7. Movement phase of the Viscount of Reissland player;
8. Magic phase of the Empire player;
9. Combat phase of the Empire player;
10. Combat phase of the Reissland player;
    — end of the actions of the Alliance player(s).

### Object of the game

The Black Forces must control the capital of the third province and the forts on the border of the
dead lands, as well as the Krak de Reiss.

For the forces of the alliance, the goal is to control the capital of the province and the largest
possible area of territory, or else to wipe out the Magiocrat's hordes.

The winner will be the player who fulfils these victory conditions at the end of the number of
turns allotted by the game.

Beware: for the various scenarios there are victory conditions that differ from case to case.

---

## Scenario no. 2 — The revolt of the slaves

While the Magiocrat is away from his kingdom, and his human troops occupy the citadels and castles
of the newly conquered lands, the non-human troops launch a surprise assault and try to eliminate
all the human troops, the better to plunder the towns.

Player no. 1 controls the Magiocrat's human armies (red on black background), which are placed in
the towns and fortifications of the map (Morgenstern, gates of the mists, and other citadels).

Player no. 1 will also control 3 minor magicians of the Magiocrat.

The Magiocrat will return to his kingdom from the 10th turn, with his magic potential at its
highest and his usual powers.

Player no. 2 will control all the Magiocrat's non-human units as well as his reinforcements; these
will mass north of the Rift of Tsaroth, while the orcs burst out of Orcreich.

Player no. 2 will control 2 minor mages of the Magiocrat.

Player no. 1 wins if they manage to control Morgenstern, Orvarth's tower and three citadels at the
end of turn 16.

Player no. 2 wins if they manage to prevent player no. 1 from achieving their objectives, or if they
eliminate more than 80 % of the Magiocrat's human troops.

The elves will remain boundlessly neutral in this conflict.

---

## Scenario no. 3 — For whom the bell tolls

Breaking the alliance of Braise, the Magiocrat breaks his oath of allegiance to the empire of Lynn.

3 months later, he sees with horror the elite troops of the imperial army of the emperor Wismerhill
advancing on his territory, flanked by the demonic and undead troops he is used to controlling,
along, of course, with the Juggernaut.

The Magiocrat, gathering all his troops, then tried to make a stand while his citadels resisted foot
by foot.

**Player no. 1**: This player will control all the troops of the empire of Lynn; plus the demonic
and undead troops (not being summoned, they cannot be dispelled), which will enter the map by the
Val de Froy.

The emperor Wismerhill has 100 points of clerical magic.

While the demigod Azolhim has 120 points of potential (Azolhim is a mage).

Player no. 1 will also control 4 minor mages.

**Player no. 2**: This player will control the Magiocrat and all his human and non-human troops, as
well as the troops of Yzent, and his reinforcements.

If by accident the counters of the emperor and of Azolhim were to be eliminated, they would reappear
2 turns later anywhere on the map.

The winner will be the one who exterminates the other; with the difference that even if the imperial
troops were eliminated, nothing would prevent the emperor from coming back another time; but not for
10 or 20 years, which would leave the Magiocrat in relative peace.

Played over an undetermined number of turns.

---

## Scenario no. 4 — The war of the dwarves

1,000 years before the black dawn, a violent conflict set the dwarf and orc nations against each
other.

To answer the ceaseless raids of the orcs, the dwarf chief Grundt ordered his army to attack
Orcreich at once and to exterminate the orcs entirely.

**Player no. 1**: Player no. 1 will control the dwarf army and the leader Grundt, as well as the
mage Vorgtd (magic potential: 45).

The dwarf army masses south of the volcano of Toth.

**Player no. 2**: Player no. 2 will control all the orc pieces, which they place inside Orcreich.
The orc player has a minor necromancer (20 magic points).

The winner is the one who exterminates the other.

---

## Scenario no. 5

In the year 50 before the dawn of darkness, the town of Morgenstern was attacked by a strange race
called "the flyers", all of whose members had wings.

The town was wholly laid waste before the reinforcements arrived.

**Player no. 1**: Place the Empire's garrison counters on the map as for the dawn of darkness
scenario. Along with 3 minor mages.

**Player no. 2**: The army of the flyers enters play at any point of the map. It has the leader
Lullth, and the mage Huluth (40 magic points).

**Goal of player no. 1**: To prevent the destruction of the towns and the kraks, and the sacking of
Morgenstern.

**Goal of player no. 2**: To destroy and set ablaze as much territory as possible before the 10th
turn, when the Empire's reinforcements arrive with Thornz and 5 dragons.

As you can see, it is easy to devise many scenarios; so we leave the field open to you. Use the
purchase points in crowns to build your armies; resolve the imaginary battles of your favourite
role-playing games, the battlefield is yours.

---

# Character sheet

- **Name:**
- **Country:**
- **Identification:** (box in which to draw the counter)
- **Att. / def. strength:**
- **Movement:**
- **Strength (missiles):**
- **Missile range:**
- **Flying movement:**
- **Special abilities:**
- **Magic potential:**

**Magic potential track**

| | | | | | | | | | |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 120 | 130 | 140 | 150 | 160 | 170 | 180 | 190 | 200 | |
| 20 | 30 | 40 | 50 | 60 | 70 | 80 | 90 | 100 | 110 |
| 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |

**Character status**: paralys. / routed / dead

**Cost of the character (in crowns):**

---

# Terrain table

The French name in brackets is the one used by `carte.json` and the engine; `plaine`, the default terrain, has no row in the booklet.

| Terrain | Movement | Combat |
| --- | --- | --- |
| **WOODS** (*bois*) | 2 points except Elves | Elves: × 2 in defence; + 2 to the attacker's die |
| **HILLS** (*colline*) | 2 points except Earth elemental | + 2 to the attacker's die |
| **MOUNTAINS** (*montagne*) | Impassable except by way of hill, road or air; same for Earth elemental | Defence × 3 |
| **RIVERS** (*riviere*) | Impassable except by way of bridges, air or aquatic creatures | Defence × 2 |
| **PATHS** (*chemin*) | × 2 | — |
| **ROADS** (*route*) | × 3 | — |
| **RIFT** (*faille*) | Impassable except by air | — |
| **LAKES** (*lac*) | Impassable except by water and air | Defence × 2 |
| **RAMPARTS** (no terrain of their own: *chateau* and *ville* on the map) | Impassable except by combat or for allies | Defence × 3 |
| **RUINS** (*ruines*) | × 2 | Defence × 2 |
| **VILLAGES** (*village*) | Normal | Defence × 2 |
| **FORTS** (*fort*) | Impassable except by combat or for allies | Defence × 3 |

---

*Publisher: **Jeux Descartes**, 5 rue de la Baume, 75008 Paris — Tel.: 45.62.35.27.
Layout Atelier 00 — Printed by Métais s.a., 95110 Sannois.*
