# La carte d'*Ave Tenebrae* en JSON

Transcription de `map.jpg` (source non versionnée, 6173 × 5102 px) en une grille d'hexagones
exploitable par un programme. Le fascicule de règles indique que **chaque hexagone représente
environ 1 km**.

## Fichiers produits

| Fichier | Contenu |
| --- | --- |
| `carte.json` | dict `"q,r,s"` → terrain principal (un seul terrain par hexagone) |
| `carte_details.json` | dict `"q,r,s"` → liste de **tous** les éléments présents sur l'hexagone, le terrain principal en tête |
| `carte_controle.jpg` | `map.jpg` au tiers, avec chaque hexagone teinté de la couleur de son terrain — sert à vérifier le classement à l'œil |
| `extraction_carte.py` | Script qui régénère les trois précédents à partir de `map.jpg` |

`carte_details.json` existe parce que 421 hexagones portent plusieurs éléments (une route qui
traverse un bois, une rivière qui longe une forêt, un village posé sur une route…). `carte.json`
n'en garde qu'un ; `carte_details.json` ne perd rien.

## Système de coordonnées

Grille **flat-top** (hexagones à sommets gauche/droite, arêtes horizontales en haut et en bas),
disposée en colonnes, les colonnes impaires décalées vers le bas : c'est le décalage **odd-q**
de <https://www.redblobgames.com/grids/hexagons/#coordinates>.

- **57 colonnes × 40 lignes = 2280 hexagones**, tous présents dans les deux fichiers.
- `col` va de 0 (bord ouest) à 56 (bord est), `row` de 0 (bord nord) à 39 (bord sud).
- Les clés JSON sont les coordonnées **cubiques** `"q,r,s"` avec `q + r + s = 0` :

```
q = col
r = row - (col - (col & 1)) / 2
s = -q - r
```

Coin nord-ouest `(col 0, row 0)` → `"0,0,0"`. Coin sud-est `(col 56, row 39)` → `"56,11,-67"`.

### Géométrie relevée sur le scan

Utile pour repositionner la grille sur `map.jpg` (centres en pixels, origine en haut à gauche) :

```
centre(col, row) = O + A · (q, r)
O = (76.355, 70.511)
A = [[107.5724, -0.3407],
     [ 62.8901, 125.6828]]
```

demi-largeur d'hexagone ≈ 71,7 px ; demi-hauteur ≈ 72,6 px (sommet à sommet ≈ 143 px). Le très léger
terme non diagonal (−0,34) absorbe la rotation résiduelle du scan ; la grille ainsi calée reste juste
d'un bord à l'autre de la carte.

## Vocabulaire des terrains

16 valeurs. Les six premières correspondent aux lignes du *Tableau des terrains* du fascicule,
les autres sont des lieux construits dessinés sur la carte.

| Terrain | Hexagones | Correspondance dans les règles |
| --- | --- | --- |
| `plaine` | 1399 | — (terrain par défaut) |
| `bois` | 422 | **BOIS** — 2 points sauf Elfes |
| `montagne` | 128 | **MONTAGNE** — infranchissable sauf par colline, route ou air |
| `lac` | 99 | **LACS** — infranchissables sauf par eau et air |
| `chemin` | 63 | **CHEMINS** — × 2 |
| `route` | 49 | **ROUTES** — × 3 |
| `riviere` | 30 | **RIVIÈRES** — infranchissables sauf ponts, air, créatures aquatiques |
| `village` | 22 | **VILLAGES** — défense × 2 |
| `colline` | 20 | **COLLINES** — 2 points sauf élémentaire Terre (voir réserves) |
| `faille` | 15 | **FAILLE** — infranchissable sauf par air (Faille de Tsaroth) |
| `ville` | 12 | Morgenstern, capitale de l'Empire — murailles, défense × 3 |
| `ruines` | 11 | **RUINES** — × 2, défense × 2 |
| `chateau` | 4 | Château des Marches d'Yzent — **FORTS** / **MURAILLES** |
| `fort` | 4 | **FORTS** — défense × 3, pas de résultats **DR** |
| `tour` | 1 | Tour d'Orvarth |
| `ile` | 1 | Île du Crâne, au milieu du Lac Noir |

## Règle de priorité

Quand plusieurs éléments se superposent, `carte.json` retient le premier de cette liste :

```
ville > fort > chateau > tour > ruines > village > ile
      > lac > montagne > colline > bois > faille > riviere > route > chemin > plaine
```

