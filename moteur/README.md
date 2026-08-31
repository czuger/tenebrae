# `moteur/` — le cœur du jeu

Les règles d'*Ave Tenebrae* en Python, sans rien qui touche au web : `application/` ne fait que
servir ce que ce paquet décide. Un déplacement n'est jamais jugé légal par le navigateur.

| Fichier | Contenu |
| --- | --- |
| `hexagone.py` | la carte lue en constante, et la classe `Hex` |
| `pion.py` | le catalogue des pions lu en constante, et la classe `Pion` |
| `plateau.py` | l'état de partie : quels pions sont posés, où, et dans quel camp |
| `scenario.py` | les mises en place fixées dans `scenarios/`, et le `Plateau` qu'elles donnent |
| `phase.py` | la machine à états d'un tour : quel camp joue, et à quoi (`Tour`) |
| `combat.py` | la résolution d'un combat d'après le Tableau I du fascicule |

Les deux premiers sont des constantes — la carte et les cartons sont imprimés depuis 1986. Le
troisième est le seul objet mutable du moteur : les positions, elles, changent. Le quatrième dit
d'où elles partent.

## La classe `Hex`

```python
from moteur.hexagone import Hex

depart = Hex(13, -4, -9)      # ou Hex(13, -4) : s se déduit de q + r + s = 0
depart = Hex.depuis_cle("13,-4,-9")
Hex()                          # hexagone vide, sans position

depart.terrain                 # 'plaine' — le terrain principal
depart.elements                # ('plaine',) — tout ce que porte la case, terrain en tête
depart.voisins()               # les six hexagones adjacents encore sur la carte
depart.distance(autre)         # à vol d'oiseau, en cases — sans égard au terrain
depart.deplacements(5)         # liste d'objets Hex atteignables avec 5 points
depart.en_dict()               # {'q': 13, 'r': -4, 's': -9, 'terrain': 'plaine'}
```

`deplacements()` est un parcours de Dijkstra borné par le budget de mouvement — celui du pion qui
part, `Pion.points_de_mouvement` (voir plus bas) ; sans argument, le forfait de 5 points. Les
coûts sont des `fractions.Fraction` et non des flottants : une route vaut un tiers de point, et un
chemin de cinq points ne doit pas dériver à l'arrondi.

Deux arguments nommés y ajoutent l'adversaire — `ennemis` et `sous_controle`, des ensembles de
clés « q,r,s » (voir « Zones de contrôle »). Sans eux, la carte est réputée déserte et le parcours
ne connaît que le terrain.

La carte est lue **une fois, à l'import du module** — le plateau est imprimé, il ne change pas en
cours de partie. C'est `game_box/carte_details.json` qui est lu, et non `carte.json` : sa tête de
liste donne le même terrain principal, mais lui seul conserve les 58 routes et chemins que la règle
de priorité de la carte masque sous un bois ou un massif. Sans lui, la route noire du nord
n'existerait pas pour le mouvement.

## La carte du jeu — la transcription, corrigée

La transcription automatique comporte des erreurs, relevées à l'œil sur la page `/admin/map_fix`
de l'application et écrites dans `game_box/map_fix.json`. Le moteur les applique par-dessus :

| Constante | Contenu |
| --- | --- |
| `CARTE_TRANSCRITE` | `carte_details.json` tel quel — ce que produit `extraction_carte.py` |
| `CORRECTIONS_APPLIQUEES` | `map_fix.json` tel qu'il était au démarrage : `« q,r,s » → terrain` |
| `CARTE` | la première recouverte par la seconde : **la carte sur laquelle le jeu se joue** |

`corriger(transcription, corrections)` est une fonction pure. Une correction ne porte que sur le
**terrain principal** : il prend la tête à la place de celui que la priorité de la carte y avait
mis, et les éléments secondaires suivent.

```
carte_details : ["bois", "route"]   +   map_fix : "colline"   →   ("colline", "route")
```

C'est ce qui permet à un bois de la route noire d'être corrigé en colline sans couper la route.
Une clé que la transcription ne connaît pas est ignorée : on ne crée pas d'hexagone hors carte.

Les deux fichiers restent séparés — `carte_details.json` sort du script et n'est jamais retouché —
et **le recouvrement n'a lieu qu'au démarrage** : corriger la carte pendant que le serveur tourne
ne change rien tant qu'on ne l'a pas relancé. La page d'admin le dit.

## La classe `Pion`

