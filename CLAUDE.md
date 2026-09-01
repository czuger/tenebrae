# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Nature du dépôt

Travail d'archivage et de transcription autour d'*Ave Tenebrae*, wargame fantastique de François
Marcela-Froideval (Jeux Descartes, 2ᵉ éd. 1986) : convertir des sources brutes (PDF scanné, page de
blog archivée, photos) en documents Markdown et en données exploitables, **puis en faire un jeu**.
Le jeu existe : un moteur de règles en Python, un serveur Flask, une partie à deux joueurs
sauvegardée dans MongoDB.

**Le contenu est en français** — règles, README, noms de fichiers, code (noms de classes, de
méthodes et de variables). Toute production nouvelle (documentation, noms de répertoires, slugs de
fichiers) doit rester en français, avec des slugs sans accents ni apostrophes
(`morts-vivants-01-20-unites-de-squelettes.jpg`). Seuls les messages de commit sont en anglais.

## Structure

Cinq répertoires, avec des statuts très différents :

| Répertoire | Rôle |
| --- | --- |
| `base_material/` | **Sources brutes. Porte un `CLAUDE.md` qui dit « DO NOT USE THE CONTENT OF THIS DIRECTORY ».** Le PDF des règles, l'article de blog archivé, les 144 photos. Ne pas y puiser pour un travail courant : tout ce qui en a été tiré vit déjà dans `game_box/`. On n'y retourne que pour vérifier ou compléter une transcription, et alors on met à jour le dérivé. |
| `game_box/` | **Le matériel de jeu. Porte un `CLAUDE.md` qui dit « THIS DIRECTORY CONTAINS THE SOURCE OF TRUTH ».** Règles transcrites, carte et sa grille d'hexagones, script d'extraction, et `pions/` (inventaire des 127 pions + `pions.json`). C'est là que doit lire et écrire le code du jeu. |
| `moteur/` | **Les règles, en Python.** Deux constantes lues au démarrage — la carte (la transcription recouverte par les corrections de `map_fix.json`) et le catalogue des pions (`pions.json`) — puis sept modules : `hexagone.py` (`Hex` : voisinage, coûts de terrain, déplacements, zones de contrôle), `pion.py` (`Pion` : valeurs du carton, camp), `plateau.py` (`Plateau` : qui occupe quelle case, et sous quel angle le carton y est couché), `scenario.py` (`Scenario` : une mise en place lue dans `scenarios/`), `phase.py` (`Tour` : mouvement → magie → combat, en boucle), `combat.py` (Tableau I du fascicule, et `SuiviDeCombat`) et `ia.py` (l'adversaire artificiel : ciblage, marche, concentration des attaques — et la sentinelle `JOUEUR_IA` de sa place). À côté, **les entités du jeu** : `models/` (`Partie`, `Joueur`, `Places` — un fichier par modèle) et `depots/` (leur accès en base, un module par sujet). Rien de web ici — ni Flask, ni session, ni requête ; la bibliothèque standard suffit aux règles, mongoengine ne servant qu'aux deux documents et à leurs dépôts. Voir `moteur/README.md`. |
| `scenarios/` | **Les mises en place, fixées une fois pour toutes**, un fichier JSON par scénario du fascicule. Le fascicule dit « l'armée naine se masse au sud du volcan de Toth » ; le passage de la phrase aux hexagones a été fait à la main, et ce répertoire en garde le résultat. Seul le n° 4 est fixé à ce jour. Voir `scenarios/README.md`. |
| `application/` | **Le serveur.** Application Flask (factory `create_app`) qui affiche la carte, la mise en place d'un scénario (le n° 4), et sert les déplacements et les combats calculés par `moteur/`. Elle lit `game_box/` et `scenarios/`. Elle écrit à deux endroits : `game_box/map_fix.json`, par la route d'admin `/admin/map_fix`, et **MongoDB** — la partie en cours (positions, inclinaison des pions, phase, registre des combats, et qui tient quel camp), sauvegardée à chaque coup et reprise au chargement de `/`, plus les **joueurs** connus. La base n'est jamais touchée depuis une route : tout passe par un dépôt (`moteur/depots/` pour le jeu, `application/depots/` pour le reste), et les référentiels restent en fichiers. Elle modélise deux choses, et seulement ce qui n'est pas du jeu : la **connexion** (`models/connexion.py`) — le lien entre une session Flask et le joueur du moteur, désigné par son identifiant Discord — et la **vue de la carte** (`models/vue.py`, écrite par `depots/vue.py`), c'est-à-dire l'échelle et le point que chaque joueur avait au centre, rendus au chargement suivant pour qu'un rafraîchissement ne défasse plus son zoom. La partie se joue **à deux, un joueur par camp**, identifiés par **Discord OAuth2** : la carte reste publique, les coups demandent d'être connecté et d'occuper le camp actif, et `/admin/map_fix` est réservée aux comptes de `ADMIN_DISCORD_IDS`. Le second camp peut être **confié à l'IA** (`POST /partie/nouvelle` avec `{"contre_ia": true}`) : le serveur joue alors son tour entier — par `moteur/ia.py` — dans la requête qui lui rend la main. L'authentification n'a coûté **aucune dépendance** (`flask.session` et `urllib`). Chaque navigateur suit la partie de l'autre par un **flux SSE** (`GET /flux`, le diffuseur étant dans `flux.py`) : le serveur pousse la partie quand elle change, et `marquer_un_coup` est le seul point de publication. `/partie/etat` reste servie en repli. Le
**journal de la partie** voyage avec elle : il s'écrit dans `journal_de_combat.log` **et** dans
une file bornée en mémoire, que la page montre en colonne sous la fiche — d'où la règle
« journaliser avant de marquer le coup ». Voir `application/README.md`, et `DEPLOIEMENT.md` à la racine pour ce que le flux demandera en production. |

`todo.txt` (racine) porte les consignes de travail de l'utilisateur.

Les secrets — connexion MongoDB, application Discord, `SECRET_KEY` — vivent dans `.env` à la
racine, **non versionné** : voir `.env.example`, que `application/config.py` lit une fois au
démarrage. Sans `SECRET_KEY`, l'application refuse de démarrer plutôt que d'en tirer une au hasard.

## Architecture

Quatre règles, et elles ne se négocient pas au cas par cas.

**La logique de jeu réside intégralement dans le moteur, jamais dans l'application.** La partie et
le joueur *en tant qu'entités de jeu* sont dans `moteur/models/`, avec la table des places ; leur
accès en base est dans `moteur/depots/`. Le moteur n'importe **rien** de l'application : pas de
Flask, pas de `session`, pas de `request`, aucune notion d'utilisateur web. Une partie se joue
depuis un interpréteur, sans serveur. La dépendance ne va que dans un sens — l'application importe
le moteur.

**L'application ne modélise que ce qui n'est pas du jeu**, et le fait dans `application/models/`,
avec son propre `application/depots/` quand il y a une base à écrire. Deux modèles à ce jour :
`connexion.py` — la session, dont rien n'est persisté — et `vue.py`, l'échelle et le point de la
carte qu'un joueur avait au centre. La vue est ici et non dans le moteur parce que **le moteur ne
sait pas qu'il existe une image** : une partie se joue depuis un interpréteur, où le zoom ne veut
rien dire ; l'inclinaison d'un pion, elle, est du plateau — les deux joueurs la voient pareil,
quand une vue n'appartient qu'à une paire d'yeux. Les deux modèles **référencent le joueur du
moteur par son identifiant** (`discord_id`, une chaîne) et ne doublent aucune de ses données : ni
pseudo, ni avatar, ni date. Le joueur est relu au dépôt à chaque demande. Le reste de
l'application est de l'orchestration web — routes, décorateurs d'autorisation, sérialisation vers
les gabarits — et rien d'autre.

**Un fichier par modèle, tous les modèles dans un répertoire `models/`.** Un fichier qui
regrouperait deux classes de modèle est à éclater. Le `__init__.py` de ces répertoires documente
et ne réexporte rien : `Places` n'a besoin que de la bibliothèque standard, et réexporter les
documents à côté ferait payer mongoengine à qui ne veut qu'un registre de places — comme à
l'application montée sans persistance, qui se construit aujourd'hui sans lui. On importe donc
toujours le module précis : `from moteur.models.places import Places`.

**Pas d'imports relatifs, jamais.** Aucun `from .module import ...` ni `from ..paquet import ...` :
toujours le chemin absolu (`from moteur.depots.joueur import DepotDeJoueursMongo`,
`from models.connexion import Connexion`). Aucun paquet n'est installé — c'est le `conftest.py` de
la racine, et un `sys.path.insert` en tête d'`app.py`, qui mettent la racine et `application/` sur
le chemin —, et un import relatif y casserait selon d'où l'on lance.

Un renommage de collection mongoengine, lui, se demande : les schémas existants (`parties`,
`joueurs`) restent compatibles tant que personne n'a de raison explicite d'en changer.

## Versionnement

**Tout est versionné, sources brutes comprises.** C'était l'inverse au début du projet — les
28 Mo de `base_material/` étaient exclus — et la documentation en portait un long avertissement :
il n'a plus lieu d'être. Le dépôt pèse une quarantaine de mégaoctets et l'assume ; un nouveau
clone arrive complet, transcriptions **et** sources, et retoucher une transcription ne demande
rien d'autre.

Ce qui reste hors de git est court, et tient en deux fichiers :

| Fichier | Ce qu'il exclut | Pourquoi |
| --- | --- | --- |
| `.gitignore` | `.env` | les secrets : connexion MongoDB, identifiants Discord, `SECRET_KEY` |
| | `application/journal_de_combat.log` | une trace d'exécution, propre à une machine |
| | `.idea/`, `__pycache__/`, `.pytest_cache/` | outillage local et caches |
| `.git/info/exclude` | `/.python-version` | le virtualenv pyenv est un choix local |

`.git/info/exclude` garde aussi trois motifs **périmés** — `/images/`,
`/ave_tenebrae_regles.pdf`, `/vintageboard-1-ave-tenebrae.html` — qui visaient la racine avant le
déplacement des sources dans `base_material/`. Ils ne correspondent plus à rien et ne protègent
plus rien : les fichiers qu'ils nommaient sont aujourd'hui suivis. Sans effet, donc, mais
trompeurs à la lecture.

Un seul point de vigilance subsiste : **`.DS_Store` n'est ignoré nulle part**, et la skill
`/commit` ajoute tous les fichiers. Vérifier `git status` avant de commiter.

## Les dérivés et leurs sources

Le rapport entre les deux n'a pas changé, même si tout est désormais versionné : on lit et on
écrit dans les dérivés, et on ne remonte à la source que pour vérifier.

| Chemin | Rôle |
| --- | --- |
| `base_material/ave_tenebrae_regles.pdf` | Fascicule de règles scanné, 16 pages |
| `base_material/vintageboard-1-ave-tenebrae.html` | Article de blog archivé (« Vintageboard 1 », R-One Chaff, irlboardgames.blogspot.com) ; contient le découpage des planches de pions |
| `base_material/images/` | 144 photos de la boîte, de la carte et des planches de pions |
| `game_box/ave_tenebrae_regles.md` | Transcription des règles |
| `game_box/map.jpg` | Carte du jeu (10 Mo) |
| `game_box/carte.json` | 2280 hexagones, `"q,r,s"` → terrain |
| `game_box/carte_details.json` | `"q,r,s"` → tous les éléments de l'hexagone |
| `game_box/carte_controle.jpg` | Carte teintée par terrain, pour vérification à l'œil |
| `game_box/carte.md` | Documentation de la transcription de la carte |
| `game_box/map_fix.json` | Corrections de terrain relevées à l'œil sur `/admin/map_fix`, appliquées par le moteur |
| `game_box/extraction_carte.py` | Régénère `carte.json`, `carte_details.json` et `carte_controle.jpg` depuis `map.jpg` |
| `game_box/pions/` | Inventaire des 127 pions (copies renommées) + `pions.json`, les valeurs des cartons |
| `scenarios/*.json` | Mises en place fixées, une par scénario |

## Outillage

Pas de packaging, pas de CI. Ne pas en introduire sans qu'on le demande. Le seul échafaudage est
le `Makefile` de la racine, qui sert à lancer les tests.

### Vérifier : toujours par un test, jamais à la main

**Toute vérification passe par la suite de tests, lancée par `make test`.** C'est une règle, pas
une préférence :

- **Ne jamais lancer l'application pour voir si ça marche** — pas de `python3 app.py` en tâche de
  fond suivi de `curl`, pas de `python3 -c` jetable. Ce genre de vérification ne se rejoue pas,
  ne prouve rien à personne d'autre, et laisse des serveurs et des conteneurs derrière elle.
- **Ce qu'on veut éprouver s'écrit en test**, à côté des autres, pour qu'on puisse le réessayer.
  Une nouvelle fonctionnalité arrive donc avec ses tests ; une vérification qu'on a eu envie de
  faire une fois vaut d'être gardée.
- **Le navigateur, c'est Playwright** (`application/tests/test_plateau.py`,
  `test_map_fix_navigateur.py`, `test_connexion_navigateur.py`, `test_reprise_navigateur.py`) :
  c'est là qu'on ouvre une page, qu'on clique un pion, qu'on recharge. Pas dans un vrai navigateur
  ouvert à la main.

