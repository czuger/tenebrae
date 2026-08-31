# `application/` — la carte affichée dans le navigateur

Une application Flask qui sert `game_box/map.jpg`, y **met en place un scénario** — le n° 4,
« La guerre des nains », 21 nains face à 31 orques — et laisse le navigateur faire la géométrie.
Cliquer un pion montre en **fantômes** les cases où il peut aller ; cliquer un fantôme l'y
déplace. Le survoler ouvre sa **fiche** : sa photo agrandie et tout ce que son carton porte.

Les règles ne sont pas ici : les déplacements viennent de `moteur/`, l'application ne fait que les
servir. Le JavaScript ne décide jamais de la légalité d'un mouvement. **Chaque pion se déplace du
nombre de points imprimé sur son carton** — de 1 à 20 selon l'unité, lu dans
`game_box/pions/pions.json` par `moteur.pion` — et **s'arrête au contact des adversaires**, dont
les zones de contrôle couvrent les six cases qui les environnent.

Une seconde page, `/admin/map_fix`, sert à corriger la transcription de la carte : c'est le seul
endroit où l'application écrit dans `game_box/`, et seulement dans un fichier à elle. Le moteur
applique ces corrections à son démarrage — le plateau se joue donc sur la carte corrigée.

## Lancer

Depuis ce répertoire, avec le virtualenv pyenv `tenebrae` :

```
python3 app.py
```

puis <http://127.0.0.1:5000/> pour le plateau, <http://127.0.0.1:5000/admin/map_fix> pour la
correction de la carte. Chaque rechargement du plateau **remet le scénario en place** : les pions
déplacés reviennent à leur case de départ.

Dépendance : `Flask` (plus `pytest` et `pytest-playwright` pour les tests).

## Comment ça marche

Le serveur ne dessine rien : il passe deux JSON au gabarit, dans des champs cachés
(`#pions` et `#grille`), et `static/carte.js` s'en sert. Deux morceaux sont partagés avec la page
de correction : la géométrie — cubique ↔ pixels — dans `static/geometrie.js`, et le zoom —
molette, boutons, défilement — dans `static/zoom.js` et `static/zoom.css`.

| Champ caché | Contenu |
| --- | --- |
| `#pions` | une entrée par unité du scénario : `{q, r, s}` sa case, `{cle, image, nom}` le pion posé, `{mouvement, camp}` ce dont le déplacement se sert, et les valeurs de son carton (voir « Survoler une unité ») |
| `#grille` | `origine`, `matrice` et `taille_pion` : le calage de la grille sur `map.jpg` |

## Le plateau du serveur

Les zones de contrôle demandent de savoir **qui occupe quelle case et dans quel camp** : le
serveur tient donc un `moteur.plateau.Plateau`, refait à chaque chargement de `/` et mis à jour
par `/deplacer`. Sans lui, les zones se calculeraient sur des positions périmées dès le premier
déplacement.

C'est le premier état de partie du dépôt, et il reste mince : les 52 unités du scénario posées,
pas de tour de jeu, pas de joueurs, rien qui survive au rechargement de la page. Deux onglets
ouverts sur `/` se partagent le même plateau — le dernier chargement gagne.

Le JavaScript convertit chaque hexagone en pixels avec la formule relevée dans
`game_box/carte.md` :

```
centre(q, r) = origine + matrice · (q, r)
```

Le pion est ensuite **centré** sur ce point (`translate(-50%, -50%)`) puis **incliné au hasard de
± 5°**, pour que le plateau n'ait pas l'air posé à la règle. Les positions sont exprimées en
pixels de `map.jpg` : la carte est portée à sa taille naturelle par `#plateau`, que le
JavaScript met ensuite à l'échelle.

## Approcher et reculer

La carte fait 6173 × 5102 px et s'ouvre **ajustée à la fenêtre** — un pion y fait une quinzaine
de pixels, on n'y lit rien. Le plateau se zoome donc comme la page de correction, et par le même
code (`static/zoom.js`) :

- la **molette** approche en gardant sous le curseur le point qu'il désignait ; les boutons `+`,
  `−` et « ajuster » de la barre d'outils font la même chose depuis le centre de la fenêtre — et
  c'est cette même barre qui porte la fiche du pion survolé (voir « Survoler une unité ») ;
- l'échelle va de 5 % à 100 % — au-delà du scan, il n'y a plus rien à voir ;
- **le zoom ne touche à rien d'autre.** Tout ce qui est posé sur la carte — pions, fantômes,
  surlignage — est exprimé en pixels de `map.jpg`, dans le repère de `#plateau` : le mettre à
  l'échelle emporte le tout, et le clic repasse par la même conversion. Il n'y a donc aucune
  position à recalculer, et viser un hexagone marche à toute échelle ;
- redimensionner la fenêtre **réajuste** la carte, tant qu'on n'a pas réglé l'échelle soi-même —
  sans quoi le zoom qu'on vient de choisir serait défait.

