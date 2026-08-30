# `moteur/` — le cœur du jeu

Les règles d'*Ave Tenebrae* en Python, sans rien qui touche au web : `application/` ne fait que
servir ce que ce paquet décide. Un déplacement n'est jamais jugé légal par le navigateur.

| Fichier | Contenu |
| --- | --- |
| `hexagone.py` | la carte lue en constante, et la classe `Hex` |

## La classe `Hex`

```python
from moteur.hexagone import Hex

depart = Hex(13, -4, -9)      # ou Hex(13, -4) : s se déduit de q + r + s = 0
depart = Hex.depuis_cle("13,-4,-9")
Hex()                          # hexagone vide, sans position

depart.terrain                 # 'plaine' — le terrain principal
depart.elements                # ('plaine',) — tout ce que porte la case, terrain en tête
depart.voisins()               # les six hexagones adjacents encore sur la carte
depart.deplacements(5)         # liste d'objets Hex atteignables avec 5 points
depart.en_dict()               # {'q': 13, 'r': -4, 's': -9, 'terrain': 'plaine'}
```

`deplacements()` est un parcours de Dijkstra borné par le budget de mouvement. Les coûts sont des
`fractions.Fraction` et non des flottants : une route vaut un tiers de point, et un chemin de cinq
points ne doit pas dériver à l'arrondi.

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

Avec 5 points de mouvement, une unité atteint de 60 à 100 cases en plaine, une vingtaine au cœur
d'un bois.

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
- **Ni empilement, ni zones de contrôle, ni vol, ni pouvoirs** : toutes les unités sont terrestres
  et de mouvement 5, et deux unités peuvent viser la même case.