| Commande | Ce qu'elle fait |
| --- | --- |
| `make test` | monte un MongoDB de test dans un conteneur Docker (port 27018, base `tenebrae_test`), attend qu'il réponde, puis lance toute la suite |
| `make test-rapide` | la même suite sans base : les tests qui demandent un vrai MongoDB se sautent d'eux-mêmes |
| `make test-navigateur` | les seuls tests Chromium |
| `make mongo-arret` | retire le conteneur (il reste allumé entre deux `make test`) |
| `make navigateur` | installe Chromium pour Playwright |
| `make test ARGS="-k persistance -v"` | `ARGS` est passé tel quel à pytest |

Les tests vivent dans `moteur/tests/` et `application/tests/` (pytest + Playwright, à la demande de
l'utilisateur) et se lancent **depuis la racine** — le `conftest.py` de la racine met le dépôt sur
`sys.path`, aucun paquet n'étant installé. `python3 -m pytest` marche donc aussi, mais sans la
base : préférer `make test`.

L'autre exécutable est le script d'extraction de la carte, à lancer **depuis `game_box/`** (il
travaille en chemins relatifs) :

```
cd game_box && python3 extraction_carte.py
```

Dépendances (`requirements.txt`) : Pillow, numpy, scipy pour ce script, Flask, mongoengine et
python-dotenv pour l'application, pytest, pytest-playwright et mongomock pour les tests ; le
moteur n'utilise la bibliothèque standard que pour ses règles — ses deux documents et leurs
dépôts demandent mongoengine, et rien d'autre. Elles sont installées dans le virtualenv pyenv
`tenebrae` que `.python-version` (racine, non versionné) sélectionne automatiquement ; `python3`
suffit.
Le script d'extraction tourne une dizaine de minutes et prend environ 2 Go de mémoire.

## `game_box/carte.json` — grille d'hexagones

`game_box/carte.md` est la référence : système de coordonnées, géométrie de calage sur `map.jpg`,
vocabulaire des 16 terrains, règle de priorité, table des lieux nommés, méthode et réserves. Le lire
avant de toucher aux données de la carte.

- Grille **flat-top, décalage odd-q**, 57 colonnes × 40 lignes = 2280 hexagones ; clés cubiques
  `"q,r,s"` avec `q + r + s = 0`.
- **La carte du jeu n'est pas `carte.json` seul** : le moteur pose `map_fix.json` par-dessus
  `carte_details.json` à son démarrage (`CARTE_TRANSCRITE` + `CORRECTIONS_APPLIQUEES` → `CARTE`).
  Une correction remplace le terrain principal et laisse les éléments secondaires. Corriger la
  carte ne se fait donc **jamais** en éditant `carte.json` : on relève dans `map_fix.json` par
  `/admin/map_fix`, ou on corrige le script d'extraction.
- `carte.json` ne donne **qu'un terrain par hexagone** (priorité : lieux construits > lac >
  montagne > colline > bois > faille > rivière > route > chemin > plaine) ; `carte_details.json`
  garde tout ce qui a été détecté. Les deux fichiers doivent rester cohérents : les régénérer
  ensemble avec le script, jamais éditer un seul à la main.
