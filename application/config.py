"""La configuration de l'application, en un seul endroit.

Les informations de connexion à MongoDB ne vivent jamais dans le code : elles sont lues dans
`.env` (à la racine du dépôt, non versionné — voir `.env.example`), chargé ici une seule fois,
à l'import du module. `create_app` reçoit une de ces classes et la donne à Flask ; rien d'autre
ne lit l'environnement.

`PERSISTANCE` dit ce qu'on fait de la partie : `mongo` la sauvegarde à chaque coup joué et la
reprend au chargement, `aucune` joue comme avant — tout en mémoire, rien ne survit au serveur.
C'est aussi ce qui permet de jouer sans MongoDB installé.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent

# Une seule lecture de `.env`, au premier import ; les variables déjà posées dans
# l'environnement gardent la main, comme le veut python-dotenv.
load_dotenv(RACINE / ".env")


class Config:
    """La configuration de jeu ordinaire : la partie est sauvegardée dans MongoDB."""

    PERSISTANCE = os.environ.get("PERSISTANCE", "mongo")
    # Le format qu'attend l'extension MongoEngine : tout tient dans l'URI.
    MONGODB_SETTINGS = {"host": os.environ.get("MONGODB_URI",
                                               "mongodb://localhost:27017/tenebrae")}


class ConfigDeTest(Config):
    """La configuration des tests : pas de MongoDB — le dépôt nul ne sauvegarde rien,
    et les routes gardent leur comportement d'avant persistance."""

    TESTING = True
    PERSISTANCE = "aucune"
