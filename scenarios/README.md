# `scenarios/` — les mises en place, fixées une fois pour toutes

Le fascicule décrit chaque scénario en une phrase — « l'armée naine se masse au sud du volcan de
Toth » — et ne dit jamais quel pion va sur quelle case. Le passage de la phrase aux hexagones est
un travail d'interprétation : il a été fait **une fois**, et son résultat vit ici, un fichier JSON
par scénario. Le moteur ne fait que le lire (`moteur/scenario.py`), et l'application le pose sur
la carte au chargement de `/`.

C'est ce qui a remplacé le tirage au hasard de dix pions : les déplacements s'éprouvent maintenant
sur une position connue, la même à chaque rechargement.

| Fichier | Scénario |
| --- | --- |
| `scenario-04-la-guerre-des-nains.json` | n° 4 — La guerre des nains : Nains contre Orques |

Les scénarios 1, 2, 3 et 5 du fascicule ne sont pas encore fixés.

## Le format

Nommage : `scenario-NN-<titre-slugifie>.json`, `NN` sur deux chiffres — c'est de là que
`moteur.scenario.scenarios_disponibles()` tire le numéro.

| Clé | Contenu |
| --- | --- |
| `numero`, `nom` | le numéro du scénario dans le fascicule et son titre |
| `source` | où lire le texte du scénario, dans la transcription des règles |
| `armees` | une entrée par joueur, dans l'ordre des joueurs (voir ci-dessous) |
| `placement` | `"q,r,s"` → clé de pion : **la mise en place elle-même**, une unité par case |

Chaque entrée d'`armees` porte le `joueur`, son `camp` (`alliance` / `tenebres`, celui que
`moteur.pion` donne à la faction), le nom de l'`armee`, la `consigne` du fascicule recopiée mot à
mot, l'`ancre` — l'hexagone d'où part le déploiement, celui que la consigne désigne —, le nombre
d'`unites` posées, le potentiel de `magie` du camp et son `jeteur_de_sorts` (`null` si aucun pion
ne le représente).

Les clés de pions sont celles de `game_box/pions/pions.json` ; un pion nommé plusieurs fois est
posé autant de fois, une case chacun — la boîte porte bien 15 pions d'infanterie orque sous une
seule photo.

## Scénario n° 4 — La guerre des nains

> Afin de répondre aux raids incessants des orcs, le chef nain Grundt ordonna à son armée
> l'attaque immédiate de l'Orcreich et l'extermination totale des orcs.

48 unités : **18 nains** (joueur 1, alliance) contre **30 orques** (joueur 2, ténèbres). L'armée
naine — 5 infanteries, 4 arbalétriers, 4 arbalétriers lourds et 5 phalanges — et l'armée orque
**hors renforts** — 15 infanteries, 5 cavaleries, 5 archers et 5 archers montés.

**Ne sont posées que les unités que le moteur sait jouer.** Les leaders des deux camps et le mage
Vorgtd restent en boîte : le moteur ne leur donne aucun effet — ni commandement, ni bonus de
combat, ni ralliement, ni sortilège —, et une unité qui ne fait rien de plus qu'une autre n'a rien
à faire dans une ligne de bataille. Les deux camps se battent donc à armes égales, au carton et au
terrain. Les trois pions correspondants (`nains-05-2-leaders`, `nains-06-1-mage-vorgtd`,
`orques-08-1-leader`) restent dans `game_box/pions/` : les reposer le jour où le moteur leur
donnera un effet ne demandera que de les ajouter au placement.

### Le déploiement

Les deux armées se rangent dans le couloir de plaine qui va du lac, au nord, aux plaines du sud,
entre les collines de l'ouest et le massif de montagnes qui ferme l'est à partir de la colonne 52.

**Les nains sont en trois rangs**, sur une ligne de front donnée à la main : les sept hexagones
qui vont de `50,-7,-43` à `45,-8,-37`. L'ordre le long de cette ligne est celui de la consigne —
*infanterie d'abord, phalange ensuite* :

| Rang | Ce qui le tient |
| --- | --- |
| La ligne de front | les 5 infanteries depuis `50,-7,-43`, puis 2 phalanges jusqu'à `45,-8,-37` |
| Deuxième rang | les 3 autres phalanges à l'ouest, 3 arbalétriers lourds à l'est |
| Troisième rang | le 4ᵉ arbalétrier lourd et les 4 arbalétriers |

Les arbalétriers, arme de tir, sont donc **tous en arrière de toute unité de contact** : pas un
n'est aussi près des orques que la moindre infanterie ou phalange.

**Les orques sont plus mêlés**, mais leur ordre de bataille se lit du sud au nord :