- Le classement est automatique **sauf les lieux construits et la Faille de Tsaroth**, relevés à la
  loupe et codés en dur dans `extraction_carte.py` (`MORGENSTERN`, `FORTS`, `CHATEAUX`, `TOURS`,
  `ILES`, `RUINES`, `VILLAGES`, `FAILLE`). Une correction de site se fait là, pas dans le JSON.
- Deux constantes d'amorce (`AMORCE_TAILLE`, `AMORCE_ORIGINE`) initialisent le calage de la grille.
  L'ajustement aux moindres carrés converge ensuite seul, mais elles restent nécessaires pour que la
  numérotation des colonnes et des lignes tombe juste : ne pas y toucher sans revérifier
  `carte_controle.jpg`.
- Les réglages numériques du script sont calés sur ce scan précis (6173 × 5102 px) et ne sont pas
  génériques.
- **Les incertitudes sont conservées, pas résolues** : la section « Réserves sur la transcription »
  de `carte.md` documente les collines (absentes de la carte, donc interprétées), les rivières
  traitées comme terrain d'hexagone au lieu d'arête, l'étendue floue des ruines de Ghaarth, un nom
  de village illisible. Y ajouter tout nouveau doute plutôt que de trancher sans source.
- Vérifier une modification en regardant `carte_controle.jpg`, pas en relisant le JSON.

