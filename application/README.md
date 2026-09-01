# `application/` — la carte affichée dans le navigateur

Une application Flask qui sert `game_box/map.jpg`, y **met en place un scénario** — le n° 4,
« La guerre des nains », 21 nains face à 31 orques — et laisse le navigateur faire la géométrie.
Cliquer un pion montre en **fantômes** les cases où il peut aller ; cliquer un fantôme l'y
déplace. Le survoler ouvre sa **fiche** : sa photo agrandie et tout ce que son carton porte.

Le jeu suit un **tour** : mouvement puis combat, pour les Nains puis pour les Orques, en boucle
(la magie est sautée). Le bouton « Phase suivante » avance ; le libellé de la barre d'outils dit
où l'on en est. En **phase de combat**, un clic sur une unité adverse la prend pour cible (rouge),
un clic sur ses propres unités à portée les désigne comme attaquants (or), et « Attaquer » résout
d'après le Tableau I du fascicule. **Une unité ne combat qu'une fois par phase** : celles qui ont
donné sont grisées et refusent le clic jusqu'à la phase suivante.

Les règles ne sont pas ici : les déplacements viennent de `moteur/`, l'application ne fait que les
servir. Le JavaScript ne décide jamais de la légalité d'un mouvement. **Chaque pion se déplace du
nombre de points imprimé sur son carton** — de 1 à 20 selon l'unité, lu dans
`game_box/pions/pions.json` par `moteur.pion` — et **s'arrête au contact des adversaires**, dont
les zones de contrôle couvrent les six cases qui les environnent.

La partie se joue **à deux, un joueur par camp**, chacun identifié par son compte Discord : le
serveur refuse un coup joué par celui dont ce n'est pas le tour, et chaque navigateur voit avancer
la partie de l'autre sans rien recharger — par un **flux d'événements** que le serveur pousse quand
la partie change, et non plus en redemandant toutes les trois secondes. La carte, elle, reste visible sans compte (voir « Deux
joueurs, deux camps » et « Se connecter par Discord »).

Une seconde page, `/admin/map_fix`, sert à corriger la transcription de la carte : c'est le seul
endroit où l'application écrit dans `game_box/`, et seulement dans un fichier à elle. Le moteur
applique ces corrections à son démarrage — le plateau se joue donc sur la carte corrigée. Elle est
réservée aux comptes déclarés dans `ADMIN_DISCORD_IDS`.

## Lancer

Depuis ce répertoire, avec le virtualenv pyenv `tenebrae` :

```
python3 app.py
```

puis <http://127.0.0.1:5000/> pour le plateau, <http://127.0.0.1:5000/admin/map_fix> pour la
correction de la carte. Le plateau **reprend la partie là où on l'a laissée** (voir « Persistance
de la partie ») ; `POST /partie/nouvelle` la recommence.

Il faut un `.env` à la racine du dépôt (voir `.env.example`) : sans `SECRET_KEY`, l'application
refuse de démarrer, et sans les identifiants Discord personne ne pourra se connecter.

Dépendances : `Flask`, `mongoengine` et `python-dotenv` (plus `pytest`, `pytest-playwright` et
`mongomock` pour les tests). **L'authentification n'en ajoute aucune** : la session tient sur
`flask.session`, et les deux appels à Discord sur `urllib` de la bibliothèque standard.

## Persistance de la partie

La partie est enregistrée dans **MongoDB** à chaque coup joué — déplacement, combat, changement de
phase —, et `GET /` la reprend. Seul l'état de jeu y va : les positions, l'angle sous lequel
chaque carton est couché, la phase courante, ce que la phase de combat a déjà consommé, et **qui
tient quel camp** — savoir qui joue l'Alliance fait partie de la partie, et un redémarrage ne doit
pas vider la table. À côté d'elle, une seconde
collection retient les **joueurs** connus (`joueurs`). La carte, le catalogue des pions et les
scénarios restent des fichiers de `game_box/` et `scenarios/`, qui sont la source de vérité du
dépôt.

Les places voyagent dans le dict d'état, avec le reste, et non dans des méthodes de dépôt à part :
`_remplir()` réécrit toute la partie à chaque coup, et des places tenues à côté seraient effacées
à chaque sauvegarde. Une partie enregistrée avant les joueurs n'a pas de champ `places` : elle
reste reprenable, la table est simplement vide. Il en va de même du champ `inclinaisons`, venu
plus tard : les pions d'une vieille sauvegarde se recouchent une fois à la reprise, et le premier
coup joué fige leurs angles.

**Lancer un MongoDB local**, par Docker :

```
docker run -d --name tenebrae-mongo -p 27017:27017 mongo:7
```

ou par Homebrew (`brew install mongodb-community && brew services start mongodb-community`).

**Configurer**, depuis la racine du dépôt :

```
cp .env.example .env
```

`.env` n'est pas versionné : c'est le seul endroit où vivent les informations de connexion et les
secrets, et `application/config.py` les y lit une fois au démarrage. `MONGODB_URI` et
`PERSISTANCE` pour la base ; `SECRET_KEY`, les trois `DISCORD_*`, `ADMIN_DISCORD_IDS` et
`COOKIE_SECURISE` pour les joueurs (voir « Se connecter par Discord »).

**Jouer sans MongoDB** : `PERSISTANCE=aucune` dans `.env`. Le serveur branche alors un dépôt qui ne
retient rien, et l'application se comporte comme avant la persistance — chaque chargement de `/`
repose la mise en place du scénario. C'est aussi ce que fait la configuration de test, ce qui
permet à toute la suite de tourner sans base.

Le dépôt de **joueurs**, lui, retient alors **en mémoire** au lieu de ne rien retenir. La nuance
compte : l'état de jeu a déjà un domicile dans les module-globaux d'`app.py`, un joueur n'en a
aucun, et un dépôt qui ne garderait rien n'appauvrirait pas le service — il l'interdirait, personne
ne pouvant plus ouvrir de session, donc prendre place, donc jouer. La promesse de
`PERSISTANCE=aucune` est tenue de la même façon : rien ne survit au serveur.

