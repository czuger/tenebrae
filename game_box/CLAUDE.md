# THIS DIRECTORY CONTAINS THE SOURCE OF TRUTH

Le **matériel de jeu** : les règles transcrites, la carte et sa grille d'hexagones, l'inventaire
des pions et leurs valeurs. C'est ici que le code lit — `moteur/` y prend la carte
(`carte_details.json` + `map_fix.json`) et le catalogue (`pions/pions.json`) au démarrage — et
c'est ici qu'il faut chercher une donnée du jeu, jamais dans `base_material/`.

Avant de toucher aux données :

- **La carte** — lire `carte.md` d'abord. `carte.json` et `carte_details.json` sortent
  d'`extraction_carte.py` et ne s'éditent pas à la main : une correction de terrain se relève dans
  `map_fix.json` par `/admin/map_fix`, une correction de site se fait dans le script.
- **Les règles** — `ave_tenebrae_regles.md` porte ses conventions de transcription dans son
  propre en-tête (texte seul, tableaux Markdown, orthographe modernisée).
- **Les pions** — `pions/README.md` est l'index maître ; toute copie ajoutée y est notée avec sa
  photo d'origine.

Dans les trois cas, **les incertitudes sont conservées, pas résolues** : chaque fichier a sa
section de réserves, et un doute nouveau s'y ajoute plutôt que de se trancher sans source.