## `game_box/ave_tenebrae_regles.md` — conventions de transcription

Suivre ces conventions pour toute correction ou complétion (elles sont posées dans l'en-tête du
fichier lui-même) :

- **Texte seul** : les illustrations du fascicule ne sont pas reprises, mais leur contenu
  informatif est reformulé — le schéma « Anatomie d'un pion » est rendu en bloc ASCII *et* en
  tableau, les symboles des pions en tableau à deux colonnes doubles avec approximations Unicode
  (`⊠ Infanterie`, `↑ Phalange`) ou description entre parenthèses quand aucun glyphe ne convient
  (`(créature ailée) Volants`).
- **Tous les tableaux du fascicule sont convertis en tableaux Markdown** (jamais en texte préformaté).
- **Orthographe modernisée** : le fascicule est composé en caractères gothiques où le glyphe « b »
  note « v » ; le texte est rétabli en français moderne.
- Structure : `#` pour les grandes parties (Règles, Unités spéciales, Magie, Livre des sortilèges,
  Points d'achat, Scénarios, Tableau des terrains), `##`/`###` en dessous. Les sortilèges portent
  en titre les initiales des lanceurs autorisés : `### Boule de feu — *M, N*` (M = mage,
  C = clerc, N = nécromancien).
- Séparateurs `---` entre les grandes sections.

## `game_box/pions/` — inventaire des pions

127 photos de pions, copiées depuis `base_material/images/` (les originaux y restent **intacts** ;
ce répertoire ne contient que des copies renommées) et classées en 21 répertoires numérotés par
faction ou utilité, d'après le découpage donné par l'article de blog. `pions.json` s'y ajoute :
les valeurs relevées à l'œil sur les cartons, que `moteur.pion` lit au démarrage.

- Nommage : `NN-faction/faction-NN-<description-slugifiee>.jpg`, la numérotation reflétant l'ordre
  de présentation dans la source.
- `game_box/pions/README.md` est l'index maître : sommaire des 21 répertoires, répartition en camps
  (Alliance / Ténèbres / neutre), puis une table par faction associant chaque fichier à son contenu
  **et à sa photo d'origine**. Toute nouvelle copie doit être ajoutée à ces tables avec sa
  provenance.
- **Les incertitudes de la source sont conservées, pas résolues** : les libellés `(renforts ?)` et
  les interprétations d'initiales (`K` = kobolds ?) gardent leur point d'interrogation, et la
  section « Réserves sur l'inventaire » en fin de README documente les lacunes connues (photo
  manquante des cavaleries lourdes du Chaos, initiales des non-humains non expliquées par les
  règles, cinq mouvements illisibles). Ne pas trancher ces points sans source ; les ajouter à cette
  section si de nouveaux doutes apparaissent.
- La section finale liste les 17 images volontairement non reprises (couvertures, vues de carte,
  habillage du blog).

## Commits

**Ne jamais commiter de sa propre initiative.** C'est l'utilisateur qui décide quand et quoi
commiter : laisser le travail dans l'arbre de travail et le lui signaler. Ne commiter que sur une
demande explicite pour ce commit-là — invoquer `/commit`, ou dire « commit ». Une consigne comme
« versionne ce fichier » veut dire « ajoute-le au dépôt », pas « commit ». Une autorisation donnée
une fois ne vaut pas pour la suivante.

Messages courts en anglais, une phrase — le contenu est en français, les messages de commit ne le
sont pas. La skill `/commit` du projet produit un message d'une phrase, ajoute tous les fichiers et
commit : « tous les fichiers » veut bien dire tous, `.DS_Store` compris s'il traîne. Un coup d'œil
à `git status` avant.