## Cliquer, montrer, déplacer

Un clic est d'abord ramené en coordonnées cubiques : la même matrice, **inversée**, puis un
arrondi cubique donne l'hexagone visé. C'est la seule chose que le navigateur calcule — la suite
est un aller-retour avec le serveur.

| Route | Réponse |
| --- | --- |
| `GET /deplacements?q=&r=&s=&pion=` | `{"depart": {…}, "pion": "cle", "camp": "alliance", "mouvement": 8, "hexagones": [{q, r, s, terrain}, …]}` |
| `POST /deplacer` — corps `{"depart": {…}, "arrivee": {…}, "pion": "cle"}` | `{"autorise": bool, "depart": {…}, "arrivee": {…}, "pion": "cle", "camp": "alliance", "mouvement": 8}` |

Coordonnées illisibles ou de somme non nulle → 400 ; hexagone hors carte → 404 ; pion inconnu du
catalogue → 400.

**C'est le plateau du serveur qui dit quel pion se tient sur la case de départ**, dans quel camp,
et quels adversaires lui opposent leurs zones de contrôle. Le paramètre `pion` — la clé de
`pions.json`, `reissland-02-8-cavaleries` — ne sert qu'à interroger une **case vide** : le pion
posé, lui, l'emporte toujours. Le navigateur ne dit donc jamais de combien de points il dispose,
et un `mouvement` glissé dans la requête n'a aucun effet. Sans `pion` sur une case vide, le forfait
de 5 points s'applique et la carte est réputée sans adversaire.

1. clic sur un pion → `/deplacements` → un fantôme par hexagone rendu : la même image, à 50 %
   d'opacité, sous les pions posés, centrée et inclinée comme eux. Une cavalerie de Reissland
   (8 points) en couvre plus de deux cents en plaine, le bélier d'Yzent (2 points) une vingtaine,
   un marqueur aucun — et un adversaire proche les fait s'arrêter à son contact ;
2. clic sur un fantôme → `/deplacer` → le pion se repose sur la case, de travers autrement, et
   **change de case sur le plateau du serveur** : les zones du coup d'après en tiennent compte ;
3. clic ailleurs, ou de nouveau sur le pion sélectionné → les fantômes s'effacent.

`/deplacer` recalcule la portée côté serveur au lieu de croire le navigateur.

## Survoler une unité

La carte s'ouvre ajustée à la fenêtre, où un pion fait une quinzaine de pixels : on n'y lit ni son
dessin ni ses chiffres. **Survoler une unité remplit sa fiche**, qui n'est pas un encadré posé sur
la carte mais **le prolongement de la barre des boutons de zoom** : un trait la sépare d'eux,
comme le compteur de la page de correction. La barre s'allonge, elle ne se déplace pas.

- **Le survol n'interroge jamais le serveur.** Tout ce que la fiche montre est déjà dans le champ
  caché `#pions`, valeurs du carton comprises ; c'est le même parti que la page de correction, où
  les 2280 terrains partent d'un coup.
- **La barre garde la taille qu'elle a sans la fiche.** C'est ce qui règle le corps du texte
  (0.75 rem) et la vignette (20 px) : la hauteur reste celle des boutons de zoom, qu'on survole
  une unité ou non. La fiche **ne passe donc jamais à la ligne** — sur une fenêtre étroite, elle
  se laisse rogner par la droite, et les remarques cèdent la place les premières, étant ce qu'elle
  a de moins utile au jeu. En dessous d'un millier de pixels, les dernières valeurs peuvent y
  passer aussi.
- **Tout tient sur une ligne** : le carton en vignette, le nom, le camp et la case, le symbole,
  les six valeurs chiffrées, les remarques.
- **La vignette sert à reconnaître le pion, pas à le lire** : ses chiffres sont écrits en toutes
  lettres à côté.
- **Ce que le carton ne porte pas est rendu par un tiret**, jamais par un zéro : un pion sans tir
  ne tire pas, il ne tire pas « à 0 ». Les remarques, elles, ne sont pas une valeur du carton mais
  ce que la photo laisse en suspens — un nom illisible, un cadrage incomplet : **leur mention ne
  paraît que s'il y a quelque chose à dire**.
- « Mouvement » est le budget dont le moteur se sert — le mouvement au sol, à défaut celui de vol,
  0 pour un marqueur (voir `moteur/README.md`) —, et non la valeur brute que `pions.json` laisse
  parfois vide.
- **La barre est hors de `#plateau`** : le zoom ne l'atteint pas, la fiche garde sa taille à toute
  échelle. Et elle est **en place fixe** : d'un pion à l'autre, rien ne bouge.
- **La fiche laisse passer les clics** (`pointer-events: none`) là où les boutons, eux, les
  prennent : sans quoi elle rendrait injouable la bande de carte qu'elle recouvre.