```python
from moteur.pion import CATALOGUE, pion

cavalerie = pion("reissland-02-8-cavaleries")
cavalerie.force                # 5 — haut à gauche du carton
cavalerie.mouvement            # 8 — haut à droite
cavalerie.tir, cavalerie.portee        # (None, None) : elle ne tire pas
cavalerie.mouvement_vol                # None — le chiffre entre parenthèses, quand il y en a un
cavalerie.facultes_speciales           # None — la lettre du haut au centre : « P », « s »…
cavalerie.points_de_mouvement          # 8 — ce que le déplacement consomme
cavalerie.est_une_unite                # True — un marqueur répondrait False
cavalerie.camp                         # 'alliance' — 'tenebres' ou 'neutre' pour d'autres
cavalerie.exerce_une_zone_de_controle  # True

Hex(1, 26, -27).deplacements(cavalerie.points_de_mouvement)
```

Les valeurs viennent de `game_box/pions/pions.json`, relevé à l'œil sur les 127 photos de
`game_box/pions/` (voir `game_box/pions/README.md`). Le fichier est lu **une fois, à l'import** :
comme la carte, les cartons sont imprimés, ils ne changent pas en cours de partie.

Une valeur absente du carton — ou illisible sur la photo — vaut `None`, et `remarques` dit
laquelle. Seul `points_de_mouvement` tranche, parce que le déplacement a besoin d'un nombre :

| Le pion porte | `points_de_mouvement` |
| --- | --- |
| un mouvement au sol | ce mouvement, de 1 à 20 points |
| un mouvement en vol seul | ce vol, faute de mieux — la seule chauve-souris |
| aucune valeur | `IMMOBILE`, c'est-à-dire 0 : un marqueur ne se déplace pas |

`est_une_unite` sépare les 115 unités des 12 photos qui n'en sont pas : les 6 marqueurs, les
2 feuilles de suivi et les 4 vues d'ensemble ne portent aucune valeur chiffrée.

### Les camps

Le camp n'est **pas** dans `pions.json` : il n'est pas imprimé sur le carton. Il vient de la
section « Camps » de `game_box/pions/README.md`, tenue ici dans `CAMPS`, faction par faction :

| Camp | Factions | Pions |
| --- | --- | --- |
| `ALLIANCE` | Reissland, Empire Tharque, Templiers, Population, Empire de Lynn, Elfes, Nains, Dragons | 47 |
| `TENEBRES` | Yzent, Chaos, Non-humains, Orques, Sahuaguins, Morts-vivants, Démons, Juggernaut | 56 |
| `NEUTRE` | Volants, conjurations, magiciens, marqueurs, vues d'ensemble | 24 |

