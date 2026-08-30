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

52 unités : **21 nains** (joueur 1, alliance) contre **31 orques** (joueur 2, ténèbres). Toute
l'armée naine — 5 infanteries, 4 arbalétriers, 4 arbalétriers lourds, 5 phalanges, 2 leaders et le
mage Vorgtd — et toute l'armée orque **hors renforts** — 15 infanteries, 5 cavaleries, 5 archers,
5 archers montés et le leader.

Les deux ancres sont **relevées à l'œil sur la carte** et ne sortent pas du scan :

| Ancre | Hexagone | Ligne |
| --- | --- | --- |
| Sud du volcan de Toth (nains) | `53,-9,-44` | 17 |
| L'Orcreich (orques) | `53,-15,-38` | 11 |

Elles sont à 6 cases l'une de l'autre, les nains au sud. Le déploiement part de l'ancre et
s'étend en couronnes successives : **les orques en cercle** autour de la leur (anneaux 0, 1 et 2
pleins, puis 12 cases sur les 18 de l'anneau 3), **les nains en demi-cercle vers le sud**, aucune
unité naine ne remontant au nord de la ligne de son ancre. Aucune des deux armées ne dépasse
3 cases de son ancre, chaque unité en touche au moins une autre de son camp, et les deux fronts
restent à **3 cases** l'un de l'autre : le premier tour sert à marcher, pas à combattre.

Les nains tiennent 21 cases de plaine. Les orques tiennent surtout le chemin qui traverse
l'Orcreich (14 cases) et de la plaine (12), plus 3 collines, le village de `53,-18,-35` et le fort
de `51,-13,-38` — ce fort est une correction relevée à la main dans `game_box/map_fix.json`, et
une infanterie orque y tient garnison.

### Réserves sur cette mise en place

Comme ailleurs dans le dépôt, les incertitudes sont conservées, pas résolues.

- **Les hexagones ne sont pas dans le fascicule.** « Au sud du volcan de Toth », « à l'intérieur
  de l'Orcreich » : les ancres et le dessin des deux masses sont une lecture de la carte, pas une
  donnée du jeu. Une autre lecture donnerait un autre déploiement également recevable.
- **Le nécromant mineur orque n'est pas posé.** Le scénario le donne au joueur n° 2 (20 points de
  magie), mais `game_box/pions/11-orques/` ne contient aucun pion de nécromant, et
  `19-magiciens/` n'a que deux vues d'ensemble. Son potentiel est noté dans `armees`, son
  `jeteur_de_sorts` est `null`.
- **Les renforts orques restent en boîte** (`orques-05` à `orques-07`) : le scénario n'en prévoit
  pas.
- **La magie n'est pas jouée.** Les 45 points de Vorgtd et les 20 du nécromant sont enregistrés
  et rien ne les dépense : ni sorts, ni tour de jeu, ni combat dans le moteur à ce stade.
- **La condition de victoire n'est pas modélisée** — « le vainqueur est celui qui exterminera
  l'autre » suppose un combat, qui n'existe pas encore.
- **L'ancre de l'Orcreich n'est pas le fort.** Le fort relevé à `51,-13,-38` est à 2 cases de
  l'ancre `53,-15,-38` ; laquelle des deux cases le fascicule appelle « Orcreich » n'est pas
  tranché, et le déploiement couvre les deux.

## Tests

`moteur/tests/test_scenario.py`, depuis la racine du dépôt :

```
python3 -m pytest moteur/tests/test_scenario.py
```

Il éprouve la lecture des fichiers, les effectifs annoncés contre les pions réellement posés, la
forme des deux déploiements, et la cohérence avec la carte : chaque case existe, aucune unité sur
un terrain impraticable, et chacune a au moins une case où aller. **Une correction de terrain qui
mettrait une unité dans un lac se verrait donc ici**, et non en cours de partie.
