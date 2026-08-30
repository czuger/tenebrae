"""Met le dépôt et l'application sur `sys.path` : ni l'un ni l'autre n'est un paquet installé.

Ce fichier permet de lancer toute la suite depuis la racine : `python3 -m pytest`.
"""

import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent

for chemin in (RACINE, RACINE / "application"):
    if str(chemin) not in sys.path:
        sys.path.insert(0, str(chemin))