Le terrain naturel l'emporte donc sur les voies : la route noire qui traverse le massif du nord
donne `montagne`, un chemin en forêt donne `bois`. Les 42 hexagones « route » et 17 hexagones
« chemin » ainsi masqués restent listés dans `carte_details.json`.

## Lieux nommés

Coordonnées en `col,row` (odd-q) ; ajouter la conversion ci-dessus pour retrouver la clé JSON.

### Villages (22)

| col,row | Nom | col,row | Nom |
| --- | --- | --- | --- |
| 2,9 | Hameau aux loups | 42,36 | Lorift |
| 3,14 | Reiss | 45,30 | Denrift |
| 6,11 | Hameaux des âmes | 46,28 | Aurilt |
| 6,22 | Sorrow | 48,38 | Trillift |
| 6,25 | Malfroy | 50,34 | Dendrill |
| 10,14 | Ulmar | 52,27 | Voloors |
| 12,17 | Hurlewind | 53,8 | Sandhardt (lecture incertaine) |
| 15,31 | Ghalmaz-Ar | 54,31 | Virlilt |
| 2,30 | Stern | 56,12 | Gròsht |
| 9,39 | New Ark | 28,30 | Dawn |
| 37,34 | Angle | 38,4 | Helden |

### Places fortes et sites

| Terrain | col,row | Nom |
| --- | --- | --- |
| `ville` | 2,33 · 3,33 · 4,33 · 2,34 · 3,34 · 4,34 · 2,35 · 3,35 · 4,35 · 2,36 · 3,36 · 4,36 | **Morgenstern**, capitale de l'Empire (12 hexagones, ceinturée de douves) |
| `chateau` | 1,2 · 2,1 · 2,2 · 3,1 | **Château des Marches d'Yzent** (muraille et ses portes) |
| `fort` | 16,20 | **Krak des trois frontières** |
| `fort` | 32,20 | **Marche du Lac** |
| `fort` | 48,20 | **Montfaucon** |
| `fort` | 4,16 | Redoute fortifiée sur la route du Val de Froy (sans nom sur la carte) |
| `tour` | 27,2 | **Tour d'Orvarth**, au sommet du massif nord |
| `ile` | 52,4 | **Île du Crâne**, au milieu du Lac Noir |
| `ruines` | 0,1 · 0,2 | **Ruines d'Yzent** |
| `ruines` | 28,3 · 29,3 · 30,3 · 31,3 · 28,4 · 29,4 · 30,4 | **Ruines de Ghaarth** (d'où surgissent les morts-vivants) |
| `ruines` | 33,2 · 34,2 | Ruines du **Seuil des brumes** |
| `faille` | 9,2 · 10,2 · 10,3 · 10,4 · 11,4 · 11,5 · 12,5 · 12,6 · 13,6 · 13,7 · 14,7 · 14,8 · 15,8 · 16,9 · 17,9 | **Faille de Tsaroth** |

Étendues d'eau : **Lac Noir** au nord-est (avec l'Île du Crâne), **Lac d'Aurore** au sud-est, plus
les douves de Morgenstern. La **Forêt elfique** occupe l'angle sud-est.

## Régénérer les fichiers

```
python3 extraction_carte.py
```

Dépendances : `Pillow`, `numpy`, `scipy`. Il faut `map.jpg` dans le répertoire courant — la source
n'est pas versionnée. Comptez une dizaine de minutes et environ 2 Go de mémoire ; le script
réécrit `carte.json`, `carte_details.json` et `carte_controle.jpg`.

Les réglages numériques sont calés sur ce scan précis et n'ont pas vocation à être génériques.
Les lieux construits et la Faille de Tsaroth ne sont pas détectés automatiquement : ils sont
relevés à la main en tête de script (`MORGENSTERN`, `FORTS`, `CHATEAUX`, `TOURS`, `ILES`,
`RUINES`, `VILLAGES`, `FAILLE`) — c'est là qu'il faut corriger un site, pas dans le JSON.

## Méthode

Classement automatique, pixel par pixel, puis agrégation par hexagone :

1. **Calage de la grille** — les centres d'hexagones sont détectés comme maxima de la transformée
   de distance au réseau de lignes blanches, puis un réseau affine leur est ajusté aux moindres
   carrés (2101 centres retenus). Chaque pixel est ensuite attribué à un hexagone.
2. **Eau** — pixels bleus ; ouverture morphologique de rayon 16 px pour séparer les `lac` des
   `riviere`.