| Route | Effet |
| --- | --- |
| `GET /` | reprend la dernière partie ; à défaut — base vide, ou sauvegarde d'un autre scénario — repose le scénario et en ouvre une |
| `POST /partie/nouvelle` | repose le scénario et ouvre une nouvelle partie, **sans lever la table** ; avec le corps `{"contre_ia": true}`, confie le camp adverse à l'IA (voir « Jouer contre l'IA ») ; rend `{"pions": […], "phase": {…}}` et la table |

Les parties précédentes restent en base : `POST /partie/nouvelle` n'efface rien, il ouvre un
document de plus, et c'est le plus récent que `/` reprend.

**Les routes ne connaissent pas MongoDB.** Elles passent par un *dépôt* (`moteur/depots/`) que la
factory `create_app` accroche à l'application, et n'échangent avec lui que des dicts d'état ; le
document et les requêtes sont dans `moteur/depots/partie.py` et `moteur/models/partie.py`, nulle
part ailleurs. La sérialisation, elle, est dans le moteur (`Plateau.en_dict`/`restaurer`,
`Tour.restaurer`, `SuiviDeCombat.en_dict`/`restaurer`) et ne dépend d'aucune base.

**La partie n'est pas un modèle de l'application** : c'est du jeu, et le jeu est dans le moteur.
L'application n'en garde que l'orchestration — quand charger, quand sauvegarder, et ce qu'on en
montre au navigateur. Voir « Les modèles » plus bas, et la section « Architecture » du `CLAUDE.md`
de la racine.

Un mot sur l'extension : le todo demandait Flask-MongoEngine, dont la dernière version (1.0.0,
2022) importe `flask.json.JSONEncoder`, retiré de Flask depuis la 2.3 — elle ne s'importe pas sous
le Flask 3 de ce dépôt. `application/extensions.py` en reprend l'interface (`db = MongoEngine()`,
`db.init_app(app)`, `MONGODB_SETTINGS` dans la config) au-dessus de `mongoengine` seul. Si
l'extension redevient installable, ce fichier est le seul à changer.

## Les modèles

L'application ne modélise **qu'une seule chose** : la connexion. Tout le reste est du jeu, et vit
dans `moteur/models/` — un fichier par modèle, de part et d'autre.

| Classe | Module | Collection Mongo | Fichier |
| --- | --- | --- | --- |
| `Connexion` | application | — (le cookie signé de Flask) | `models/connexion.py` |
| `Partie` | moteur | `parties` | `moteur/models/partie.py` |
| `Joueur` | moteur | `joueurs` | `moteur/models/joueur.py` |
| `Places` | moteur | — (champ `places` de `Partie`) | `moteur/models/places.py` |

`Connexion` est le lien entre une session Flask et le joueur du moteur. Elle ne double rien de ce
que `Joueur` sait : elle ne retient qu'un **identifiant Discord**, celui que la session porte, et
va relire le joueur au dépôt chaque fois qu'on le lui demande — c'est ce qui fait qu'un changement
de pseudo se voit dès la requête suivante. Elle n'est pas persistée : le cookie signé de Flask
*est* son stockage, et il vit chez le joueur.

```python
connexion = la_connexion()          # Connexion(session, le_depot_de_joueurs())
connexion.poser_un_etat_oauth()     # avant de partir chez Discord
connexion.reprendre_l_etat_oauth()  # au retour : l'état est retiré de la session
connexion.ouvrir(identite)          # enregistre le joueur du moteur, ouvre la session
connexion.joueur()                  # le dict du joueur, relu au dépôt — ou None
connexion.fermer()                  # déconnexion
```

Les routes ne touchent donc plus à `session` : elles demandent `la_connexion()`, et le savoir de
ce que la session porte — quelles clés, dans quel ordre, avec quelle précaution — tient en un seul
fichier. La dépendance ne va que dans un sens : `models/connexion.py` connaît le moteur, le moteur
ne connaît rien de Flask.

## Comment ça marche

Le serveur ne dessine rien : il passe deux JSON au gabarit, dans des champs cachés
(`#pions` et `#grille`), et `static/carte.js` s'en sert. Deux morceaux sont partagés avec la page
de correction : la géométrie — cubique ↔ pixels — dans `static/geometrie.js`, et le zoom —
molette, boutons, défilement — dans `static/zoom.js` et `static/zoom.css`.

| Champ caché | Contenu |
| --- | --- |
| `#pions` | une entrée par unité du scénario : `{q, r, s}` sa case, `inclinaison` l'angle sous lequel elle est couchée, `{cle, image, nom}` le pion posé, `{mouvement, camp}` ce dont le déplacement se sert, et les valeurs de son carton (voir « Survoler une unité ») |
| `#grille` | `origine`, `matrice` et `taille_pion` : le calage de la grille sur `map.jpg` |
| `#phase` | la phase courante : `{camp, type, armee, libelle, numero, indisponibles}` (voir « Phases et combat ») |
| `#table` | qui regarde et qui tient quel camp : `{connecte, pseudo, avatar, administrateur, camps, armees, places}` (voir « Deux joueurs, deux camps ») |
| `#version` | le numéro de version de la partie, à quoi le navigateur voit que l'adversaire a joué |

## Le plateau du serveur

Les zones de contrôle demandent de savoir **qui occupe quelle case et dans quel camp** : le
serveur tient donc un `moteur.plateau.Plateau`, refait à chaque chargement de `/` et mis à jour
par `/deplacer`. Sans lui, les zones se calculeraient sur des positions périmées dès le premier
déplacement.

À côté du plateau, le serveur tient un `moteur.phase.Tour` — le module-global `TOUR` — : quel
camp joue, et à quoi. Plateau et tour sont **repris de la sauvegarde** à chaque chargement de `/`,
ou refaits depuis le scénario s'il n'y en a pas (voir « Persistance de la partie »). Il n'y a
qu'**une partie courante par processus** : deux onglets ouverts sur `/` se partagent le même
plateau et le même tour — ce qui tombe bien, puisque les deux joueurs jouent la même partie.

À côté d'eux, le module-global `PLACES` (`moteur/models/places.py`) retient qui tient quel camp.
Contrairement au plateau et au tour, il n'est **pas** refait à chaque chargement de `/` :
recommencer une partie ne renvoie personne de sa place.