| Depuis les nains | Ce qui s'y tient |
| --- | --- |
| Le front | 14 infanteries sur deux rangs, plus une garnison dans le fort de `51,-13,-38` |
| Derrière | les 5 archers à pied, collés au second rang d'infanterie |
| Plus loin | les 5 archers montés, qui font la liaison |
| La rive du lac | les 5 cavaleries, **toutes**, sur la ligne 8 |

Tout ce que les nains ont devant eux à 4 cases ou moins est donc de l'infanterie orque ; les dix
archers ne forment qu'un seul bloc derrière elle ; et les cinq cavaliers sont les seules unités du
plateau à border l'eau — c'est ce qui les distingue des archers montés, juste derrière eux.

### Les ancres

L'`ancre` n'est pas le centre d'un cercle : c'est **le point d'où part le déploiement**, et les
deux sont occupés.

| Ancre | Hexagone | Ce qui la tient |
| --- | --- | --- |
| Sud du volcan de Toth (nains) | `50,-7,-43` | le premier hexagone de la ligne de front, une infanterie |
| L'Orcreich (orques) | `51,-13,-38` | le fort, tenu par une infanterie en garnison |

Les deux fronts restent à **3 cases** l'un de l'autre, exactement : le premier tour sert à
marcher, pas à combattre. Chaque armée est d'un seul tenant — chaque unité en touche au moins une
autre de son camp — et aucune n'est posée dans un cul-de-sac.

Les nains tiennent 15 cases de plaine et 3 de chemin. Les orques tiennent de la plaine (15), les
collines qui descendent du lac (8), le chemin qui traverse l'Orcreich (6) et le fort de
`51,-13,-38` — ce fort est une correction relevée à la main dans `game_box/map_fix.json`.

### Réserves sur cette mise en place

Comme ailleurs dans le dépôt, les incertitudes sont conservées, pas résolues.

- **Les hexagones ne sont pas dans le fascicule.** « Au sud du volcan de Toth », « à l'intérieur
  de l'Orcreich » : les ancres et le dessin des deux armées sont une lecture de la carte, pas une
  donnée du jeu. Une autre lecture donnerait un autre déploiement également recevable.
- **La ligne de front naine a été donnée à la main**, par ses deux bouts, et le reste du
  déploiement s'y accroche. Elle ne sort ni du fascicule ni de la carte.
- **Les leaders et le mage sont écartés faute d'effet dans le moteur**, et non parce que le
  scénario les refuse : le fascicule donne un leader à chaque camp et Vorgtd aux nains.
- **Le nécromant mineur orque n'est pas posé** non plus, mais pour une autre raison : le scénario
  le donne au joueur n° 2 (20 points de magie) et **aucun pion ne le représente** —
  `game_box/pions/11-orques/` n'en contient pas, et `19-magiciens/` n'a que deux vues d'ensemble.
- **Les deux potentiels de magie restent notés** dans `armees` (45 pour les nains, 20 pour les
  orques) alors que le `jeteur_de_sorts` des deux camps est `null` : ces nombres viennent du
  fascicule, et c'est ce qu'il faudra dépenser le jour où la magie se jouera.
- **Les renforts orques restent en boîte** (`orques-05` à `orques-07`) : le scénario n'en prévoit
  pas.
- **La magie n'est pas jouée** : ni sortilège, ni dépense, ni phase qui en fasse quelque chose.
  C'est pour cela que le mage est resté en boîte, et non l'inverse.
- **La condition de victoire n'est pas modélisée** — « le vainqueur est celui qui exterminera
  l'autre » : le moteur résout les combats un par un, mais ne dit jamais que la partie est finie.

## Tests

`moteur/tests/test_scenario.py`, depuis la racine du dépôt :

```
python3 -m pytest moteur/tests/test_scenario.py
```

Il éprouve la lecture des fichiers, les effectifs annoncés contre les pions réellement posés, la
forme des deux déploiements, et la cohérence avec la carte : chaque case existe, aucune unité sur
un terrain impraticable, et chacune a au moins une case où aller. **Une correction de terrain qui
mettrait une unité dans un lac se verrait donc ici**, et non en cours de partie.

La forme du déploiement est éprouvée telle qu'elle a été demandée, et non recopiée : le test
retrace la ligne naine entre ses deux bouts (`ligne_cubique`) au lieu d'en lister les sept clés,
et vérifie ensuite l'ordre de bataille par les distances — les arbalétriers derrière les unités de
contact, l'infanterie orque devant tout le reste, les archers en un seul bloc derrière elle, la
cavalerie seule à border le lac.