- **Les fantômes n'ont pas de fiche** : ils répètent l'unité déjà sélectionnée, et couvrir la
  carte de survols qui disent tous la même chose n'apprendrait rien.

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

- **Zoom** : le même que celui du plateau (voir plus haut) — la carte s'ouvre ajustée à la
  fenêtre, où un hexagone fait 25 px : on ne juge pas un bois à cette taille.
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

## La mise en place

Le serveur ne tire plus rien au hasard : il lit la mise en place du scénario `NUMERO_DU_SCENARIO`
(4) dans `scenarios/` par `moteur.scenario`, une fois au démarrage, et la repose à chaque
chargement de `/`.

- **Le placement vient du fichier, pas du serveur.** `scenarios/scenario-04-la-guerre-des-nains.json`
  donne « case → clé de pion » ; l'application n'y ajoute que ce qu'il faut pour l'affichage —
  l'image, le nom lisible, le mouvement et le camp, tous repris au catalogue de
  `game_box/pions/`. Le détail du déploiement et ses réserves sont dans `scenarios/README.md`.
- **La position est reproductible.** Recharger la page remet les 52 unités à leur case : c'est ce
  qui permet d'éprouver un déplacement deux fois de suite et d'obtenir le même résultat. En
  contrepartie, il n'y a aucun moyen de reprendre une partie en cours — le rechargement l'efface.
- **Le mouvement est celui du carton** : chaque pion emporte ses points, lus sur la photo et
  rangés dans `game_box/pions/pions.json`. Le reste des valeurs — force, tir, portée — ne joue
  encore aucun rôle dans les règles, mais la fiche du survol le montre.
- **Le camp vient de la faction** (voir `moteur/README.md`) : il décide qui gêne qui. Ici, les
  nains sont l'alliance et les orques les ténèbres, et les deux masses se font face à 3 cases.
- Les vues d'ensemble ne sont toujours pas servies : les 4 photos de `21-vues-d-ensemble/` et les
  2 planchettes de suivi de `19-magiciens/` ne montrent pas un pion isolé, et `/pions/…` les
  refuse. Le scénario ne les nomme pas non plus.
- Une case n'accueille qu'un pion, et le plateau ne se souvient de rien d'un rechargement à
  l'autre.

## Tests

Depuis la **racine du dépôt**, pour couvrir aussi le moteur :

```
python3 -m pytest
```

`tests/test_map_fix.py` et `tests/test_map_fix_navigateur.py` couvrent la page de correction —
le second dans Chromium : survol, dialogue, enregistrement, boutons de zoom. Tous deux
détournent le chemin du fichier de corrections vers un répertoire temporaire : **aucun test
n'écrit dans `game_box/`**.

`tests/test_serveur.py` interroge Flask sans navigateur : contenu des champs cachés — dont les
valeurs du carton que la fiche du survol y lit —, cohérence des coordonnées, fichiers servis, la
mise en place servie case par case — elle doit être celle du
scénario, et la même d'un chargement à l'autre —, et les deux routes de déplacement, dont la
vérification qu'elles n'ajoutent rien aux règles du moteur, que la portée suit le carton du pion
posé, qu'un adversaire au contact la réduit, qu'un ami ne la réduit pas, et qu'un déplacement
accepté change vraiment le plateau du serveur. Chaque test y part d'une **carte déserte** — le
plateau survit d'une requête à l'autre, et les 52 unités du scénario se retrouveraient sinon sous
les pieds du test suivant. Ce que contient le scénario lui-même est éprouvé à part, dans
`moteur/tests/test_scenario.py`.

`tests/test_plateau.py` ouvre la page dans Chromium avec Playwright : les 52 pions chargés et
centrés à moins d'un pixel, inclinés de moins de 5°, carte qui reste à l'échelle après
redimensionnement, le zoom — boutons, molette qui garde son point sous le pointeur, pions qui
restent sur leur hexagone une fois approchés, échelle réglée à la main qu'un redimensionnement ne
défait pas —, la fiche du survol — les valeurs du carton des cinquante-deux unités comparées au
catalogue du moteur, la mention de remarques qui ne paraît qu'à bon escient, la photo, la case
d'un pion qu'on vient de déplacer, la fiche qui se referme en quittant le pion, qui ne paraît pas
sur un fantôme, qui tient dans la barre d'outils sans la faire grandir — à la fenêtre étroite
comme à la large —, qui n'en bouge pas d'un pion à l'autre et qui ne capte pas les clics —, puis le cycle complet clic → fantômes → déplacement, à
l'ajustement comme une fois approché. Les fantômes attendus sont ceux que le plateau du serveur
calcule — il tourne dans le même processus, on le lit directement — et un test pose un adversaire
au contact pour vérifier que le clic en montre alors moins.

Les tests de navigateur demandent Chromium :

```
python3 -m playwright install chromium
```