Le JavaScript convertit chaque hexagone en pixels avec la formule relevée dans
`game_box/carte.md` :

```
centre(q, r) = origine + matrice · (q, r)
```

Le pion est ensuite **centré** sur ce point (`translate(-50%, -50%)`) puis **incliné de quelques
degrés**, pour que le plateau n'ait pas l'air posé à la règle. Cet angle n'est **pas** tiré par la
page : il vient du serveur, avec le pion, parce qu'il est de l'état de partie — le plateau du
moteur le tire à la pose et le garde (`moteur/plateau.py`), la sauvegarde l'emporte, et il ne
change que lorsque le pion est déplacé. Une page qui le retirait à chaque fois faisait pivoter les
cinquante-deux cartons à chaque scène reposée. La page n'en tire un que pour les
**fantômes**, qui ne sont posés nulle part. Les positions sont exprimées en pixels de `map.jpg` :
la carte est portée à sa taille naturelle par `#plateau`, que le JavaScript met ensuite à
l'échelle.

## Approcher et reculer

La carte fait 6173 × 5102 px et s'ouvre **ajustée à la fenêtre** — un pion y fait une quinzaine
de pixels, on n'y lit rien. Le plateau se zoome donc comme la page de correction, et par le même
code (`static/zoom.js`) :

- la **molette** approche en gardant sous le curseur le point qu'il désignait ; les boutons `+`,
  `−` et « ajuster » de la barre d'outils font la même chose depuis le centre de la fenêtre — la
  fiche du pion survolé se pose sous cette barre (voir « Survoler une unité ») ;
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
| `POST /deplacer` — corps `{"depart": {…}, "arrivee": {…}, "pion": "cle"}` | `{"autorise": bool, "depart": {…}, "arrivee": {…}, "inclinaison": -3.52, "pion": "cle", "camp": "alliance", "mouvement": 8}` |

Coordonnées illisibles ou de somme non nulle → 400 ; hexagone hors carte → 404 ; pion inconnu du
catalogue → 400.

`/deplacements` reste en lecture seule et n'est jamais bloqué. `/deplacer`, lui, **refuse
(`autorise: false`, sans toucher au plateau) tout déplacement hors de la phase de mouvement du
camp du pion** : c'est le seul endroit où le tour pèse sur le mouvement.

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
2. clic sur un fantôme → `/deplacer` → le pion se repose sur la case, de travers autrement — c'est
   le serveur qui a tiré ce nouvel angle et qui le rend, dans `inclinaison` —, et il **change de
   case sur le plateau du serveur** : les zones du coup d'après en tiennent compte ;
3. clic ailleurs, ou de nouveau sur le pion sélectionné → les fantômes s'effacent.

`/deplacer` recalcule la portée côté serveur au lieu de croire le navigateur.

En **phase de combat**, le clic ne sert plus à déplacer : il désigne une cible puis des attaquants
(voir « Phases et combat »).

## Phases et combat

Le serveur tient la phase courante dans `TOUR` (`moteur.phase.Tour`) et la passe au gabarit dans
`#phase`. Le fascicule enchaîne, pour chaque camp, **mouvement → magie → combat** ; la magie n'est
pas implémentée, `Tour.suivante()` la saute — elle n'est jamais courante.

| Route | Réponse |
| --- | --- |
| `GET /phase` | `{camp, type, armee, libelle, numero, indisponibles}` — pour rafraîchir le navigateur |
| `POST /phase/suivante` | la phase suivante, même forme ; journalisée |
| `GET /combat/portee?cq=&cr=&cs=&aq=&ar=&as=` | `{"a_portee": bool, "disponible": bool, "message": str\|null}` ; un refus part au journal |
| `GET /combat/cible?cq=&cr=&cs=` | `{"disponible": bool, "message": str\|null}` ; un refus part au journal |
| `POST /combat` — corps `{"cible": {q,r,s}, "attaquants": [{q,r,s}, …]}` | voir plus bas |

`GET /` porte `#phase` ; le JavaScript en tire le libellé de la barre d'outils et **ce qu'un clic
fait** : en phase de mouvement, seul le camp actif montre ses fantômes ; en phase de combat,

1. clic sur une unité **adverse** → le serveur (`/combat/cible`) dit si elle peut encore être
   prise ; si oui, elle devient la cible, surlignée en **rouge** ;
2. clic sur une de ses **propres** unités → le serveur (`/combat/portee`) dit si elle est à portée
   (distance ≤ 1, ou ≤ sa portée de tir) et si elle n'a pas déjà attaqué ; si oui, elle rejoint les
   attaquants, surlignée en **or** ; si non, rien ne bouge et le refus est au journal ;
