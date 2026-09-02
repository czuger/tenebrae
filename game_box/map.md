# The *Ave Tenebrae* map, in JSON

Transcription of `map.jpg` (6173 × 5102 px) into a hexagon grid a program can use. The rules
booklet states that **each hexagon represents about 1 km**.

The terrain vocabulary and the produced file names are French: they are the game's data, read as
they stand by the engine. Only the code around them is English.

## Files produced

| File | Contents |
| --- | --- |
| `carte.json` | dict `"q,r,s"` → main terrain (a single terrain per hexagon) |
| `carte_details.json` | dict `"q,r,s"` → list of **every** element present on the hexagon, main terrain first |
| `carte_controle.jpg` | `map.jpg` at a third of its size, with each hexagon tinted with the colour of its terrain — used to check the classification by eye |
| `extract_map.py` | The script that regenerates the three above from `map.jpg` |

`carte_details.json` exists because 421 hexagons carry several elements (a road crossing a wood, a
river running along a forest, a village sitting on a road, …). `carte.json` keeps only one;
`carte_details.json` loses nothing.

## Coordinate system

A **flat-top** grid (hexagons with left/right vertices, horizontal edges top and bottom), laid out
in columns, the odd columns offset downwards: that is the **odd-q** offset of
<https://www.redblobgames.com/grids/hexagons/#coordinates>.

- **57 columns × 40 rows = 2280 hexagons**, all present in both files.
- `col` runs from 0 (western edge) to 56 (eastern edge), `row` from 0 (northern edge) to 39
  (southern edge).
- The JSON keys are the **cube** coordinates `"q,r,s"` with `q + r + s = 0`:

```
q = col
r = row - (col - (col & 1)) / 2
s = -q - r
```

North-west corner `(col 0, row 0)` → `"0,0,0"`. South-east corner `(col 56, row 39)` →
`"56,11,-67"`.

### Geometry recorded on the scan

Useful for repositioning the grid on `map.jpg` (centres in pixels, origin top left):

```
centre(col, row) = O + A . (q, r)
O = (76.355, 70.511)
A = [[107.5724, -0.3407],
     [ 62.8901, 125.6828]]
```

hexagon half-width ≈ 71.7 px; half-height ≈ 72.6 px (vertex to vertex ≈ 143 px). The very slight
off-diagonal term (−0.34) absorbs the scan's residual rotation; the grid aligned this way stays
correct from one edge of the map to the other.

## Terrain vocabulary

16 values. The first six correspond to the rows of the booklet's *Tableau des terrains*, the others
are built places drawn on the map.

| Terrain | Hexagons | Correspondence in the rules |
| --- | --- | --- |
| `plaine` | 1399 | — (default terrain) |
| `bois` | 422 | **BOIS** — 2 points except Elves |
| `montagne` | 128 | **MONTAGNE** — impassable except through a hill, a road or the air |
| `lac` | 99 | **LACS** — impassable except by water and air |
| `chemin` | 63 | **CHEMINS** — × 2 |
| `route` | 49 | **ROUTES** — × 3 |
| `riviere` | 30 | **RIVIÈRES** — impassable except at bridges, by air, by aquatic creatures |
| `village` | 22 | **VILLAGES** — defence × 2 |
| `colline` | 20 | **COLLINES** — 2 points except Earth elemental (see caveats) |
| `faille` | 15 | **FAILLE** — impassable except by air (the Rift of Tsaroth) |
| `ville` | 12 | Morgenstern, capital of the Empire — walls, defence × 3 |
| `ruines` | 11 | **RUINES** — × 2, defence × 2 |
| `chateau` | 4 | Château des Marches d'Yzent — **FORTS** / **MURAILLES** |
| `fort` | 4 | **FORTS** — defence × 3, no **DR** results |
| `tour` | 1 | Tour d'Orvarth |
| `ile` | 1 | Île du Crâne, in the middle of the Lac Noir |

## Priority rule

When several elements overlap, `carte.json` keeps the first of this list:

```
ville > fort > chateau > tour > ruines > village > ile
      > lac > montagne > colline > bois > faille > riviere > route > chemin > plaine
```

Natural terrain therefore prevails over ways: the black road crossing the northern massif gives
`montagne`, a path in a forest gives `bois`. The 42 "route" and 17 "chemin" hexagons hidden that
way remain listed in `carte_details.json`.

## Named places

Coordinates in `col,row` (odd-q); apply the conversion above to find the JSON key.

### Villages (22)

| col,row | Name | col,row | Name |
| --- | --- | --- | --- |
| 2,9 | Hameau aux loups | 42,36 | Lorift |
| 3,14 | Reiss | 45,30 | Denrift |
| 6,11 | Hameaux des âmes | 46,28 | Aurilt |
| 6,22 | Sorrow | 48,38 | Trillift |
| 6,25 | Malfroy | 50,34 | Dendrill |
| 10,14 | Ulmar | 52,27 | Voloors |
| 12,17 | Hurlewind | 53,8 | Sandhardt (uncertain reading) |
| 15,31 | Ghalmaz-Ar | 54,31 | Virlilt |
| 2,30 | Stern | 56,12 | Gròsht |
| 9,39 | New Ark | 28,30 | Dawn |
| 37,34 | Angle | 38,4 | Helden |

### Strongholds and sites

| Terrain | col,row | Name |
| --- | --- | --- |
| `ville` | 2,33 · 3,33 · 4,33 · 2,34 · 3,34 · 4,34 · 2,35 · 3,35 · 4,35 · 2,36 · 3,36 · 4,36 | **Morgenstern**, capital of the Empire (12 hexagons, ringed by a moat) |
| `chateau` | 1,2 · 2,1 · 2,2 · 3,1 | **Château des Marches d'Yzent** (the wall and its gates) |
| `fort` | 16,20 | **Krak des trois frontières** |
| `fort` | 32,20 | **Marche du Lac** |
| `fort` | 48,20 | **Montfaucon** |
| `fort` | 4,16 | A fortified redoubt on the road of the Val de Froy (unnamed on the map) |
| `tour` | 27,2 | **Tour d'Orvarth**, at the summit of the northern massif |
| `ile` | 52,4 | **Île du Crâne**, in the middle of the Lac Noir |
| `ruines` | 0,1 · 0,2 | **Ruines d'Yzent** |
| `ruines` | 28,3 · 29,3 · 30,3 · 31,3 · 28,4 · 29,4 · 30,4 | **Ruines de Ghaarth** (whence the undead surge) |
| `ruines` | 33,2 · 34,2 | Ruins of the **Seuil des brumes** |
| `faille` | 9,2 · 10,2 · 10,3 · 10,4 · 11,4 · 11,5 · 12,5 · 12,6 · 13,6 · 13,7 · 14,7 · 14,8 · 15,8 · 16,9 · 17,9 | **Faille de Tsaroth** |

Bodies of water: the **Lac Noir** in the north-east (with the Île du Crâne), the **Lac d'Aurore**
in the south-east, plus Morgenstern's moat. The **Forêt elfique** occupies the south-eastern
corner.

## Regenerating the files

```
python3 extract_map.py
```

Dependencies: `Pillow`, `numpy`, `scipy`. `map.jpg` must be in the current directory. Allow about
ten minutes and some 2 GB of memory; the script rewrites `carte.json`, `carte_details.json` and
`carte_controle.jpg`.

The numeric settings are tuned to this precise scan and are not meant to be generic. The built
places and the Rift of Tsaroth are not detected automatically: they are recorded by hand at the
head of the script (`MORGENSTERN`, `FORTS`, `CASTLES`, `TOWERS`, `ISLANDS`, `RUINS`, `VILLAGES`,
`RIFT`) — that is where a site must be corrected, not in the JSON.

## Method

Automatic classification, pixel by pixel, then aggregation per hexagon:

