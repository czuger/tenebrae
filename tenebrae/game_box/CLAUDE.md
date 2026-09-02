# THIS DIRECTORY CONTAINS THE SOURCE OF TRUTH

The **game material**: the transcribed rules, the map and its hexagon grid, the counter inventory
and their values. This is where the code reads — `tenebrae/engine/` takes the map
(`carte_details.json` + `map_fix.json`) and the catalogue (`pions/pions.json`) from here at start-up
— and this is where a game datum is to be looked for, never in `material/base_material/`.

The file names and the vocabulary here are French, and stay that way: this is 1986 material,
transcribed as it stands. Only the code around it is English.

Before touching the data:

- **The map** — read `map.md` first. `carte.json` and `carte_details.json` come out of
  `extract_map.py` and are not edited by hand: a terrain fix is recorded in `map_fix.json` through
  `/admin/map_fix`, a site fix is made in the script.
- **The rules** — `ave_tenebrae_regles.md` carries its transcription conventions in its own header
  (text only, Markdown tables, modernised spelling).
- **The counters** — `pions/README.md` is the master index; every copy added is noted there with
  its source photograph.

In all three cases, **uncertainties are kept, not resolved**: each file has its own caveats
section, and a new doubt is added to it rather than settled without a source.
