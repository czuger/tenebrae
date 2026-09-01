# Ave Tenebrae

*Ave Tenebrae* est un wargame fantastique de François Marcela-Froideval, publié par Jeux Descartes
(2ᵉ édition, 1986) : deux armées, une carte d'hexagones, 127 planches de pions en carton.

Ce dépôt fait deux choses. Il **archive** le jeu — le fascicule de règles transcrit en Markdown,
la carte relevée hexagone par hexagone, l'inventaire photographié des pions et les valeurs de leurs
cartons — et il en **fait un jeu jouable** : un moteur de règles en Python et un serveur Flask où
deux joueurs, identifiés par Discord, se déplacent et se combattent tour à tour sur la carte du
navigateur.

Tout est en français, code compris. Le jeu n'est pas terminé : le mouvement et le combat tournent,
la magie non.

## Structure

```
tenebrae/
├── base_material/   les sources brutes — ne pas y puiser
├── game_box/        le matériel de jeu — la source de vérité
├── moteur/          les règles, en Python
├── scenarios/       les mises en place, un JSON par scénario
├── application/     le serveur Flask et la carte du navigateur
├── Makefile         lance la suite de tests (et son MongoDB)
└── .env.example     la configuration à recopier en .env
```

### `base_material/` — les sources brutes

Le PDF du fascicule (16 pages scannées), un article de blog archivé qui donne le découpage des
planches de pions, et 144 photos de la boîte, de la carte et des pions. **On n'y travaille pas** :
tout ce qui en a été tiré vit dans `game_box/`. On n'y revient que pour vérifier une transcription.

### `game_box/` — le matériel de jeu

La source de vérité du dépôt. Le code lit ici, et nulle part ailleurs.

| Fichier | Contenu |
| --- | --- |
| `ave_tenebrae_regles.md` | le fascicule transcrit : règles, magie, sortilèges, scénarios, tableaux |
| `map.jpg` | la carte du jeu, scannée |
| `carte.json` | 2280 hexagones, `"q,r,s"` → un terrain |
| `carte_details.json` | les mêmes, mais avec **tous** les éléments de chaque case |
| `map_fix.json` | les corrections de terrain relevées à l'œil, appliquées par le moteur |
| `carte_controle.jpg` | la carte teintée par terrain, pour vérifier la transcription à l'œil |
| `carte.md` | comment la carte a été transcrite, et ce qui reste incertain |
| `extraction_carte.py` | régénère les trois fichiers de carte depuis `map.jpg` (une dizaine de minutes) |
| `pions/` | 127 photos de pions classées par faction, `pions.json` (les valeurs des cartons) et leur index |

### `moteur/` — les règles

Du Python sans rien de web, qui n'utilise que la bibliothèque standard. La carte et le catalogue
des pions sont lus **une fois, à l'import** : le plateau est imprimé, il ne change pas en cours de
partie.

| Module | Contenu |
| --- | --- |
| `hexagone.py` | `Hex` — voisinage, coûts de terrain, déplacements (Dijkstra), zones de contrôle |
| `pion.py` | `Pion` — les valeurs du carton, et le camp de sa faction |
| `plateau.py` | `Plateau` — qui occupe quelle case ; le seul objet mutable du moteur |
| `scenario.py` | `Scenario` — une mise en place lue dans `scenarios/`, et le plateau qu'elle donne |
| `phase.py` | `Tour` — mouvement → magie → combat, pour chaque joueur, en boucle |
| `combat.py` | le Tableau I du fascicule, et le registre d'un combat par unité et par phase |

`moteur/README.md` détaille chaque classe, les coûts de terrain, les zones de contrôle, et la
liste des règles du fascicule qui ne sont pas encore jouées.

### `scenarios/` — les mises en place

Le fascicule dit « l'armée naine se masse au sud du volcan de Toth » et ne dit jamais quel pion va
sur quelle case. Le passage de la phrase aux hexagones a été fait **une fois, à la main**, et son
résultat vit ici, un JSON par scénario. Seul le n° 4, « La guerre des nains », est fixé.

### `application/` — le serveur

Une application Flask (`create_app`) qui affiche la carte, y pose le scénario, et sert ce que le
moteur décide. **Le navigateur ne juge jamais de la légalité d'un coup** : cliquer un pion demande
au serveur où il peut aller, et le serveur répond d'après `moteur/`.

- La partie se joue **à deux, un joueur par camp**, identifiés par **Discord OAuth2**. La carte
  reste visible sans compte ; jouer demande d'être connecté et de tenir le camp actif.
- Elle est **sauvegardée dans MongoDB** à chaque coup — positions, phase, combats déjà livrés, et
  qui tient quel camp — et reprise au chargement de `/`.
- `/admin/map_fix` sert à corriger la transcription de la carte, réservée aux comptes déclarés
  dans `ADMIN_DISCORD_IDS`. C'est le seul endroit où l'application écrit dans `game_box/`.

`application/README.md` détaille les routes, l'affichage, les phases, le combat et la connexion.

## Installer

```
python3 -m pip install -r requirements.txt
cp .env.example .env       # puis renseigner SECRET_KEY et les identifiants Discord
```

Sans `SECRET_KEY`, l'application refuse de démarrer. Sans MongoDB, mettre `PERSISTANCE=aucune`
dans le `.env` : la partie repart alors de la mise en place à chaque chargement.

## Lancer

```
cd application && python3 app.py
```

Puis <http://127.0.0.1:5000/> pour le plateau, <http://127.0.0.1:5000/admin/map_fix> pour la
correction de la carte.

## Vérifier

Toute vérification passe par la suite de tests — on ne lance pas le serveur pour voir si ça
marche.

| Commande | Ce qu'elle fait |
| --- | --- |
| `make test` | monte un MongoDB de test dans Docker, puis lance toute la suite |
| `make test-rapide` | la même suite sans base : les tests qui en demandent une se sautent |
| `make test-navigateur` | les seuls tests Chromium (Playwright) |
| `make navigateur` | installe Chromium pour Playwright |
| `make mongo-arret` | retire le conteneur de test |

Les tests vivent dans `moteur/tests/` et `application/tests/`, et se lancent depuis la racine.

## Où lire ensuite

| Fichier | Sujet |
| --- | --- |
| `game_box/ave_tenebrae_regles.md` | les règles du jeu |
| `game_box/carte.md` | comment la carte a été transcrite, et ses réserves |
| `game_box/pions/README.md` | l'inventaire des 127 pions |
| `moteur/README.md` | les classes du moteur et l'interprétation des règles |
| `scenarios/README.md` | le format des mises en place |
| `application/README.md` | le serveur, l'affichage, les phases, la connexion Discord |
| `CLAUDE.md` | les conventions de travail du dépôt |

## Sources

Le matériel d'origine est celui de Jeux Descartes (1986) ; il est archivé ici pour l'étude et
n'est pas redistribuable. Le découpage des planches de pions vient de l'article « Vintageboard 1 »
de R-One Chaff (irlboardgames.blogspot.com), conservé dans `base_material/`.