3. « Attaquer » (visible dès qu'il y a une cible et un attaquant) → `POST /combat` ;
4. « Annuler », ou un nouveau clic sur la cible → la sélection se vide et les surlignages tombent.

`POST /combat` revalide tout côté serveur — phase, camp de la cible, portée de chaque attaquant,
et le registre de la phase —, lance le dé (`app.lancer_le_de`, isolé pour les tests), résout via
`moteur.combat.livrer_combat` et applique le résultat :

```json
{"resolu": true, "resultat": "DE", "message": "Combat résolu : Défenseur Éliminé",
 "elimines": [{"q": 1, "r": 26, "s": -27, "terrain": "plaine"}], "jet": 4, "de": 4, "rapport": [3, 1],
 "indisponibles": {"attaquants": [{"q": 0, "r": 26, "s": -26, "terrain": "plaine"}], "cibles": []}}
```

Seules les issues `AE`, `DE` et `EX` retirent des pions ; les reculs (`AR`, `DR`) ne changent rien.
`{"resolu": false, "message": …}` quand ce n'est pas la phase de combat, que la cible n'est pas
adverse, qu'elle a déjà été attaquée, ou qu'aucun attaquant n'est valide.

### Un seul combat par unité et par phase

Le fascicule limite chaque unité à une attaque par phase, et chaque cible à une attaque par phase
même par des attaquants différents. Le compte est tenu **côté serveur** par le module-global
`SUIVI` (`moteur.combat.SuiviDeCombat`), à côté de `PLATEAU` et de `TOUR` :

- il est **vidé à chaque changement de phase** (`POST /phase/suivante`) — donc entre la phase de
  combat des Nains et celle des Orques, et au tour suivant. `GET /` le reprend de la sauvegarde,
  ou le vide s'il repose le scénario ;
- un combat **livré** y inscrit tous ses attaquants et sa cible, **quelle que soit son issue** : un
  recul, que le moteur laisse sans effet, a tout de même engagé ses unités ;
- un combat **refusé** (aucun attaquant valide) n'y inscrit rien.

`indisponibles` — porté par `#phase`, `GET`/`POST /phase…` et la réponse de `POST /combat` — donne
les **cases** de ce registre qui portent encore un pion, pour que la page grise ces unités
(`.pion.indisponible`). Le registre désigne les unités par leur case et non par leur carton : voir
`moteur/README.md` § « Un seul combat par unité et par phase » pour ce que cela suppose.

**Le journal est un simple fichier local**, `application/journal_de_combat.log` (une ligne par
événement : changement de phase, unité hors de portée, résultat de combat en français). C'est le
deuxième endroit où l'application écrit sur le disque, après `/admin/map_fix` ; le fichier est
ignoré par git.

## Survoler une unité

La carte s'ouvre ajustée à la fenêtre, où un pion fait une quinzaine de pixels : on n'y lit ni son
dessin ni ses chiffres. **Survoler une unité remplit sa fiche**, un encadré qui n'est pas posé
n'importe où sur la carte mais **sous la barre des boutons de zoom**, dans le même panneau
(`#panneau`) et aligné sur son bord gauche. La fiche paraît et disparaît sous la barre ; ni l'une
ni l'autre ne se déplace.

- **Le survol n'interroge jamais le serveur.** Tout ce que la fiche montre est déjà dans le champ
  caché `#pions`, valeurs du carton comprises ; c'est le même parti que la page de correction, où
  les 2280 terrains partent d'un coup.
- **La barre garde la taille de référence que `carte.css` documente**, et que la fiche ne peut plus
  toucher. La fiche a d'abord été *dans* la barre, à la suite des boutons ; il lui fallait pour
  cela un corps de 0.1875 rem — trois pixels — pour ne pas l'allonger, ce qui la rendait illisible.
  Descendue d'un cran, elle **reprend le corps de la barre** (0.85 rem) et une vignette de 48 px.
- **Le rapport de taille de la barre ne se modifie pas.** `zoom.css` le fixe — corps 0.85 rem,
  garniture 0.4/0.7 rem, boutons 0.15/0.6 rem, ancrage à 0.6 rem du coin —, `carte.css` le
  documente en tête de sa section et se garde de le redéfinir. `#panneau` reprend l'ancrage à
  l'identique et la barre y passe simplement en `position: static`.
- **Un élément par ligne** : le nom, puis le camp et la case, puis le symbole, puis les six
  valeurs chiffrées, puis les remarques — empilés à côté de la vignette, qui reste à gauche. Les
  six valeurs tiennent sur une ligne et **passent à la ligne sur une fenêtre étroite** : la fiche
  grandit alors vers le bas, ce qu'elle ne pouvait pas se permettre dans la barre.
- **La vignette sert à reconnaître le pion, pas à le lire** : ses chiffres sont écrits en toutes
  lettres à côté.
- **Ce que le carton ne porte pas est rendu par un tiret**, jamais par un zéro : un pion sans tir
  ne tire pas, il ne tire pas « à 0 ». Les remarques, elles, ne sont pas une valeur du carton mais
  ce que la photo laisse en suspens — un nom illisible, un cadrage incomplet : **leur mention ne
  paraît que s'il y a quelque chose à dire**.
- « Mouvement » est le budget dont le moteur se sert — le mouvement au sol, à défaut celui de vol,
  0 pour un marqueur (voir `moteur/README.md`) —, et non la valeur brute que `pions.json` laisse
  parfois vide.
- **Le panneau est hors de `#plateau`** : le zoom ne l'atteint pas, la fiche garde sa taille à
  toute échelle. Et il est **en place fixe**, hors du flux : d'un pion à l'autre rien ne bouge, et
  la carte occupe la fenêtre comme s'il n'existait pas.
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

**La route est réservée** aux comptes Discord énumérés dans `ADMIN_DISCORD_IDS` (voir
`.env.example`). Une liste vide n'admet personne, et le refus le dit : une variable de sécurité
dont l'absence ouvrirait tout serait un piège. Un visiteur sans compte reçoit 401, un joueur
ordinaire 403.

## Deux joueurs, deux camps

Une partie réunit **deux comptes Discord, un par camp** : l'un tient les Nains (l'Alliance),
l'autre les Orques (les Ténèbres). Le serveur refuse un coup joué par celui dont ce n'est pas le
tour — c'est le décorateur `camp_actif_requis` —, et le navigateur éteint d'avance les boutons
qu'un refus attendrait.

La table est un registre à part, `moteur/models/places.py` — c'est du jeu, pas du web —, tenu à
côté du plateau et du tour dans le module-global `PLACES`. Il ne connaît que des identifiants
Discord, et ne défend qu'un invariant :
**un camp a au plus un occupant**, et une place ne se prend pas à qui l'occupe. La règle qui veut
qu'un joueur ne tienne qu'un camp est ailleurs, dans la route `POST /partie/place` — cette
séparation est ce qui permet à la suite de tests d'asseoir un seul joueur des deux côtés pour
jouer une partie à elle seule.

| Route | Méthode | Ce qu'elle fait | Qui peut |
| --- | --- | --- | --- |
| `/partie/place` | POST | s'asseoir au camp du corps `{camp}` | tout compte connecté |
| `/partie/place/quitter` | POST | rendre sa place ; la partie ne bouge pas | tout compte connecté |
| `/partie/etat` | GET | où en est la partie — le repli du flux, voir plus bas | tout le monde |
| `/flux` | GET | le flux d'événements : la partie poussée quand elle change | tout le monde |

