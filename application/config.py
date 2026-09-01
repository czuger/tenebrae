"""La configuration de l'application, en un seul endroit.

Les informations de connexion à MongoDB et les secrets de Discord ne vivent jamais dans le code :
ils sont lus dans `.env` (à la racine du dépôt, non versionné — voir `.env.example`), chargé ici
une seule fois, à l'import du module. `create_app` reçoit une de ces classes et la donne à Flask ;
rien d'autre ne lit l'environnement.

`PERSISTANCE` dit ce qu'on fait de la partie : `mongo` la sauvegarde à chaque coup joué et la
reprend au chargement, `aucune` joue comme avant — tout en mémoire, rien ne survit au serveur.
C'est aussi ce qui permet de jouer sans MongoDB installé.

`AUTHENTIFICATION` dit d'où vient l'identité d'un joueur : de Discord, ou d'un client factice qui
répond tout seul. **Il n'est pas lu dans l'environnement, et c'est délibéré** : une variable de
`.env` qui débranche l'authentification est une porte ouverte qu'une faute de frappe suffit à
laisser béante. Seule `ConfigDeTest` pose « factice », et les tests sont le seul endroit d'où l'on
peut s'en servir.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

RACINE = Path(__file__).resolve().parent.parent

# Une seule lecture de `.env`, au premier import ; les variables déjà posées dans
# l'environnement gardent la main, comme le veut python-dotenv.
load_dotenv(RACINE / ".env")


def _liste(nom):
    """Une variable d'environnement en liste : « 12,34 » → ["12", "34"], l'absence → []."""
    return [element.strip() for element in os.environ.get(nom, "").split(",") if element.strip()]


class Config:
    """La configuration de jeu ordinaire : la partie est sauvegardée dans MongoDB."""

    PERSISTANCE = os.environ.get("PERSISTANCE", "mongo")
    # Le format qu'attend l'extension MongoEngine : tout tient dans l'URI.
    MONGODB_SETTINGS = {"host": os.environ.get("MONGODB_URI",
                                               "mongodb://localhost:27017/tenebrae")}

    # --- La session ---
    #
    # Ce qui signe le cookie de session. Absente, `create_app` refuse de démarrer plutôt que d'en
    # tirer une au hasard : une clé qui change à chaque lancement déconnecterait tout le monde à
    # chaque redémarrage, et personne ne verrait pourquoi.
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Le JavaScript n'a rien à lire dans le cookie : tout ce qu'il sait du joueur lui vient du
    # gabarit.
    SESSION_COOKIE_HTTPONLY = True
    # « Lax » et non « Strict » : le retour de Discord est une navigation de premier niveau venue
    # d'un autre site. « Strict » retiendrait le cookie, la session paraîtrait vide, l'état de
    # l'OAuth serait introuvable — et le flux ne pourrait jamais aboutir.
    SESSION_COOKIE_SAMESITE = "Lax"
    # En développement on parle http://127.0.0.1, où un cookie « Secure » ne serait pas posé du
    # tout : la variable est à « non » par défaut, et passe à « oui » derrière HTTPS.
    SESSION_COOKIE_SECURE = os.environ.get("COOKIE_SECURISE", "non") == "oui"
    # Le cookie n'est réécrit que par les réponses qui ont **modifié** la session : ouvrir ou
    # fermer une connexion, poser ou reprendre l'état de l'OAuth2. Par défaut Flask le réécrit à
    # chaque réponse dès que la session est permanente — donc dès qu'elle porte un joueur —, et
    # c'est ce qui cassait la connexion : une requête partie avec l'ancienne session avant
    # `/connexion` — un sondage de repli, une reconnexion du flux depuis un autre onglet — répond
    # après, et son cookie, sans l'état, écrase celui que `/connexion` venait de poser. Le retour
    # de Discord ne trouvait plus rien à quoi se comparer. Ce qu'on y perd : l'expiration du
    # cookie (`PERMANENT_SESSION_LIFETIME`, 31 jours) court depuis la connexion et non depuis la
    # dernière visite — on se reconnecte une fois par mois, c'est tout.
    SESSION_REFRESH_EACH_REQUEST = False

    # --- L'identité des joueurs ---
    AUTHENTIFICATION = "discord"
    DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID")
    DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET")
    # Discord compare cette URI à celle du Developer Portal **caractère par caractère** :
    # « localhost » n'y est pas « 127.0.0.1 », et un « / » de trop suffit à faire échouer
    # l'échange. Elle vient de la configuration et jamais de `request.host`, qu'un en-tête forgé
    # déplacerait.
    DISCORD_REDIRECT_URI = os.environ.get("DISCORD_REDIRECT_URI",
                                          "http://127.0.0.1:5000/connexion/retour")

    # Qui peut corriger la carte (`/admin/map_fix`), par identifiant Discord. Une liste vide
    # n'admet personne : une variable de sécurité dont l'absence ouvrirait tout serait un piège.
    # Le refus dit comment se déclarer.
    ADMINISTRATEURS = _liste("ADMIN_DISCORD_IDS")


class ConfigDeTest(Config):
    """La configuration des tests : pas de MongoDB — le dépôt nul ne sauvegarde rien,
    et les routes gardent leur comportement d'avant persistance."""

    TESTING = True
    PERSISTANCE = "aucune"

    # Discord sans Discord : le client factice referme le flux sur notre propre route de retour
    # (voir `client_discord.py`). Rien ne sort de la machine, et le flux complet est éprouvé.
    AUTHENTIFICATION = "factice"

    # Fixée, et n'ayant jamais servi ailleurs : la suite ne dépend pas d'un `.env` local.
    SECRET_KEY = "cle-de-test-sans-valeur"

    # Le joueur de test corrige la carte comme il joue : c'est `tests/conftest.py` qui pose cet
    # identifiant en session.
    ADMINISTRATEURS = ["100000000000000001"]