`ADVERSAIRES` dit qui s'oppose à qui : l'alliance et les ténèbres, et personne d'autre. **Le
neutre n'a pas d'adversaire** — il ne gêne personne et personne ne le gêne. Les scénarios y
mettraient plus de nuance (l'Empire de Lynn n'entre qu'au scénario 3, les Nains au 4, les Volants
au 5, Yzent est un « allié d'opportunité ») : le moteur n'en sait rien.

## Zones de contrôle

> Chaque unité exerce une influence particulière sur les six cases qui environnent celle qu'elle
> occupe : ces six cases constituent sa « zone de contrôle ».

`zone_de_controle(hexagones)` rend ces cases, en clés « q,r,s ». `Hex.deplacements()` en tient
compte par ses deux arguments nommés :

| Argument | Contenu | Effet |
| --- | --- | --- |
| `ennemis` | les cases que l'adversaire occupe | on n'y entre pas : le mouvement n'engage pas le combat |
| `sous_controle` | les cases que ses zones couvrent | on y entre au tarif du terrain, et on s'y arrête |

Le fascicule tient en trois lignes, et le parcours en trois règles :

| La règle | Dans le parcours |
| --- | --- |
| « pénétrer […] sans dépense de points supplémentaires » | la case coûte ce que coûte son terrain |
| « elle doit s'arrêter dès qu'elle y est entrée » | d'une case sous contrôle, on ne repart pas |
| « on ne peut passer d'une zone à une autre qu'après être sorti de la première » | la case de départ, seule case sous contrôle d'où l'on progresse encore, ne mène qu'à des cases libres |

Une unité qui **commence** son mouvement sous contrôle en sort donc, mais par une case libre : la
figure de l'exemple du fascicule, où C contourne X1 pour atteindre X2 et « dépensera donc 4 points
de mouvement au lieu de 2 », se retrouve telle quelle dans
`moteur/tests/test_zone_de_controle.py`.

## La classe `Plateau`

```python
from moteur.plateau import Plateau

plateau = Plateau([(Hex(1, 26, -27), pion("elfes-01-5-infanteries"))])
plateau.poser(hexagone, pion)          # une case, un pion ; retirer() et vider() défont
plateau.pion_sur(hexagone)             # le Pion posé là, ou None
plateau.cases_tenues_par("alliance")   # les clés « q,r,s » de ce camp
plateau.adversaires_de("alliance")     # celles du camp opposé
plateau.zones_de_controle_contre("alliance")
plateau.mouvement_de(hexagone)         # les points du pion posé
plateau.deplacements(hexagone)         # ses cases d'arrivée, zones de contrôle comprises
plateau.deplacer(depart, arrivee)      # recalcule, applique, et dit si c'est fait
```

C'est le plateau qui réunit les trois : le pion posé donne son mouvement et son camp, le camp
donne les adversaires, les adversaires donnent les zones de contrôle.

- **Le pion posé fait foi.** `deplacements(hexagone, pion)` accepte un pion en second argument,
  mais il ne sert qu'à interroger une case vide — pour savoir où telle unité irait si on l'y
  mettait. Sans pion du tout, le forfait s'applique et, faute de camp, personne n'est un
  adversaire.
- **Une case amie se traverse mais ne se prend pas.** Le fascicule autorise le passage
  (« une unité peut traverser une case occupée par une unité de la même armée ») et interdit
  l'empilement : les cases occupées sont donc retirées des destinations, pas du parcours.

## Les scénarios

```python
from moteur.scenario import scenario

guerre_des_nains = scenario(4)         # lu dans scenarios/scenario-04-…json
guerre_des_nains.armees                # une entrée par joueur : camp, consigne, ancre, magie
guerre_des_nains.camps                 # ('alliance', 'tenebres')
guerre_des_nains.placement             # « q,r,s » → clé de pion
len(guerre_des_nains)                  # 52 unités
guerre_des_nains.plateau()             # un Plateau neuf, chaque pion sur sa case
```

Le fascicule décrit une mise en place en une phrase — « l'armée naine se masse au sud du volcan de
Toth » — et ne dit jamais quel pion va sur quelle case. Le passage de la phrase aux hexagones a
été fait une fois pour toutes, hors du code, et vit dans `scenarios/*.json` : **le moteur ne fait
que lire ce fichier**. Le format, le détail du scénario n° 4 et les réserves qui vont avec sont
dans `scenarios/README.md`.

`plateau()` rend un `Plateau` **neuf** à chaque appel : deux parties ne partagent pas leurs
positions. Une clé de pion inconnue du catalogue, ou une case hors carte, arrête la lecture —
mieux vaut un scénario refusé qu'une armée amputée sans que personne ne le voie.

## Coût du mouvement

D'après le *Tableau des terrains* du fascicule (`game_box/ave_tenebrae_regles.md`) :

| Terrain | Coût d'entrée |
| --- | --- |
| `plaine`, `village`, `ville`, `ile`, `tour` | 1 point |
| `bois`, `colline`, `ruines` | 2 points |
| `route` → `route` | ⅓ de point (« ROUTES × 3 ») |
| `chemin` → `chemin` | ½ point (« CHEMINS × 2 ») |
| `lac`, `riviere`, `faille`, `fort`, `chateau` | infranchissable |
| `montagne` | infranchissable, sauf depuis une colline ou une autre montagne, ou par une voie qui la traverse |

Le tarif de la voie ne vaut que si on la suit d'une case à l'autre : « si une unité doit emprunter
une route au cours d'un mouvement, et si elle ne se trouve pas sur cette route au début de son
déplacement, elle doit d'abord utiliser le nombre de points de mouvements nécessités par la nature
du terrain qui la sépare de la route ».

Les cartons vont de 1 point (les démons protoplasmiques) à 20 (le demi-dieu Azolhim) ; 4 est la
valeur la plus courante, portée par 35 pions. Ce que cela donne en plaine, en cases atteintes :

| Points | Cases atteintes en plaine |
| --- | --- |
| 2 — le bélier d'Yzent | une vingtaine |
| 4 — l'infanterie de l'Empire | une soixantaine |
| 5 — l'ancien forfait | de 60 à 100 |
| 8 — la cavalerie de Reissland | plus de deux cents |
| 20 — le demi-dieu Azolhim | un millier, soit deux hexagones de la carte sur cinq |

Au cœur d'un bois, où chaque case coûte 2 points, il faut compter trois à quatre fois moins.

## Les phases de jeu

```python
from moteur.phase import Tour

tour = Tour(("alliance", "tenebres"), {"alliance": "Nains", "tenebres": "Orques"})
tour.libelle                 # « Phase de mouvement — Nains »
tour.type_de_phase           # « mouvement » — jamais « magie »
tour.autorise_mouvement("alliance")   # True
tour.suivante()              # passe au combat des Nains ; la magie est franchie d'elle-même
tour.numero                  # 1, puis 2 quand la séquence reboucle
```

Le fascicule (`game_box/ave_tenebrae_regles.md`, § « Phases de jeu ») fixe l'ordre : chaque joueur
enchaîne **mouvement → magie → combat**, puis c'est au joueur suivant, en boucle. `Tour` tient ce
curseur. La **phase de magie n'est pas implémentée** : `suivante()` la saute, elle n'est jamais
courante. `autorise_mouvement` / `autorise_combat` disent si un camp donné peut agir maintenant —
c'est ce que l'application consulte pour bloquer un déplacement hors phase.

`Tour` ne connaît ni le plateau ni les pions : il ne fait qu'ordonner les phases. L'application en
tient un exemplaire, remis à zéro à chaque chargement de la carte, à côté de son `Plateau`.

## Les combats

```python
from moteur.combat import a_portee, livrer_combat, resoudre

a_portee(hex_attaquant, pion_attaquant, hex_cible)   # distance ≤ 1, ou ≤ portée si le pion tire
resoudre([12, 4], pion_defenseur, hex_defenseur, jet=3)   # → « DE », « AE », « EX », « AR », « DR »
resultat = livrer_combat(plateau, hex_cible, [hex_attaquant], jet=3)
resultat.resultat, resultat.elimines, resultat.rapport, resultat.de
```

Le **Tableau I** du fascicule (`§ Combats`) est transcrit tel quel dans `TABLEAU_I` : le rapport
de force en colonnes (de 1-5 à 6-1), le jet de dé en lignes. On additionne la `force` des
attaquants, on la rapporte à celle du défenseur — **arrondi en faveur du défenseur**, borné —, on
lance le dé, on lit la case.

`force` est **la seule valeur du carton que le combat consomme** ; elle sert à la fois d'attaque
et de défense, comme sur le pion. Le *Tableau des terrains* ajoute deux modificateurs, appliqués
d'après le terrain du **défenseur** : sa force est multipliée (× 2 en village, ruines, rivière,
lac ; × 3 en montagne, fort, château ; × 2 en bois pour les seuls Elfes), et l'attaquant gagne
**+ 2 au dé** si le défenseur tient une colline ou un bois.

