# `application/` — la carte affichée dans le navigateur

Une application Flask qui sert `game_box/map.jpg`, tire **dix hexagones au hasard**, pose un pion
sur chacun, et laisse le navigateur faire la géométrie. Cliquer un pion montre en **fantômes** les
cases où il peut aller ; cliquer un fantôme l'y déplace.

Les règles ne sont pas ici : les déplacements viennent de `moteur/`, l'application ne fait que les
servir. Le JavaScript ne décide jamais de la légalité d'un mouvement.

Une seconde page, `/admin/map_fix`, sert à corriger la transcription de la carte : c'est le seul
endroit où l'application écrit dans `game_box/`, et seulement dans un fichier à elle. Le moteur
applique ces corrections à son démarrage — le plateau se joue donc sur la carte corrigée.

## Lancer

Depuis ce répertoire, avec le virtualenv pyenv `tenebrae` :

```
python3 app.py
```

puis <http://127.0.0.1:5000/> pour le plateau, <http://127.0.0.1:5000/admin/map_fix> pour la
correction de la carte. Chaque rechargement du plateau rejoue un tirage.

Dépendance : `Flask` (plus `pytest` et `pytest-playwright` pour les tests).

## Comment ça marche

Le serveur ne dessine rien : il passe deux JSON au gabarit, dans des champs cachés
(`#pions` et `#grille`), et `static/carte.js` s'en sert. La géométrie elle-même — cubique ↔
pixels — vit dans `static/geometrie.js`, partagé avec la page de correction.

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

## Corriger la carte — `/admin/map_fix`

L'implémentation des déplacements a montré que la carte transcrite comporte des erreurs, et elles
ne se voient qu'à l'œil. Cette page affiche `map.jpg`, dit le terrain sous le pointeur, et le
corrige d'un clic.

**Toute la carte part au navigateur d'un coup**, dans les champs cachés — 2280 hexagones, une
cinquantaine de kilo-octets. Le survol ne demande donc rien au serveur : il lit dans l'objet reçu.
Seul le choix d'un terrain fait un aller-retour.

| Champ caché | Contenu |
| --- | --- |
| `#hexagones` | `« q,r,s » → terrain` pour les 2280 hexagones, le terrain principal seul |
| `#corrections` | les corrections déjà relevées, lues dans `map_fix.json` |
| `#appliquees` | celles que le moteur a chargées à son démarrage — l'écart appelle un redémarrage |
| `#terrains` | les 16 terrains, dans l'ordre de priorité de `game_box/carte.md` |
| `#grille` | le même calage que le plateau, sans `taille_pion` |

- **Zoom** : la carte s'ouvre ajustée à la fenêtre — un hexagone y fait 25 px, on ne juge pas un
  bois à cette taille. La molette approche en gardant sous le curseur le point qu'il désignait ;
  les boutons `+`, `−` et « ajuster » font la même chose depuis le centre.
- **Survol** : l'hexagone visé est surligné et un encadré donne `q,r,s — terrain`, suivi de
  `→ terrain corrigé` si la case a déjà été reprise.
- **Clic** : une boîte de dialogue donne le terrain de la carte et seize boutons. Choisir celui que
  la carte porte déjà **retire** la correction — c'est le retour en arrière.
- Les cases corrigées restent marquées en rouge sur la carte, et la barre d'outils les compte.

| Route | Réponse |
| --- | --- |
| `GET /admin/map_fix` | la page |
| `POST /admin/map_fix` — corps `{q, r, s, terrain}` | `{"cle", "terrain", "origine", "corrige": bool}` |

Terrain inconnu ou coordonnées illisibles → 400 ; hexagone hors carte → 404.

Chaque correction est écrite aussitôt dans **`game_box/map_fix.json`**, qui ne contient que les
cases reprises :

```json
{
"29,5,-34": "colline"
}
```

`carte.json` et `carte_details.json` **ne sont jamais touchés** : ils sont produits par
`game_box/extraction_carte.py` et doivent le rester (voir `game_box/carte.md`).

**Le moteur lit ce fichier et le pose par-dessus la transcription**, une fois, à son démarrage
(voir `moteur/README.md`) : le plateau de `/` et les déplacements se calculent sur la carte
corrigée. Comme le recouvrement n'a lieu qu'au démarrage, la barre d'outils annonce
« redémarrer le serveur pour jouer dessus » dès que les corrections relevées s'écartent de celles
que le moteur a chargées.

Cette page, elle, travaille toujours sur la carte **transcrite** : `#hexagones` porte ce que le
scan a donné, les corrections viennent à part, et le terrain « d'origine » du dialogue reste celui
du scan. Sans quoi, après un redémarrage, « Rétablir » proposerait de rétablir la correction
elle-même.

Pas de gestion d'administration : la route est ouverte.

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

`tests/test_map_fix.py` et `tests/test_map_fix_navigateur.py` couvrent la page de correction —
le second dans Chromium : survol, dialogue, enregistrement, zoom. Tous deux détournent le chemin
du fichier de corrections vers un répertoire temporaire : **aucun test n'écrit dans `game_box/`**.

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
