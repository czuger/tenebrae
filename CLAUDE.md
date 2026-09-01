# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Nature du dépôt

Travail d'archivage et de transcription autour d'*Ave Tenebrae*, wargame fantastique de François
Marcela-Froideval (Jeux Descartes, 2ᵉ éd. 1986) : convertir des sources brutes (PDF scanné, page de
blog archivée, photos) en documents Markdown et en données exploitables. **L'objectif à terme est
d'en faire un jeu** ; du code va s'ajouter.

**Le contenu est en français** — règles, README, noms de fichiers. Toute production nouvelle
(documentation, noms de répertoires, slugs de fichiers) doit rester en français, avec des slugs sans
accents ni apostrophes (`morts-vivants-01-20-unites-de-squelettes.jpg`). Seuls les messages de
commit sont en anglais.

## Structure

Cinq répertoires, avec des statuts très différents :

| Répertoire | Rôle |
| --- | --- |
| `base_material/` | **Sources brutes. Porte un `CLAUDE.md` qui dit « DO NOT USE THE CONTENT OF THIS DIRECTORY ».** Le PDF des règles, l'article de blog archivé, les 144 photos. Ne pas y puiser pour un travail courant : tout ce qui en a été tiré vit déjà dans `game_box/`. On n'y retourne que pour vérifier ou compléter une transcription, et alors on met à jour le dérivé. |
| `game_box/` | **Le matériel de jeu. Porte un `CLAUDE.md` qui dit « THIS DIRECTORY CONTAINS THE SOURCE OF TRUTH ».** Règles transcrites, carte et sa grille d'hexagones, script d'extraction, et `pions/` (inventaire des 127 pions). C'est là que doit lire et écrire le code du jeu. |
| `moteur/` | **Les règles, en Python.** Deux constantes lues au démarrage — la carte (la transcription recouverte par les corrections de `map_fix.json`) et le catalogue des pions (`pions.json`) — et quatre classes : `Hex` (voisinage, coûts de terrain, déplacements), `Pion` (valeurs du carton, camp), `Plateau` (qui occupe quelle case : c'est de là que sortent les zones de contrôle) et `Scenario` (une mise en place lue dans `scenarios/`). Rien de web ici. Voir `moteur/README.md`. |
| `scenarios/` | **Les mises en place, fixées une fois pour toutes**, un fichier JSON par scénario du fascicule. Le fascicule dit « l'armée naine se masse au sud du volcan de Toth » ; le passage de la phrase aux hexagones a été fait à la main, et ce répertoire en garde le résultat. Voir `scenarios/README.md`. |
| `application/` | **Le serveur.** Application Flask (factory `create_app`) qui affiche la carte, la mise en place d'un scénario (le n° 4), et sert les déplacements calculés par `moteur/`. Elle lit `game_box/` et `scenarios/`. Elle écrit à deux endroits : `game_box/map_fix.json`, par la route d'admin `/admin/map_fix`, et **MongoDB** — la partie en cours (positions, phase, registre des combats, et qui tient quel camp), sauvegardée à chaque coup et reprise au chargement de `/`, plus les **joueurs** connus. La base n'est jamais touchée depuis une route : tout passe par un dépôt (`depots.py`, `modeles.py`), et les référentiels restent en fichiers. La partie se joue **à deux, un joueur par camp**, identifiés par **Discord OAuth2** : la carte reste publique, les coups demandent d'être connecté et d'occuper le camp actif, et `/admin/map_fix` est réservée aux comptes de `ADMIN_DISCORD_IDS`. L'authentification n'a coûté **aucune dépendance** (`flask.session` et `urllib`). Voir `application/README.md`. |

`todo.txt` (racine) porte les consignes de travail de l'utilisateur ; il n'est pas versionné.

Les secrets — connexion MongoDB, application Discord, `SECRET_KEY` — vivent dans `.env` à la
racine, non versionné : voir `.env.example`, que `application/config.py` lit une fois au démarrage.
Sans `SECRET_KEY`, l'application refuse de démarrer plutôt que d'en tirer une au hasard.

## Sources et dérivés

**Les sources brutes sont exclues de git, seuls les dérivés sont versionnés.** C'est délibéré :
elles sont volumineuses (28 Mo) et non redistribuables. Un nouveau clone n'aura donc pas
`base_material/` ; retoucher une transcription demande les fichiers locaux.

| Chemin | Rôle | Versionné ? |
| --- | --- | --- |
| `base_material/ave_tenebrae_regles.pdf` | Fascicule de règles scanné, 16 pages | non |
| `base_material/vintageboard-1-ave-tenebrae.html` | Article de blog archivé (« Vintageboard 1 », R-One Chaff, irlboardgames.blogspot.com) ; contient le découpage des planches de pions | non |
| `base_material/images/` | 144 photos de la boîte, de la carte et des planches de pions | non |
| `todo.txt` | Consignes de travail de l'utilisateur | non |
| `game_box/ave_tenebrae_regles.md` | Transcription des règles | **oui** |
| `game_box/map.jpg` | Carte du jeu (10 Mo) | **oui** |
| `game_box/carte.json` | 2280 hexagones, `"q,r,s"` → terrain | **oui** |
| `game_box/carte_details.json` | `"q,r,s"` → tous les éléments de l'hexagone | **oui** |
| `game_box/carte_controle.jpg` | Carte teintée par terrain, pour vérification à l'œil | **oui** |
| `game_box/carte.md` | Documentation de la transcription de la carte | **oui** |
| `game_box/map_fix.json` | Corrections de terrain relevées à l'œil sur `/admin/map_fix`, appliquées par le moteur | **oui** |
| `game_box/extraction_carte.py` | Régénère les trois fichiers ci-dessus depuis `map.jpg` | **oui** |
| `game_box/pions/` | Inventaire des pions + copies renommées | **oui** |
| `scenarios/*.json` | Mises en place fixées, une par scénario | **oui** |

L'exclusion est locale, dans `.git/info/exclude` (pas dans `.gitignore`, qui ne contient que
`.idea/`). Ne pas « corriger » cela en ajoutant les sources à git.

⚠️ **Les motifs d'exclusion sont périmés depuis le déplacement dans `base_material/`.** Ils visent
encore `/images/`, `/ave_tenebrae_regles.pdf`, `/vintageboard-1-ave-tenebrae.html` à la racine.
Résultat : `git add -A` mettrait en index les 146 fichiers de `base_material/` (28 Mo). Vérifier
`git status` avant tout `add` large, et ne jamais faire `git add -A` / `git add .` à l'aveugle ici.

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
  `test_map_fix_navigateur.py`, `test_reprise_navigateur.py`) : c'est là qu'on ouvre une page,
  qu'on clique un pion, qu'on recharge. Pas dans un vrai navigateur ouvert à la main.

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
moteur n'utilise que la bibliothèque standard. Elles sont installées dans le virtualenv pyenv
`tenebrae` que `.python-version` (racine, non versionné) sélectionne automatiquement ; `python3`
suffit.
Le script tourne une dizaine de minutes et prend environ 2 Go de mémoire.

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
faction ou utilité, d'après le découpage donné par l'article de blog.

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
  règles). Ne pas trancher ces points sans source ; les ajouter à cette section si de nouveaux
  doutes apparaissent.
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
commit : attention, « tous les fichiers » inclut aujourd'hui `base_material/` (voir l'avertissement
plus haut).