3. **Relief, voies et bâti** — pixels « chauds » (R > V), fermés à travers les seules lignes de
   grille ; une ouverture de rayon 20 px isole les massifs (`montagne`), les composantes allongées
   restantes donnent `route` (épaisseur ≥ 13 px) et `chemin`, le reste (blocs compacts) donne les
   symboles de bâti.
4. **Bois** — deux détecteurs réunis, parce que le scan est fortement vignetté et que les forêts
   n'ont pas la même teinte à gauche et à droite de la carte : (a) teinte HSV > 93° ; (b) écart de
   « jaunité » (V − B) au niveau local de la plaine, estimé par un fond lissé recalculé
   itérativement en excluant les forêts.
5. **Lieux construits** — les 64 amas de symboles et les 30 petites composantes brunes isolées ont
   été **relus un à un sur le scan** ; les étiquettes gothiques ont servi à nommer chaque site et à
   écarter les faux positifs (textes, lignes de frontière en pointillés, liseré de la carte).

Seuils par hexagone : `lac` ≥ 40 %, `montagne` ≥ 45 %, `colline` 15–45 %, `bois` ≥ 40 %,
`riviere` ≥ 7 %, `route` ≥ 6 %, `chemin` ≥ 5 %. `carte_details.json` utilise des seuils plus bas
(12 %, 45 %, 15 %, 18 %, 4 %, 3,5 %, 3,5 %) pour signaler tout ce qui affleure.

## Réserves sur la transcription

Les erreurs relevées à l'œil depuis, hexagone par hexagone, ne sont **pas corrigées ici** : elles
s'écrivent dans `map_fix.json` (`« q,r,s » → terrain`, les seules cases corrigées), par la route
d'admin `/admin/map_fix` de l'application. `carte.json` et `carte_details.json` restent ce que le
script produit : c'est le moteur qui pose les corrections par-dessus, à son démarrage, et le jeu
se joue sur le résultat (voir `moteur/README.md`). Reverser ces corrections dans
`extraction_carte.py` reste à faire — d'ici là, une correction ne peut que remplacer le terrain
principal d'un hexagone, jamais retirer une route ou un chemin détecté à tort.

- **Les collines ne sont pas dessinées sur la carte.** Le fascicule dit que « l'accès aux montagnes
  nécessite le passage par les cases collines qui les bordent », mais aucune couleur ne les
  distingue : les massifs passent du brun au vert d'un hexagone à l'autre. Les 20 hexagones
  `colline` sont une **interprétation** — ceux dont 15 à 45 % de la surface est en relief. Avec
  cette lecture, 58 des 128 hexagones `montagne` sont bordés d'une colline, d'une route ou d'un
  chemin ; les 70 autres restent inaccessibles au sol. À trancher au moment d'écrire les règles de
  mouvement.
- **Rivières, ponts et murailles sont traités comme des terrains d'hexagone**, alors que les règles
  en font des éléments de *côté* d'hexagone (« infranchissables sauf par ponts »). Les ponts,
  notamment celui qui donne accès à Morgenstern, ne sont pas relevés séparément.
- **La distinction route / chemin repose sur l'épaisseur du trait** (seuil 13 px). Elle est nette
  pour les grands axes du sud, plus incertaine sur le réseau du nord, entièrement classé `chemin`.
- **Les fortifications de la route noire** (autour de 21,3 → 24,4) sont dessinées comme des
  élargissements de la route, sans symbole propre : elles ressortent en `route`, pas en `fort`.
- **Trois villages portent un symbole différent des autres** — Hurlewind (12,17), Aurilt (46,28) et
  Ghalmaz-Ar (15,31) ont un plan fermé, proche de celui des kraks. Le fascicule distingue
  « villes, villages ou citadelles » (3 unités empilables) sans que la carte donne de légende. Tous
  sont classés `village`.
- **L'étendue exacte des ruines de Ghaarth est approximative** : le champ de gravats se prolonge en
  gravats épars vers 28,3 · 31,2 · 32,2 · 33,1 · 34,1 · 35,1, sans limite franche. Seuls les
  hexagones nettement couverts ont été retenus.
- **Le nom du village 53,8 (« Sandhardt » ?) n'est pas lisible avec certitude** sur le scan.
- Les hexagones du bord de carte (colonne 0, colonne 56, ligne 0, ligne 39) sont partiellement
  couverts par le liseré brun de la carte ; leur classement s'appuie sur la seule partie visible.