Ce qui est **public** : `/`, la carte, les images de pions, `/deplacements`, `/phase`,
`/combat/portee`, `/combat/cible`, `/partie/etat` et `/flux`. Un visiteur de passage voit donc la
partie — et la suit en direct — et
peut consulter ce qui serait atteignable, comme avant. Ce qui demande une **place au camp actif** :
`/deplacer`, `/combat`, `/phase/suivante`. `POST /partie/nouvelle` demande seulement d'être assis :
recommencer n'est pas un coup, et **les places sont conservées** — ce sont les deux mêmes personnes,
et les vider enfermerait dehors celui-là même qui vient de cliquer.

Les refus rendent **401** quand personne n'est connecté, **403** quand quelqu'un l'est mais ne
tient pas ce qu'il faut, avec un `message` en français que la page affiche sous la barre d'outils.
Le reste des échecs garde le silence qu'il avait, leurs refus partant au journal.

Se déconnecter ne rend pas sa place : on revient s'y asseoir.

### Jouer contre l'IA

Le second compte peut être une machine. Le bouton **« Nouvelle partie contre l'IA »** du dialogue
de la table — visible quand on est assis et que l'autre camp est à donner : libre, ou déjà tenu
par l'IA — envoie `POST /partie/nouvelle` avec le corps `{"contre_ia": true}` : le scénario est
reposé, et le camp que le demandeur ne tient pas est confié à l'IA. Un camp tenu par un autre
humain n'est pas à donner — 409, on ne met personne à la porte, et la mise en place n'est pas
refaite.

L'IA n'a ni session ni compte Discord : elle occupe sa place sous la sentinelle `ia.JOUEUR_IA`
(`"ia"`, qu'aucun identifiant Discord — des chaînes de chiffres — ne peut porter), qui voyage
dans le dict des places comme n'importe quel identifiant — rien de plus à sauvegarder, rien de
plus à reprendre — et que `la_table()` affiche sous le nom « IA ». Un humain ne peut pas s'y
asseoir — la place est occupée — et `camp_actif_requis` ne peut jamais lui apparier une session.

Son tour se joue **côté serveur, dans la requête qui lui rend la main** : `faire_jouer_l_ia()`,
appelé à la fin de `POST /phase/suivante` — et à la création de la partie, pour le cas où le
scénario ouvre sur son camp. La stratégie vit dans le moteur (`moteur/ia.py`, voir
`moteur/README.md`) ; l'application ne fait qu'y passer le dé (`lancer_le_de`), sauvegarder et
journaliser. Une seule sauvegarde à la fin du tour : la version monte, et le navigateur voit les
coups de l'IA aussitôt par le flux, comme il verrait ceux d'un adversaire humain. Une
sauvegarde ne tombe donc jamais sur une phase tenue par l'IA — « / » n'a jamais à la faire jouer.

### Suivre la partie de l'adversaire

La page tient un **flux ouvert** vers le serveur — `GET /flux`, du Server-Sent Events — et n'en
redemande jamais rien. C'est le serveur qui écrit, au moment où la partie change, et à tous ceux
qui la regardent à la fois. Le navigateur voit donc le coup de l'adversaire en quelques
millisecondes, là où le sondage d'avant mettait jusqu'à trois secondes et posait vingt questions
inutiles pour une réponse utile.

Le canal est **à sens unique**, serveur → navigateur, et il le reste : tout ce que le joueur fait
part en `POST` sur les routes ordinaires, exactement comme avant. Le flux ne sert qu'à porter le
résultat d'un coup aux **autres**.

**Le mécanisme, en trois pièces** (`application/flux.py`) :

- un **abonné** par flux ouvert, c'est-à-dire par onglet qui regarde la partie ;
- une **boîte à une place** par abonné — un `Queue(maxsize=1)` dont le contenu est *remplacé*
  plutôt qu'empilé. Personne n'a besoin d'un état périmé : une requête qui fait monter la version
  trois fois (c'est le cas de `/partie/nouvelle`, qui repose le scénario puis laisse l'IA jouer)
  ne réveille l'abonné qu'une fois, et sur le dernier état ;
- `marquer_un_coup`, dans `app.py`, qui publie. **C'est le seul point de publication**, et c'est
  aussi le passage obligé de tout ce qui bouge : aucun coup ne peut être joué sans que les flux
  ouverts l'apprennent.

**Pourquoi la photo est prise au moment de publier.** Le plateau, le tour et le registre des
combats sont des module-globaux, et rien ne les protège. Si le générateur d'un flux allait les
relire à son réveil, il les lirait depuis le fil qui sert *son* flux, pendant qu'un autre fil est
peut-être en train de déplacer un pion. On ne lui laisse donc rien à relire : la photo est prise
une fois, dans le fil qui vient d'écrire, et c'est elle qui voyage.

**Ce qui se compose par destinataire.** Presque tout est partagé — les pions, la phase —, mais
pas la **table** : elle dit à chacun s'il est connecté, sous quel pseudo, et quels camps il
tient. C'est la seule part du message que le flux compose au moment d'écrire, pour un joueur
qu'il relit au dépôt à chaque fois (jamais mis en cache : quitter sa place se voit au message
suivant).

**Le numéro de version sert deux fois.** Il monte d'un cran à chaque coup joué, et c'est aussi
l'**identifiant d'événement** du flux — celui que le navigateur renvoie en `Last-Event-ID`
lorsqu'il se reconnecte. Le serveur sait alors s'il y a du retard à rattraper : si le numéro colle,
il ouvre le flux sur un simple commentaire ; sinon il envoie toute la partie. C'est ce qui fait
qu'un serveur redémarré, un réseau coupé ou un portable réveillé se rattrapent tout seuls, sans
une ligne de code pour cela.

**Un battement de cœur** — un commentaire SSE, `: battement` — traverse la connexion toutes les
20 secondes. Sans lui, un pare-feu, un proxy ou le navigateur finirait par refermer une connexion
qu'il croit morte.

**L'onglet fermé libère sa place.** La page ferme son flux sur `beforeunload` et `pagehide`, et
l'abonnement est de toute façon radié dès que le générateur est fermé, quoi qu'il arrive. Sans
cela, chaque page refermée laisserait une boîte à qui le serveur continuerait de déposer chaque
coup joué.

**Le repli est gardé.** Si l'`EventSource` échoue cinq fois de suite — un intermédiaire qui coupe
le SSE, un proxy d'entreprise —, la page referme le flux et retombe sur l'ancien sondage de
`GET /partie/etat?version=N`, toutes les trois secondes. Cette route reste servie pour cela : le
jeu ralentit, il ne casse pas.

