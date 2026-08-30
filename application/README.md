# `application/` — la carte affichée dans le navigateur

Première étape vers le jeu : une application Flask qui sert `game_box/map.jpg`, tire **dix
hexagones au hasard**, pose un pion sur chacun, et laisse le navigateur faire la géométrie.

## Lancer

Depuis ce répertoire, avec le virtualenv pyenv `tenebrae` :

```
python3 app.py
```

puis <http://127.0.0.1:5000/>. Chaque rechargement rejoue un tirage.

Dépendance : `Flask` (plus `pytest` et `pytest-playwright` pour les tests).

## Comment ça marche

Le serveur ne dessine rien : il passe deux JSON au gabarit, dans des champs cachés
(`#pions` et `#grille`), et `static/carte.js` s'en sert.

| Champ caché | Contenu |
| --- | --- |
| `#pions` | dix entrées `{q, r, s, image, nom}` — la position en coordonnées cubiques et le pion tiré |
| `#grille` | `origine`, `matrice` et `taille_pion` : le calage de la grille sur `map.jpg` |

Le JavaScript convertit chaque hexagone en pixels avec la formule relevée dans
`game_box/carte.md` :

```
centre(q, r) = origine + matrice · (q, r)
```

Le pion est ensuite **centré** sur ce point (`translate(-50%, -50%)`) puis **incliné au hasard de
± 5°**, pour que le plateau n'ait pas l'air posé à la règle. Les positions sont exprimées en
pixels de `map.jpg` : la carte est portée à sa taille naturelle par `#plateau`, que le
JavaScript met ensuite à l'échelle pour tenir dans la fenêtre.

## Choix du tirage

- Les hexagones sont tirés dans `game_box/carte.json`, **hors terrains infranchissables**
  (`lac`, `montagne`, `faille`, `riviere` — voir le tableau des terrains) : 2008 hexagones sur 2280.
- Les pions sont tirés dans `game_box/pions/`, **hors vues d'ensemble** : les 4 photos de
  `21-vues-d-ensemble/` et les 2 planchettes de suivi de `19-magiciens/` ne montrent pas un pion
  isolé. Restent 121 pions sur 127.
- Le tirage ne tient aucun compte des règles : ni camp, ni scénario, ni empilement. Un pion
  peut sortir plusieurs fois, un mort-vivant peut se retrouver en pleine forêt elfique.

## Tests

```
python3 -m pytest
```

`tests/test_serveur.py` interroge Flask sans navigateur (contenu des champs cachés, cohérence
des coordonnées, terrains, fichiers servis). `tests/test_plateau.py` ouvre la page dans Chromium
avec Playwright et vérifie le rendu : dix pions chargés, chacun centré sur le centre calculé de
son hexagone à moins d'un pixel, incliné de moins de 5°, et la carte qui reste à l'échelle après
redimensionnement.

Les tests de navigateur demandent Chromium :

```
python3 -m playwright install chromium
```
