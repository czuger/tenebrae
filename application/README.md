# `application/` — la carte affichée dans le navigateur

Une application Flask qui sert `game_box/map.jpg`, tire **dix hexagones au hasard**, pose un pion
sur chacun, et laisse le navigateur faire la géométrie. Cliquer un pion montre en **fantômes** les
cases où il peut aller ; cliquer un fantôme l'y déplace.

Les règles ne sont pas ici : les déplacements viennent de `moteur/`, l'application ne fait que les
servir. Le JavaScript ne décide jamais de la légalité d'un mouvement.

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

## Cliquer, montrer, déplacer

Un clic est d'abord ramené en coordonnées cubiques : la même matrice, **inversée**, puis un
arrondi cubique donne l'hexagone visé. C'est la seule chose que le navigateur calcule — la suite
est un aller-retour avec le serveur.

| Route | Réponse |
| --- | --- |
| `GET /deplacements?q=&r=&s=` | `{"depart": {…}, "mouvement": 5, "hexagones": [{q, r, s, terrain}, …]}` |
| `POST /deplacer` — corps `{"depart": {…}, "arrivee": {…}}` | `{"autorise": bool, "depart": {…}, "arrivee": {…}}` |

Coordonnées illisibles ou de somme non nulle → 400 ; hexagone hors carte → 404.

1. clic sur un pion → `/deplacements` → un fantôme par hexagone rendu : la même image, à 50 %
   d'opacité, sous les pions posés, centrée et inclinée comme eux ;
2. clic sur un fantôme → `/deplacer` → le pion se repose sur la case, de travers autrement ;
3. clic ailleurs, ou de nouveau sur le pion sélectionné → les fantômes s'effacent.

`/deplacer` recalcule la portée côté serveur au lieu de croire le navigateur : c'est là que
viendra se greffer l'état de partie (qui occupe quelle case, dans quel camp).

## Choix du tirage

- Les hexagones sont tirés dans `game_box/carte.json`, **hors terrains infranchissables**
  (`lac`, `montagne`, `faille`, `riviere` — voir le tableau des terrains) : 2008 hexagones sur 2280.
- Les pions sont tirés dans `game_box/pions/`, **hors vues d'ensemble** : les 4 photos de
  `21-vues-d-ensemble/` et les 2 planchettes de suivi de `19-magiciens/` ne montrent pas un pion
  isolé. Restent 121 pions sur 127.
- Le tirage ne tient aucun compte des règles : ni camp, ni scénario, ni empilement. Un pion
  peut sortir plusieurs fois, un mort-vivant peut se retrouver en pleine forêt elfique.
- Toutes les unités sont traitées de la même façon : terrestres, mouvement 5, sans égard aux
  valeurs portées sur le pion. Deux pions peuvent viser la même case, et le plateau ne se souvient
  de rien d'un rechargement à l'autre.

## Tests

Depuis la **racine du dépôt**, pour couvrir aussi le moteur :

```
python3 -m pytest
```

`tests/test_serveur.py` interroge Flask sans navigateur : contenu des champs cachés, cohérence des
coordonnées, terrains, fichiers servis, et les deux routes de déplacement — dont la vérification
qu'elles n'ajoutent rien aux règles du moteur. `tests/test_plateau.py` ouvre la page dans Chromium
avec Playwright : dix pions chargés et centrés à moins d'un pixel, inclinés de moins de 5°, carte
qui reste à l'échelle après redimensionnement, puis le cycle complet clic → fantômes →
déplacement.

Les tests de navigateur demandent Chromium :

```
python3 -m playwright install chromium
```