Reposer la scène doit être **sans effet visible** sur ce qui n'a pas bougé : c'est pourquoi
l'inclinaison de chaque pion voyage avec lui (voir « Poser les pions »). Elle vient du plateau du
serveur, qui la retient d'un message à l'autre ; seul un pion déplacé se recouche. Pour la même
raison, le repère du bouton « localiser » est retenu par sa **case** et non par son image : la
scène reposée détruit toutes les images et les recrée, et le bouton s'éteindrait à chaque coup.

Ce que tout ceci demandera le jour d'une mise en production — serveur WSGI, Nginx, délais
d'attente, et pourquoi un seul worker — est dans `DEPLOIEMENT.md`, à la racine. Les endroits du
code concernés portent le marqueur `TODO: PRODUCTION`.

## Se connecter par Discord

Le flux OAuth2 tient en quatre temps, et tout ce qui parle à Discord est dans
`client_discord.py` :

1. `GET /connexion` tire un `state` (`Connexion.poser_un_etat_oauth`), le pose en session et
   redirige vers Discord ;
2. le joueur autorise, Discord le renvoie sur `GET /connexion/retour` avec un code et le `state` ;
3. la route **retire** le `state` de la session (`Connexion.reprendre_l_etat_oauth`) et le compare
   par `compare_digest` — un retour rejoué ne trouve donc plus rien à quoi se comparer —, puis
   échange le code contre un jeton et lit `/users/@me` ;
4. `Connexion.ouvrir` crée ou met à jour le joueur en base et ouvre la session, et l'on revient au
   plateau.

`POST /deconnexion` ferme la session. Elle est en POST comme tout ce qui change quelque chose ici :
un lien ou une image d'un autre site ne doit pas pouvoir déconnecter le joueur.

**Ce que la session porte** — et c'est `models/connexion.py` qui en décide, seul : l'identifiant
Discord, et le `state` le temps d'un aller-retour. Rien d'autre, et surtout pas le jeton d'accès —
le cookie de session de Flask est *signé, pas chiffré*, et son contenu se lit à qui le tient. Le
pseudo et l'avatar se relisent au dépôt à chaque requête, ce qui les tient à jour dès qu'ils
changent chez Discord.

Le cookie est `HttpOnly`, `SameSite=Lax` et `Secure` derrière HTTPS (`COOKIE_SECURISE=oui`).
**`Lax` et non `Strict`** : le retour de Discord est une navigation de premier niveau venue d'un
autre site, et `Strict` retiendrait le cookie — la session paraîtrait vide, le `state` serait
introuvable, et le flux ne pourrait jamais aboutir.

La portée demandée est `identify` seule. Pas `email` : le jeu n'en ferait rien, et une portée de
moins est un consentement de moins à demander. Le champ `courriel` de `moteur.models.joueur`
attend, au cas où.

**Aucune dépendance n'a été ajoutée pour tout cela**, et c'est le même parti que pour
`extensions.py`, qui a réécrit l'interface de Flask-MongoEngine plutôt que d'installer une
extension morte : `flask.session` suffit à la session, `urllib.request` aux deux appels HTTP.

### La couture qui rend le flux éprouvable

`create_app` accroche un **client d'identité** aux extensions de l'application, exactement comme
elle y accroche le dépôt : `ClientDiscord` en jeu, `ClientDiscordFactice` sous la configuration de
test. Le factice ne court-circuite rien — il rend une URL d'autorisation qui pointe vers **notre
propre route de retour**. Le navigateur la suit, revient avec un code et un état, et le vrai code
se déroule alors du début à la fin. C'est ce qui permet d'éprouver la connexion dans Chromium sans
qu'aucun paquet ne parte vers discord.com.

`AUTHENTIFICATION` n'est **pas** lu dans l'environnement, délibérément : une variable de `.env` qui
débranche l'authentification est une porte ouverte qu'une faute de frappe suffit à laisser béante.
Seule `ConfigDeTest` pose « factice ».

### Configurer une application Discord