Le hasard reste au bord du moteur : `jet` est **passé en argument**, jamais tiré ici. C'est
l'application qui lance le dé (`app.lancer_le_de`), ce qui permet aux tests de le fixer.

**Trois issues seulement changent le plateau**, et `livrer_combat` les applique en retirant les
pions : `AE` (attaquant éliminé), `DE` (défenseur éliminé), `EX` (les deux). `AR` et `DR` — les
reculs — sont lus mais laissés sans effet, faute de règle de retraite. Voir les réserves ci-dessous.

## Réserves sur l'interprétation

Comme pour la carte et l'inventaire des pions, les doutes sont conservés, pas tranchés.

- **Le « × 2 » des ruines est lu comme un surcoût**, alors que la même colonne du tableau note
  « × 2 » pour les chemins et « × 3 » pour les routes, où le facteur multiplie le mouvement.
  Prendre les ruines pour un terrain rapide n'a pas de sens ; elles sont donc traitées comme les
  bois et les collines, à 2 points.
- **Rivières et murailles sont des terrains d'hexagone**, pas des côtés : c'est ainsi qu'elles ont
  été transcrites (voir `game_box/carte.md`). Les ponts n'étant pas relevés, aucune rivière n'est
  franchissable — y compris l'accès à Morgenstern.
- **Les collines sont une interprétation du scan**, pas un terrain dessiné : l'accès aux montagnes
  en dépend directement. 42 des 128 hexagones de montagne bordent une colline ou portent une voie ;
  les autres restent inaccessibles au sol.
