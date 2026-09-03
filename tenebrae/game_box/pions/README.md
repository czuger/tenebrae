# Ave Tenebrae counters — filed by faction and by purpose

This directory gathers the **127 counter photographs** of the 2nd edition of Ave Tenebrae (1986),
taken from the `material/base_material/images/` directory and filed after the breakdown detailed in
`material/base_material/vintageboard-1-ave-tenebrae.html` (the article "Vintageboard 1: Ave
Tenebrae", R-One Chaff).

The original files are **kept intact** in `material/base_material/images/`; this directory contains
only renamed copies. The file names, and the contents column of the tables below, are French: they
are the game's data, and the code reads them as they stand.

## Summary

| Directory | Faction / purpose | Counters |
| --- | --- | --- |
| `01-yzent/` | Yzent | 12 |
| `02-reissland/` | Viscounty of Reissland | 4 |
| `03-empire/` | Tharque Empire | 10 |
| `04-templiers/` | Templars | 7 |
| `05-population/` | Population | 1 |
| `06-empire-de-lynn/` | Empire of Lynn | 12 |
| `07-chaos/` | Chaos | 6 |
| `08-non-humains/` | Non-humans | 11 |
| `09-elfes/` | Elves | 6 |
| `10-nains/` | Dwarves | 6 |
| `11-orques/` | Orcs | 8 |
| `12-sahuaguins/` | Sahuagin | 4 |
| `13-dragons/` | Dragons | 1 |
| `14-morts-vivants/` | Undead | 6 |
| `15-demons/` | Demons | 8 |
| `16-volants/` | Flyers | 5 |
| `17-conjurations/` | Assorted conjurations | 7 |
| `18-machines-de-siege/` | Siege engines | 1 |
| `19-magiciens/` | Magicians and clerics | 2 |
| `20-marqueurs/` | Markers and game elements | 6 |
| `21-vues-d-ensemble/` | Overviews | 4 |

### Sides

- **Forces of the Alliance / of Good**: Tharque Empire, Viscounty of Reissland, Templars, Elves,
  Population, Dragons, Empire of Lynn (scenario 3), Dwarves (scenario 4).
- **Forces of the Darkness / of the Magiocrat**: Chaos, Non-humans, Orcs, Sahuagin, Yzent (an ally
  of convenience), Undead, Demons, the Juggernaut.
- **Neutral / outside the sides**: Flyers (scenario 5), conjurations, markers.

## Values read off the counters — `pions.json`

`pions.json` records, for each of the 127 photographs in this directory, the values **read by eye
off the photograph**. The key is the image's name without directory or extension; the dictionary
carries the image's path from the repository root. Its field names are French, like the rest of the
game's data, and `tenebrae.engine.piece` reads them as such.

| Field | Contents | Position on the counter |
| --- | --- | --- |
| `image` | path of the photograph from the repository root | — |
| `faction` | filing directory (`01-yzent`, …) | — |
| `force` | attack and defence strength | top left |
| `mouvement` | movement points | top right |
| `tir` | combat strength by missile fire | bottom left |
| `portee` | missile range | bottom right |
| `mouvement_vol` | flight movement (the figure in brackets) | bottom centre |
| `facultes_speciales` | special ability letter (`P`, `s`, `PA`, `D`…) | top centre |
| `symbole` | unit type identified from the symbol table | centre |
| `remarques` | non-human letters, leader names, reading doubts | — |

A field absent from the counter is `null`. 114 of the 127 entries carry a movement value; the other
13 are the markers, the two record sheets, the four overviews and the bats (which have only a
flight movement).

The file is **written by hand from the photographs**, not generated: correcting it means reopening
the photograph concerned.

## Yzent

`01-yzent/` — Hereditary enemy of the Viscounty of Reissland. Arrives from the north-west of the map (scenarios 1 and 3).

| File | Contents | Source photograph |
| --- | --- | --- |
| `yzent-01-9-infanteries-de-puissance-4.jpg` | 9 infanteries de puissance 4 | `20170714_154512.jpg` |
| `yzent-02-6-infanteries-de-puissance-6.jpg` | 6 infanteries de puissance 6 | `20170714_154739.jpg` |
| `yzent-03-8-archers.jpg` | 8 archers | `20170714_154526.jpg` |
| `yzent-04-3-catapultes.jpg` | 3 catapultes | `20170714_154702.jpg` |
| `yzent-05-1-belier.jpg` | 1 belier | `20170714_154648.jpg` |
| `yzent-06-5-phalanges-de-puissance-5-renforts.jpg` | 5 phalanges de puissance 5 (renforts ?) | `20170714_154631.jpg` |
| `yzent-07-5-phalanges-de-puissance-8-renforts.jpg` | 5 phalanges de puissance 8 (renforts ?) | `20170714_154616.jpg` |
| `yzent-08-7-cavaleries-de-puissance-5-renforts.jpg` | 7 cavaleries de puissance 5 (renforts ?) | `20170714_154720.jpg` |
| `yzent-09-6-cavaleries-de-puissance-10-renforts.jpg` | 6 cavaleries de puissance 10 (renforts ?) | `20170714_154757.jpg` |
| `yzent-10-1-general-de-puissance-25-renforts.jpg` | 1 general de puissance 25 (renforts ?) | `20170714_154810.jpg` |
| `yzent-11-leader-1.jpg` | leader 1 | `20170714_154821.jpg` |
| `yzent-12-leader-2.jpg` | leader 2 | `20170714_154834.jpg` |

## Reissland

`02-reissland/` — A kingdom independent of the Empire, present in scenario 1. Must contain the invasion from Yzent.

| File | Contents | Source photograph |
| --- | --- | --- |
| `reissland-01-15-infanteries.jpg` | 15 infanteries | `20170714_162924.jpg` |
| `reissland-02-8-cavaleries.jpg` | 8 cavaleries | `20170714_162904.jpg` |
| `reissland-03-3-archers.jpg` | 3 archers | `20170714_162845.jpg` |
| `reissland-04-1-leader.jpg` | 1 leader | `20170714_162934.jpg` |

## The Tharque Empire

`03-empire/` — The Empire's human forces: garrison troops, then reinforcements.

| File | Contents | Source photograph |
| --- | --- | --- |
| `empire-01-26-infanteries.jpg` | 26 infanteries | `20170715_142502.jpg` |
| `empire-02-6-cavaleries.jpg` | 6 cavaleries | `20170715_142519.jpg` |
| `empire-03-7-archers.jpg` | 7 archers | `20170715_142430.jpg` |
| `empire-04-1-leader.jpg` | 1 leader | `20170715_142541.jpg` |
| `empire-05-8-infanteries-renforts.jpg` | 8 infanteries (renforts) | `20170715_142630.jpg` |
| `empire-06-13-phalanges-renforts.jpg` | 13 phalanges (renforts) | `20170715_142559.jpg` |
| `empire-07-7-archers-renforts.jpg` | 7 archers (renforts) | `20170715_142614.jpg` |
| `empire-08-4-cavaleries-de-puissance-8-renforts.jpg` | 4 cavaleries de puissance 8 (renforts) | `20170715_143543.jpg` |
| `empire-09-6-cavaleries-de-puissance-10-renforts.jpg` | 6 cavaleries de puissance 10 (renforts) | `20170715_142646.jpg` |
| `empire-10-1-leader-renforts.jpg` | 1 leader (renforts) | `20170715_143428.jpg` |

## Templars

`04-templiers/` — Elite reinforcement of scenario 1 (turn 12, or the fall of Reissland). Immune to fear.

| File | Contents | Source photograph |
| --- | --- | --- |
| `templiers-01-5-infanteries.jpg` | 5 infanteries | `20170715_150125.jpg` |
| `templiers-02-9-cavaleries-de-puissance-10.jpg` | 9 cavaleries de puissance 10 | `20170715_150145.jpg` |
| `templiers-03-8-cavaleries-lourdes-de-puissance-15.jpg` | 8 cavaleries lourdes de puissance 15 | `20170715_150159.jpg` |
| `templiers-04-4-archers-montes-a-cheval.jpg` | 4 archers montes a cheval | `20170715_150216.jpg` |
| `templiers-05-1-general.jpg` | 1 general | `20170715_150243.jpg` |
| `templiers-06-leader-1.jpg` | leader 1 | `20170715_150259.jpg` |
| `templiers-07-leader-2.jpg` | leader 2 | `20170715_150314.jpg` |

## Population

`05-population/` — Populace counters scattered through the Empire's villages at the start of the game.

| File | Contents | Source photograph |
| --- | --- | --- |
| `population-01-20-populaces.jpg` | 20 populaces | `20170715_192640.jpg` |

## The Empire of Lynn

`06-empire-de-lynn/` — The imperial army of scenario 3 (Pour qui sonne le glas). The only force in the game to have chariots.

| File | Contents | Source photograph |
| --- | --- | --- |
| `empire-de-lynn-01-10-infanteries.jpg` | 10 infanteries | `20170715_194401.jpg` |
| `empire-de-lynn-02-10-cavaleries-de-puissance-10.jpg` | 10 cavaleries de puissance 10 | `20170715_194457.jpg` |
| `empire-de-lynn-03-4-cavaleries-lourdes-de-puissance-15.jpg` | 4 cavaleries lourdes de puissance 15 | `20170715_194532.jpg` |
| `empire-de-lynn-04-4-cavaleries-lourdes-de-puissance-30.jpg` | 4 cavaleries lourdes de puissance 30 | `20170715_194600.jpg` |
| `empire-de-lynn-05-10-phalanges.jpg` | 10 phalanges | `20170715_194633.jpg` |
| `empire-de-lynn-06-6-archers-de-puissance-4.jpg` | 6 archers de puissance 4 | `20170715_194708.jpg` |
| `empire-de-lynn-07-4-archers-de-puissance-10.jpg` | 4 archers de puissance 10 | `20170715_194739.jpg` |
| `empire-de-lynn-08-3-chars-legers.jpg` | 3 chars legers | `20170715_194802.jpg` |
| `empire-de-lynn-09-3-chars-lourds.jpg` | 3 chars lourds | `20170715_194825.jpg` |
| `empire-de-lynn-10-4-catapultes.jpg` | 4 catapultes | `20170715_194853.jpg` |
| `empire-de-lynn-11-empereur-whismerhill.jpg` | Empereur Whismerhill | `20170715_194935.jpg` |
| `empire-de-lynn-12-demi-dieu-azolhim.jpg` | Demi-dieu Azolhim | `20170715_194913.jpg` |

## Chaos

`07-chaos/` — The Magiocrat's basic human army, first onto the battlefield.

| File | Contents | Source photograph |
| --- | --- | --- |
| `chaos-01-4-infanteries-de-puissance-5.jpg` | 4 infanteries de puissance 5 | `20170718_124656.jpg` |
| `chaos-02-10-archers-de-puissance-3.jpg` | 10 archers de puissance 3 | `20170718_124823.jpg` |
| `chaos-03-5-cavaleries-de-puissance-9.jpg` | 5 cavaleries de puissance 9 | `20170718_124942.jpg` |
| `chaos-04-10-phalanges.jpg` | 10 phalanges | `20170718_125122.jpg` |
| `chaos-05-6-infanteries-de-puissance-10-renforts.jpg` | 6 infanteries de puissance 10 (renforts ?) | `20170718_125449.jpg` |
| `chaos-06-1-leader.jpg` | 1 leader | `20170718_125540.jpg` |

## Non-humans

`08-non-humains/` — Seven races entering through the Seuil des Brumes. Must always fight in a group.

| File | Contents | Source photograph |
| --- | --- | --- |
| `non-humains-01-3-infanteries-de-trolls.jpg` | 3 infanteries de trolls | `20170718_133713.jpg` |
| `non-humains-02-6-infanteries-de-gobelins.jpg` | 6 infanteries de gobelins | `20170718_133804.jpg` |
| `non-humains-03-4-cavaleries-de-gobelins.jpg` | 4 cavaleries de gobelins | `20170718_133848.jpg` |
| `non-humains-04-3-infanteries-d-hobgobelins.jpg` | 3 infanteries d'hobgobelins | `20170718_133946.jpg` |
| `non-humains-05-2-archers-hobgobelins-h.jpg` | 2 archers hobgobelins (h) | `20170720_201750.jpg` |
| `non-humains-06-3-infanteries-k-kobolds.jpg` | 3 infanteries K (kobolds ?) | `20170720_201834.jpg` |
| `non-humains-07-2-archers-k-kobolds.jpg` | 2 archers K (kobolds ?) | `20170720_201919.jpg` |
| `non-humains-08-3-infanteries-m-minotaures-ou-manticores.jpg` | 3 infanteries m (minotaures ou manticores ?) | `20170720_202022.jpg` |
| `non-humains-09-3-infanteries-o-ogres-ou-orog.jpg` | 3 infanteries o (ogres ou orog ?) | `20170720_202128.jpg` |
| `non-humains-10-3-infanteries-bug.jpg` | 3 infanteries bug (?) | `20170720_202247.jpg` |
| `non-humains-11-2-phalanges-bug.jpg` | 2 phalanges bug (?) | `20170720_202315.jpg` |

## Elves

`09-elfes/` — Allies of the Empire; they appear if an enemy unit comes within 10 squares of the elven forest.

| File | Contents | Source photograph |
| --- | --- | --- |
| `elfes-01-5-infanteries.jpg` | 5 infanteries | `20170718_140046.jpg` |
| `elfes-02-4-archers.jpg` | 4 archers | `20170718_140113.jpg` |
| `elfes-03-5-cavaleries-de-puissance-6.jpg` | 5 cavaleries de puissance 6 | `20170718_140153.jpg` |
| `elfes-04-5-cavaleries-de-puissance-10.jpg` | 5 cavaleries de puissance 10 | `20170718_140239.jpg` |
| `elfes-05-3-archers-montes-a-cheval.jpg` | 3 archers montes a cheval | `20170718_140313.jpg` |
| `elfes-06-1-leader.jpg` | 1 leader | `20170720_205941.jpg` |

## Dwarves

`10-nains/` — Absent from the 1st edition. Scenario 4 (La guerre des nains), south of the volcano of Toth.

| File | Contents | Source photograph |
| --- | --- | --- |
| `nains-01-5-infanteries.jpg` | 5 infanteries | `20170720_204053.jpg` |
| `nains-02-4-arbaletriers.jpg` | 4 arbaletriers | `20170720_203935.jpg` |
| `nains-03-4-arbaletriers-lourds.jpg` | 4 arbaletriers lourds | `20170720_203953.jpg` |
| `nains-04-5-phalanges.jpg` | 5 phalanges | `20170720_204024.jpg` |
| `nains-05-2-leaders.jpg` | 2 leaders | `20170720_204117.jpg` |
| `nains-06-1-mage-vorgtd.jpg` | 1 mage (Vorgtd) | `20170720_204129.jpg` |

## Orcs

`11-orques/` — Based in the Orcreich. Attack bonus at night, penalty by day. Scenarios 1 and 4.

| File | Contents | Source photograph |
| --- | --- | --- |
| `orques-01-15-infanteries.jpg` | 15 infanteries | `20170721_113339.jpg` |
| `orques-02-5-cavaleries.jpg` | 5 cavaleries | `20170721_113516.jpg` |
| `orques-03-5-archers.jpg` | 5 archers | `20170721_113549.jpg` |
| `orques-04-5-archers-montes-a-cheval.jpg` | 5 archers montes a cheval | `20170721_113614.jpg` |
| `orques-05-2-infanteries-renforts.jpg` | 2 infanteries (renforts) | `20170721_113659.jpg` |
| `orques-06-5-cavaleries-renforts.jpg` | 5 cavaleries (renforts) | `20170721_113717.jpg` |
| `orques-07-3-cavaleries-archers-renforts.jpg` | 3 cavaleries archers (renforts) | `20170721_113738.jpg` |
| `orques-08-1-leader.jpg` | 1 leader | `20170721_113800.jpg` |

## Sahuagin

`12-sahuaguins/` — An aquatic race of the Lac Noir, subject to the Magiocrat. Strength x2 in water.

| File | Contents | Source photograph |
| --- | --- | --- |
| `sahuaguins-01-1-infanterie.jpg` | 1 infanterie | `20170721_122824.jpg` |
| `sahuaguins-02-5-phalanges.jpg` | 5 phalanges | `20170721_122901.jpg` |
| `sahuaguins-03-5-tridents.jpg` | 5 tridents | `20170721_122802.jpg` |
| `sahuaguins-04-9-archers.jpg` | 9 archers | `20170721_122750.jpg` |

## Dragons

`13-dragons/` — A summoning of the forces of good (20 magic points, appearing on a 1 on the die). A single attack at 4 against 1.

| File | Contents | Source photograph |
| --- | --- | --- |
| `dragons-01-pions-de-dragons-trois-couleurs.jpg` | pions de dragons (trois couleurs) | `20170721_125028.jpg` |

## Undead

`14-morts-vivants/` — Summoned by the Magiocrat from the Île du Crâne (80 magic points). They fight only at night.

| File | Contents | Source photograph |
| --- | --- | --- |
| `morts-vivants-01-20-unites-de-squelettes.jpg` | 20 unites de squelettes | `20170721_184848.jpg` |
| `morts-vivants-02-7-unites-de-zombies.jpg` | 7 unites de zombies | `20170721_184929.jpg` |
| `morts-vivants-03-5-goules.jpg` | 5 goules | `20170721_184955.jpg` |
| `morts-vivants-04-5-archers-de-nature-indeterminee.jpg` | 5 archers de nature indeterminee | `20170721_185041.jpg` |
| `morts-vivants-05-5-cavaleries-de-nature-indeterminee.jpg` | 5 cavaleries de nature indeterminee | `20170721_185102.jpg` |
| `morts-vivants-06-3-lords-montes-sur-dragons.jpg` | 3 lords (montes sur dragons) | `20170721_185124.jpg` |

## Demons

`15-demons/` — Legions summoned by Orvarth (100 magic points); protoplasmic ones (50 points).

| File | Contents | Source photograph |
| --- | --- | --- |
| `demons-01-5-infanteries.jpg` | 5 infanteries | `20170723_192754.jpg` |
| `demons-02-3-cavaleries.jpg` | 3 cavaleries | `20170723_193012.jpg` |
| `demons-03-4-phalanges.jpg` | 4 phalanges | `20170723_193037.jpg` |
| `demons-04-5-tridents.jpg` | 5 tridents (?) | `20170723_193113.jpg` |
| `demons-05-prince-demon-1.jpg` | prince demon 1 | `20170723_193137.jpg` |
| `demons-06-prince-demon-2.jpg` | prince demon 2 | `20170723_193158.jpg` |
| `demons-07-prince-demon-3.jpg` | prince demon 3 | `20170723_193218.jpg` |
| `demons-08-8-demons-protoplasmiques.jpg` | 8 demons protoplasmiques | `20170723_193240.jpg` |

## Flyers

`16-volants/` — The winged race of scenario 5 (the attack on Morgenstern). Leader Lullth, mage Huluth.

| File | Contents | Source photograph |
| --- | --- | --- |
| `volants-01-5-infanteries.jpg` | 5 infanteries | `20170723_194849.jpg` |
| `volants-02-5-phalanges.jpg` | 5 phalanges | `20170723_194939.jpg` |
| `volants-03-8-archers.jpg` | 8 archers | `20170723_195005.jpg` |
| `volants-04-1-leader-lullth.jpg` | 1 leader (Lullth) | `20170723_195025.jpg` |
| `volants-05-1-mage-huluth.jpg` | 1 mage (Huluth) | `20170723_195041.jpg` |

## Assorted conjurations

`17-conjurations/` — Elementals and animals conjured by the mages and clerics. Duration: 3 turns.

| File | Contents | Source photograph |
| --- | --- | --- |
| `conjurations-01-6-chauves-souris.jpg` | 6 chauves-souris | `20170723_200755.jpg` |
| `conjurations-02-3-loups.jpg` | 3 loups | `20170723_200831.jpg` |
| `conjurations-03-6-rats.jpg` | 6 rats | `20170723_200851.jpg` |
| `conjurations-04-6-elementaires-de-feu.jpg` | 6 elementaires de feu | `20170723_200914.jpg` |
| `conjurations-05-6-elementaires-de-terre.jpg` | 6 elementaires de terre | `20170723_200939.jpg` |
| `conjurations-06-6-elementaires-d-air.jpg` | 6 elementaires d'air | `20170723_201000.jpg` |
| `conjurations-07-6-elementaires-d-eau.jpg` | 6 elementaires d'eau | `20170723_201022.jpg` |

## Siege engines

`18-machines-de-siege/` — The Juggernaut, Lord Whismerhill's siege engine (scenario 3).

| File | Contents | Source photograph |
| --- | --- | --- |
| `machines-de-siege-01-juggernaut.jpg` | Juggernaut | `20170723_204336.jpg` |

## Magicians and clerics

`19-magiciens/` — Spellcaster counters for both sides (5 for the darkness, 4 for the Empire, plus Orvarth and Thornz).

| File | Contents | Source photograph |
| --- | --- | --- |
| `magiciens-01-pions-de-magiciens-vue-d-ensemble.jpg` | pions de magiciens (vue d'ensemble) | `20170707_194729.jpg` |
| `magiciens-02-pions-de-magiciens-et-clercs-vue-d-ensemble.jpg` | pions de magiciens et clercs (vue d'ensemble) | `20170707_194615.jpg` |

## Markers and game elements

`20-marqueurs/` — Counters with no combat strength, placed on the map by spells or special abilities.

| File | Contents | Source photograph |
| --- | --- | --- |
| `marqueurs-01-feu-mur-de-flammes.jpg` | feu (mur de flammes) | `20170711_212643.jpg` |
| `marqueurs-02-brume-mur-de-brume.jpg` | brume (mur de brume) | `20170711_213319.jpg` |
| `marqueurs-03-paralysie.jpg` | paralysie | `20170711_213715.jpg` |
| `marqueurs-04-deroute.jpg` | deroute | `20170711_214414.jpg` |
| `marqueurs-05-forteresse-ou-tour-en-ruines.jpg` | forteresse ou tour en ruines | `20170711_215353.jpg` |
| `marqueurs-06-breche-dans-un-mur.jpg` | breche dans un mur | `20170711_215436.jpg` |

## Overviews

`21-vues-d-ensemble/` — General photographs of the counter sheets and of the storage.

| File | Contents | Source photograph |
| --- | --- | --- |
| `vues-d-ensemble-01-planches-de-pions.jpg` | planches de pions | `20170707_194529.jpg` |
| `vues-d-ensemble-02-boite-de-rangement-des-pions.jpg` | boite de rangement des pions | `20170707_195114.jpg` |
| `vues-d-ensemble-03-pions-en-vrac-vue-1.jpg` | pions en vrac (vue 1) | `20170403_163205.jpg` |
| `vues-d-ensemble-04-pions-en-vrac-vue-2.jpg` | pions en vrac (vue 2) | `20170403_163157.jpg` |
---

## Caveats on the inventory

- **Chaos — heavy cavalry**: the blog source reuses the same photograph
  (`20170718_125449.jpg`) for "6 infanteries de puissance 10" and for
  "5 cavaleries lourdes (renforts)". The photograph has been filed only once, under the infantry;
  the photograph of the Chaos heavy cavalry is therefore missing from the source.
- The "(renforts ?)" labels with a question mark carry over the source's uncertainties: the rules
  do not say which Yzent and Chaos units are the starting troops and which are the reinforcements.
- The non-humans' initials (`h`, `K`, `m`, `o`, `bug`) are explained nowhere in the rules; the
  interpretations offered are the article author's.
- **Incomplete readings in `pions.json`**: on five photographs the counter is cropped or the value
  illegible, and the field stays `null` — `yzent-02` (the bottom of the counter), `orques-07` (no
  firing values printed), `morts-vivants-05` (an isolated "5" at the bottom centre),
  `conjurations-01` (no ground movement), `conjurations-07` (bottom left). The `remarques` field
  says so each time.
- **Two files in `19-magiciens/` are not counters**: they are the Alliance and Forces Noires record
  sheets (turn sequence, results table, tracks for the mages' magic points). The names they carry
  are recorded in `remarques` in `pions.json`: THORNZ, MIRZ, ORF, CHÊL, ELIM on the Alliance side;
  ORVARTH, VIZ, ÔM, HAART, GÔL, ZORN on the Forces Noires side. Likewise,
  `vues-d-ensemble-01-planches-de-pions.jpg` in fact shows the booklet's "Symboles" page, not the
  counter sheets.

## Images from `material/base_material/images/` not reproduced here

These 17 files are not counters and remain only in `material/base_material/images/`: the cover and
box photographs (`pic73874_md.jpg`, `20170707_194444.jpg`,
`0f6274f5782e7183198dcabff5b13ed1267d.jpeg`, `HE_BGG_2.jpg`), views of the map and its regions
(`20170707_194834.jpg`, `20170403_163236.jpg`, `20170710_134448.jpg`, `20170710_134527_001.jpg`,
`20170710_134550.jpg`, `20170710_134613.jpg`, `20170710_134853.jpg`, `20170710_143554.jpg`,
`20170710_150031_001.jpg`), the *Fiefs et Empires* expansion (`fiefs.jpeg`), the *Chroniques de la
Lune Noire* comic (`chroniques.jpg`), and the blog's furniture
(`blogger_logo_round_35.png`, `121110-F-VO466-040.JPG`).