1. Ouvrir le [Developer Portal](https://discord.com/developers/applications) et **New
   Application** ; lui donner un nom.
2. Onglet **OAuth2** : relever le **Client ID**, puis **Reset Secret** pour obtenir le **Client
   Secret** (il ne se réaffiche jamais — le copier tout de suite).
3. Toujours dans **OAuth2**, section **Redirects**, ajouter l'URI de retour **au caractère près** :
   `http://127.0.0.1:5000/connexion/retour` en développement. Discord la compare exactement :
   `localhost` n'y est pas `127.0.0.1`, et un `/` final de trop suffit à faire échouer l'échange.
4. Reporter les trois valeurs dans `.env` (`DISCORD_CLIENT_ID`, `DISCORD_CLIENT_SECRET`,
   `DISCORD_REDIRECT_URI`), et y ajouter une `SECRET_KEY`.
5. Pour s'autoriser la correction de la carte : activer le mode développeur dans Discord
   (Paramètres › Avancés), copier son propre identifiant depuis son profil, et le poser dans
   `ADMIN_DISCORD_IDS`.

Le portail ne demande **aucune portée à cocher** : elle est réclamée par l'URL d'autorisation, et
c'est `identify`.

## La mise en place

Le serveur ne tire plus rien au hasard : il lit la mise en place du scénario `NUMERO_DU_SCENARIO`
(4) dans `scenarios/` par `moteur.scenario`, une fois au démarrage, et la repose au premier
chargement de `/` — ou à chacun, si la persistance est débranchée.

- **Le placement vient du fichier, pas du serveur.** `scenarios/scenario-04-la-guerre-des-nains.json`
  donne « case → clé de pion » ; l'application n'y ajoute que ce qu'il faut pour l'affichage —
  l'image, le nom lisible, le mouvement et le camp, tous repris au catalogue de
  `game_box/pions/`. Le détail du déploiement et ses réserves sont dans `scenarios/README.md`.
- **La position de départ est reproductible.** Une partie neuve remet toujours les 52 unités aux
  mêmes cases : c'est ce qui permet d'éprouver un déplacement deux fois de suite et d'obtenir le
  même résultat. `POST /partie/nouvelle` — et, sans persistance, le simple rechargement — y
  ramène.
- **Le mouvement est celui du carton** : chaque pion emporte ses points, lus sur la photo et
  rangés dans `game_box/pions/pions.json`. La **force** sert maintenant au combat ; le tir et la
  portée n'y servent que pour la distance d'engagement d'un archer.
- **Le camp vient de la faction** (voir `moteur/README.md`) : il décide qui gêne qui. Ici, les
  nains sont l'alliance et les orques les ténèbres, et les deux masses se font face à 3 cases.
- Les vues d'ensemble ne sont toujours pas servies : les 4 photos de `21-vues-d-ensemble/` et les
  2 planchettes de suivi de `19-magiciens/` ne montrent pas un pion isolé, et `/pions/…` les
  refuse. Le scénario ne les nomme pas non plus.
- Une case n'accueille qu'un pion. Ce que le plateau garde d'un rechargement à l'autre dépend de
  la persistance (voir plus haut).

## Tests

Depuis la **racine du dépôt**, pour couvrir aussi le moteur :

```
make test
```

`make test` monte lui-même un MongoDB de test dans un conteneur — port 27018, base
`tenebrae_test`, à part de celui du jeu —, attend qu'il réponde, puis lance toute la suite en le
lui désignant. Sans Docker, `make test-rapide` lance la même suite sans base : les tests qui
demandent un vrai MongoDB se sautent d'eux-mêmes. `make mongo-arret` retire le conteneur, qui
reste sinon allumé d'une série à l'autre. `ARGS` passe des arguments à pytest :
`make test ARGS="-k persistance -v"`.

**Rien ne se vérifie à la main** : ni serveur lancé pour aller voir, ni `curl`. Ce qu'on veut
éprouver s'écrit en test, et ce qui se voit dans une page s'éprouve dans Chromium par Playwright.

`tests/test_diffuseur.py`, `tests/test_flux.py` et `tests/test_flux_navigateur.py` couvrent le
**flux SSE**, en trois couches. Le premier prend le diffuseur seul, sans Flask ni navigateur :
boîte à une place, coalescence de trois publications en un réveil, fan-out à plusieurs abonnés, et
radiation garantie — sur une sortie normale, sur une erreur, et sur un générateur abandonné, qui
est ce qui arrive quand un onglet se ferme. Le deuxième prend la route `/flux` par le client
Flask : mimetype et en-têtes (`Cache-Control`, `X-Accel-Buffering`), le commentaire d'ouverture à
qui est à jour et toute la partie à qui ne l'est pas, le `Last-Event-ID` qui prime sur `?version`
et le serveur redémarré qu'il rattrape, le coup poussé sans que personne ait rien demandé, le
battement, la **table composée par destinataire** — un joueur assis et un visiteur anonyme
reçoivent la même partie et deux tables différentes —, le joueur relu à chaque message, et dix
flux ouverts puis refermés qui ne laissent rien derrière eux. Le troisième ouvre Chromium : la
page tient bien un `EventSource`, elle ne sonde **plus jamais** `/partie/etat`, elle n'appelle
plus rien du tout au repos, un coup joué dehors — par un client HTTP indépendant du navigateur —
arrive en moins d'une seconde et demie, deux onglets le voient ensemble, un visiteur sans compte
le voit aussi, le repère de « localiser » survit à la scène reposée, le repli sur le sondage
s'installe quand `/flux` est coupé, la page se reconnecte et rattrape ce qu'elle a manqué, et un
onglet fermé libère son abonnement.

Le serveur des tests de navigateur est **concurrent** (`threaded=True` dans `tests/conftest.py` et
`tests/test_reprise_navigateur.py`) : depuis le flux, une page ouverte tient une requête en cours
tant qu'elle vit, et un serveur mono-thread ne servirait plus rien d'autre.

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
accepté change vraiment le plateau du serveur. Il couvre aussi le **tour** : `#phase` dans la
page, `/phase/suivante` qui saute la magie et alterne les joueurs, `/deplacer` refusé hors de la
phase de mouvement, `/combat/portee` selon la distance, et `/combat` qui retire le bon pion sur un
`DE` (dé fixé par `monkeypatch` de `app.lancer_le_de`) et ne touche à rien sur un recul. La règle
du **combat unique par phase** y a sa section : un attaquant et une cible refusés au second
combat, tout un groupe d'attaquants marqué d'un coup, deux unités du même carton suivies à part,
les listes `indisponibles` servies au navigateur, et la remise à zéro d'une phase de combat à la
suivante puis au tour d'après. Chaque test y part d'une **carte déserte** — la fixture
`carte_deserte` vide le plateau, ramène le tour à sa première phase et vide le registre des
combats, tous trois étant partagés d'une requête à la suivante. Ce que
contient le scénario lui-même est éprouvé à part, dans `moteur/tests/test_scenario.py` ; la
résolution des combats, dans `moteur/tests/test_combat.py` et `test_phase.py`.

`tests/test_plateau.py` ouvre la page dans Chromium avec Playwright : les 52 pions chargés et
centrés à moins d'un pixel, inclinés de moins de 5° — et **inclinés une fois pour toutes** : un
coup joué hors de la page fait reposer la scène par le flux, et les angles doivent être les
mêmes, seul un pion déplacé se recouchant —, carte qui reste à l'échelle après
redimensionnement, le zoom — boutons, molette qui garde son point sous le pointeur, pions qui
restent sur leur hexagone une fois approchés, échelle réglée à la main qu'un redimensionnement ne
défait pas —, la fiche du survol — les valeurs du carton des cinquante-deux unités comparées au
catalogue du moteur, la mention de remarques qui ne paraît qu'à bon escient, la photo, la case
d'un pion qu'on vient de déplacer, la fiche qui se referme en quittant le pion, qui ne paraît pas
sur un fantôme, dont les éléments s'empilent un par ligne, qui se pose **sous** la barre d'outils
et alignée sur son bord gauche, qui se lit **au corps de la barre**, qui ne fait pas grandir la
barre — à la fenêtre étroite comme à la large — et qui ne capte pas les clics —, la mise en page
elle-même — le panneau qui ne déborde ni de la fenêtre ni en défilement latéral à 1400, 800 et
480 px, et la carte qu'il ne déplace ni ne rétrécit —, puis le cycle complet clic → fantômes →
déplacement, à l'ajustement comme une fois approché. Les fantômes attendus sont ceux que le
plateau du serveur calcule — il tourne dans le même processus, on le lit directement — et un test
pose un adversaire au contact pour vérifier que le clic en montre alors moins. Enfin le **tour et
le combat** : le libellé de phase, « Phase suivante » qui saute la magie, le mouvement muet en
phase de combat, la cible surlignée en rouge, le cycle complet — amener un Nain au contact d'une
Orque, passer en combat, désigner cible et attaquant, « Attaquer », et voir les surlignages
retomber —, et le **combat unique par phase** : les unités engagées grisées exactement là où le
registre du serveur les inscrit, le clic qui ne les reprend pas, et le grisage qui tombe à la
phase suivante.

`tests/test_persistance.py` est le seul à brancher la persistance, sur **mongomock** — un MongoDB
en mémoire : aucun serveur n'est demandé, et le fichier se saute de lui-même si mongomock n'est pas
installé. Il couvre l'ouverture d'une partie au premier chargement, la reprise après un
redémarrage simulé (le déplacement retrouvé, la phase retrouvée, le registre des combats retrouvé),
l'élimination qui ne revient pas, les **inclinaisons** écrites, reprises et réécrites au
déplacement — et la sauvegarde sans ce champ qui reste reprenable —, la sauvegarde d'un autre
scénario écartée, `POST
/partie/nouvelle` qui ouvre un second document sans effacer le premier — y compris quand les deux
partagent la même date, l'identifiant les départageant —, et l'aller-retour du dépôt seul. Partout
ailleurs la configuration de test pose le **dépôt nul** : les autres fichiers de tests ne voient
aucune base, et `GET /` y repose la mise en place comme avant.

`tests/test_reprise_navigateur.py` éprouve la reprise **vue de l'écran**, dans Chromium : déplacer
un pion puis recharger la page et le retrouver à sa nouvelle case, la phase retrouvée de même,
`POST /partie/nouvelle` qui repose les 52 unités, et les cartons qu'un rechargement retrouve
couchés sous le même angle — celui d'avant pour les pions immobiles, le nouveau pour le pion
déplacé. Chaque test y tourne **deux fois** — sur
mongomock, et sur le vrai MongoDB dès que `MONGODB_URI_TEST` en désigne un qui répond, ce que
`make test` fait — de sorte que la chaîne complète est éprouvée telle qu'elle tourne en vrai, sans
avoir à lancer le serveur soi-même.

`moteur/tests/test_places.py` éprouve le registre des places seul, sans requête ni base : prendre
un camp, la place qu'on ne reprend pas à son occupant, l'aller-retour de la sérialisation, et une
sauvegarde d'avant les joueurs qui laisse simplement la table vide. Il a suivi son sujet dans le
moteur ; `tests/test_connexion_modele.py` lui répond de ce côté-ci, et éprouve `Connexion` seule :
ce que la session porte et ce qu'elle ne porte pas, le joueur relu au dépôt à chaque demande, un
identifiant inconnu qui redevient anonyme, et l'état de l'OAuth2 retiré dès qu'on le reprend.

`tests/test_connexion.py` déroule le flux OAuth2 **en entier** contre le client factice : l'état
tiré au sort et vérifié, celui qui ne correspond pas et celui qu'on rejoue, le retour sans code,
le refus du joueur sur la page de Discord, un Discord muet qui rend 502, le joueur créé puis mis à
jour, et le jeton d'accès qui n'entre jamais dans la session. Puis ce que le serveur refuse : le
visiteur anonyme qui voit la carte mais ne déplace rien, le joueur qui ne tient pas le camp actif,
celui qui n'a pris aucune place, le second camp refusé à qui en tient un, la place qu'on ne reprend
pas, les deux joueurs qui s'assoient chacun au sien, les places conservées par
`POST /partie/nouvelle`, et la correction de la carte réservée aux comptes déclarés.

`tests/test_connexion_navigateur.py` fait la même chose à l'écran : le bouton qui propose de se
connecter puis montre le pseudo, **la barre d'outils qui ne grandit pas d'un pixel** une fois
l'avatar posé — c'est ce test qui a fait choisir un avatar dimensionné en `em` —, le pseudo à
rallonge qui ne pousse pas les boutons hors de vue, le dialogue de la table, le grisage hors de son
tour, le message qu'un coup refusé affiche, et surtout **deux navigateurs ouverts en même temps** :
l'un passe sa phase ou prend place, l'autre l'apprend sans rien recharger.

`tests/test_ia.py` éprouve la partie contre l'IA côté serveur : la création refusée à l'anonyme,
au joueur sans place et quand l'autre camp est tenu par un humain, l'IA assise et montrée « IA »
à la table, son tour d'ouverture joué dans la foulée quand elle tient l'Alliance, son tour
déclenché par le `POST /phase/suivante` qui lui rend la main — le dé fixé par `monkeypatch`,
comme partout —, et sa place que personne ne peut prendre. La stratégie elle-même est éprouvée
dans le moteur (`moteur/tests/test_adversaire_artificiel.py`) ; la persistance de sa place, dans
`tests/test_persistance.py`. `tests/test_ia_navigateur.py` refait le tour à l'écran : le bouton
caché à qui n'est pas assis, le camp adverse confié à l'IA d'un clic, et l'ouverture du scénario
jouée par elle avant que la main revienne au joueur.

**Toute la suite joue connectée.** La fixture `client` du `conftest.py` ouvre une session et assied
le joueur de test **aux deux camps** — c'est ce qui laisse les tests écrits avant les joueurs
traverser les deux camps dans une même session, sans en réécrire un seul. Les fixtures de page
Playwright passent, elles, par `/connexion` avant d'ouvrir le plateau : plutôt que de fabriquer un
cookie, elles déroulent le vrai flux, que le client factice referme sur notre propre route de
retour. Pour éprouver un visiteur de passage, prendre `client_anonyme`.

Les tests de navigateur demandent Chromium :

```
make navigateur
```