- **Forts et châteaux sont infranchissables**, faute de savoir à qui ils appartiennent : le
  fascicule les ouvre « par combats ou alliés », ce qui demande un état de partie.
- **Une unité posée sur un lac, une rivière ou la faille ne va nulle part** : ces terrains ne
  s'occupent pas plus qu'ils ne se traversent. Les forts et les châteaux, eux, se tiennent en
  garnison : on en part, on n'y entre pas.
- **Une correction ne porte que sur le terrain principal.** Une route détectée à tort sous un bois
  survit à la correction de ce bois et reste praticable à ⅓ de point : `map_fix.json` ne sait pas
  retirer un élément secondaire. Cela se règle dans `game_box/extraction_carte.py`.
- **Le combat ne lit que la force.** `pions.json` porte aussi le tir et la portée : `combat.py`
  ne s'en sert que pour la portée d'engagement d'un archer, jamais pour un tir résolu à part. Une
  attaque de missile suit le même Tableau I qu'un corps à corps.
- **Le vol n'est pas une règle**, seulement un nombre. Les unités volantes se déplacent au sol,
  avec leur mouvement au sol ; la chauve-souris, dont le mouvement au sol n'a pas pu être lu sur
  la photo, se déplace de son vol (2 points) sur les mêmes règles de terrain. Voler par-dessus un
  lac ou une montagne reste impossible.
- **Cinq mouvements n'ont pas pu être lus** sur la photo du pion (pion rogné, chiffre illisible) :
  ils sont notés dans `pions.json` et repris dans les réserves de `game_box/pions/README.md`.
- **Toutes les unités exercent une zone de contrôle**, alors que le fascicule en dispense les
  leaders et les jeteurs de sorts, les démons et les morts-vivants ordinaires — seuls les trois
  princes-démons et les trois lords sur dragons en exercent chez eux — et les unités tenant une
  forteresse. Ces exceptions sont lisibles dans `pions.json` (`symbole`, `faction`) : les appliquer
  ne demanderait qu'un tri, c'est un choix de ne pas l'avoir fait pour l'instant.
- **« Une zone ne s'exerce pas au-delà d'une rivière, mais franchit les ponts. »** Inapplicable en
  l'état : les rivières sont transcrites comme des terrains d'hexagone et non comme des côtés, et
  aucun pont n'est relevé. Une zone de contrôle franchit donc tout.
- **Le camp est celui de la faction**, sans égard au scénario, et **le neutre n'a pas
  d'adversaire** : volants, conjurations et marqueurs n'arrêtent personne et ne sont arrêtés par
  personne.
- **Un scénario n'est qu'une position de départ.** `scenario.py` pose les pions et s'arrête là :
  ni renforts, ni condition de victoire. Le tour de jeu, lui, existe désormais — `phase.py` —,
  mais il vit à côté du scénario, pas dedans, et le potentiel de magie que le fascicule donne à
  chaque camp reste enregistré sans que rien ne le dépense.
- **La magie n'est pas jouée.** La phase de magie est prévue dans la séquence du fascicule ;
  `Tour.suivante()` la franchit sans rien faire. Sorts, potentiel de magie, jeteurs de sorts et
  facultés spéciales (peur, paralysie, jets de protection) attendent.
- **Le combat s'arrête aux trois éliminations.** `AR` et `DR` — les reculs — ne sont pas joués,
  donc il n'y a ni retraite, ni élimination faute de retraite, ni avance après combat. `EX` retire
  **tous** les attaquants, sans le tri « force au moins égale » du fascicule. Ni charge de
  cavalerie (× 2), ni phalange (× 3), ni alternance jour/nuit, ni immunité des tireurs au recul :
  la force du carton et le terrain du défenseur sont les seuls facteurs.
- **Un combat par clic, pas par phase entière.** Le fascicule limite chaque unité à une attaque
  par phase et chaque cible à une attaque par phase : rien ne l'impose ici, l'application résout
  chaque combat déclaré sans tenir de compte.
- **L'empilement n'est pas géré au-delà d'une unité par case** : le fascicule autorise 3 unités
  dans une ville, un village ou une citadelle, et ne compte ni les leaders ni les magiciens. Le
  plateau, lui, ne pose qu'un pion par case.
- **Les zones de contrôle ne pèsent que sur le mouvement.** Leurs autres effets — l'interdiction
  de reculer dedans, l'unité éliminée faute de retraite, l'invisibilité qui les ignore — supposent
  une règle de retraite qui n'existe pas. Toutes les unités restent terrestres.