1. **Grid alignment** — hexagon centres are detected as maxima of the distance transform to the
   network of white lines, then an affine lattice is fitted to them by least squares (2101 centres
   retained). Each pixel is then assigned to a hexagon.
2. **Water** — blue pixels; a morphological opening of radius 16 px to separate `lac` from
   `riviere`.
3. **Relief, ways and buildings** — "warm" pixels (R > G), closed across the grid lines only; an
   opening of radius 20 px isolates the massifs (`montagne`), the remaining elongated components
   give `route` (thickness ≥ 13 px) and `chemin`, the rest (compact blocks) gives the building
   symbols.
4. **Woods** — two detectors combined, because the scan is heavily vignetted and the forests do not
   have the same hue on the left and on the right of the map: (a) HSV hue > 93°; (b) the departure
   in "yellowness" (G − B) from the plain's local level, estimated by a smoothed background
   recomputed iteratively while excluding the forests.
5. **Built places** — the 64 symbol clusters and the 30 isolated small brown components were
   **reread one by one on the scan**; the gothic labels served to name each site and to discard the
   false positives (lettering, dotted border lines, the map's edging).

Thresholds per hexagon: `lac` ≥ 40 %, `montagne` ≥ 45 %, `colline` 15–45 %, `bois` ≥ 40 %,
`riviere` ≥ 7 %, `route` ≥ 6 %, `chemin` ≥ 5 %. `carte_details.json` uses lower thresholds
(12 %, 45 %, 15 %, 18 %, 4 %, 3.5 %, 3.5 %) to report everything that shows.

## Réserves sur la transcription (caveats on the transcription)

The errors noticed by eye since, hexagon by hexagon, are **not corrected here**: they are written
into `map_fix.json` (`"q,r,s" → terrain`, the fixed squares only), through the application's
`/admin/map_fix` route. `carte.json` and `carte_details.json` stay what the script produces: it is
the engine that lays the fixes over them, at start-up, and the game is played on the result (see
`engine/README.md`). Feeding those fixes back into `extract_map.py` remains to be done — until
then, a fix can only replace a hexagon's main terrain, never remove a road or a path detected in
error.

- **The hills are not drawn on the map.** The booklet says that "access to the mountains requires
  passing through the hill squares that border them", but no colour tells them apart: the massifs
  go from brown to green from one hexagon to the next. The 20 `colline` hexagons are an
  **interpretation** — those of which 15 to 45 % of the surface is in relief. On that reading, 58
  of the 128 `montagne` hexagons are bordered by a hill, a road or a path; the other 70 stay
  unreachable on the ground. To be settled when the movement rules are written.
- **Rivers, bridges and walls are treated as hexagon terrains**, whereas the rules make them
  *edge* features ("impassable except at bridges"). The bridges, in particular the one giving
  access to Morgenstern, are not recorded separately.
- **The road / path distinction rests on the thickness of the stroke** (threshold 13 px). It is
  clear-cut for the great southern axes, less certain on the northern network, which is classified
  entirely as `chemin`.
- **The fortifications along the black road** (around 21,3 → 24,4) are drawn as widenings of the
  road, with no symbol of their own: they come out as `route`, not as `fort`.
- **Three villages carry a symbol different from the others** — Hurlewind (12,17), Aurilt (46,28)
  and Ghalmaz-Ar (15,31) have a closed plan, close to that of the kraks. The booklet distinguishes
  "villes, villages ou citadelles" (3 units stackable) without the map giving a legend. All are
  classified `village`.
- **The exact extent of the ruins of Ghaarth is approximate**: the rubble field continues as
  scattered rubble towards 28,3 · 31,2 · 32,2 · 33,1 · 34,1 · 35,1, with no clear boundary. Only
  the clearly covered hexagons were retained.
- **The name of village 53,8 ("Sandhardt"?) cannot be read with certainty** on the scan.
- The hexagons at the edge of the map (column 0, column 56, row 0, row 39) are partly covered by
  the map's brown edging; their classification rests on the visible part alone.
