"""D'où vient l'identité d'un joueur : de Discord, ou d'un client factice pour les tests.

Le protocole OAuth2 tient en deux allers-retours : un POST de formulaire vers `/oauth2/token`, qui
échange le code à usage unique contre un jeton d'accès, puis un GET porteur de ce jeton vers
`/users/@me`. `urllib.request` les fait très bien. **On n'ajoute donc rien à `requirements.txt`** :
c'est le même parti que `extensions.py`, qui a réécrit l'interface de Flask-MongoEngine plutôt que
d'installer une extension morte. `requests` traîne bien dans le virtualenv, mais tiré par
Playwright — et le serveur ne peut pas dépendre à l'exécution d'un outil de test.

Le fichier ne s'appelle pas `discord.py`, et ce n'est pas un caprice : `app.py` et le `conftest.py`
racine mettent `application/` en tête de `sys.path`, si bien qu'un module de ce nom masquerait pour
tout le processus un éventuel paquet `discord`.

Deux implémentations, choisies par `AUTHENTIFICATION` et accrochées à `application.extensions`
comme le dépôt l'est déjà : la vraie, et une factice qui referme le flux sur notre propre route de
retour. La factice ne court-circuite rien — le `state`, l'échange du code et la lecture de
l'identité se déroulent pour de bon —, elle évite seulement de sortir de la machine.
"""

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import url_for

AUTORISATION = "https://discord.com/oauth2/authorize"
JETON = "https://discord.com/api/oauth2/token"
MOI = "https://discord.com/api/users/@me"
CDN = "https://cdn.discordapp.com"

# Sans lui, `urlopen` attendrait indéfiniment : un Discord injoignable gèlerait la requête.
DELAI = 10

# Tout ce dont le jeu a besoin : un identifiant, un pseudo, un avatar. Pas « email » — le jeu n'en
# ferait rien, et une portée de moins est un consentement de moins à demander et une donnée
# personnelle de moins à garder. Le champ `courriel` du modèle attend, au cas où.
PORTEE = "identify"


class ErreurDiscord(Exception):
    """Discord n'a pas répondu, ou a répondu autre chose que ce qu'on attendait."""


class ClientDiscord:
    """Les trois échanges du flux OAuth2 : l'URL d'autorisation, le jeton, le compte.

    Le secret de l'application ne sort jamais d'ici : il part dans le corps d'un POST vers
    Discord, et rien d'autre dans le projet ne le lit.
    """

    def __init__(self, identifiant, secret, redirection):
        self._identifiant = identifiant
        self._secret = secret
        self._redirection = redirection

    def url_d_autorisation(self, etat):
        """Où envoyer le navigateur pour qu'il demande l'autorisation du joueur."""
        parametres = {"client_id": self._identifiant, "redirect_uri": self._redirection,
                      "response_type": "code", "scope": PORTEE, "state": etat}
        return f"{AUTORISATION}?{urlencode(parametres)}"

    def echanger_le_code(self, code):
        """Le code à usage unique rapporté par le navigateur, contre un jeton d'accès."""
        corps = urlencode({"client_id": self._identifiant, "client_secret": self._secret,
                           "grant_type": "authorization_code", "code": code,
                           "redirect_uri": self._redirection}).encode()
        reponse = self._appeler(JETON, corps=corps)
        try:
            return reponse["access_token"]
        except (KeyError, TypeError) as souci:
            raise ErreurDiscord("Discord n'a pas rendu de jeton d'accès") from souci

    def identite(self, jeton):
        """« /users/@me », ramené au vocabulaire du jeu."""
        moi = self._appeler(MOI, entetes={"Authorization": f"Bearer {jeton}"})
        try:
            return {"discord_id": str(moi["id"]),
                    "pseudo": moi.get("global_name") or moi["username"],
                    "nom_affiche": moi.get("global_name"),
                    "avatar": self.url_de_l_avatar(moi),
                    "courriel": moi.get("email")}
        except (KeyError, TypeError) as souci:
            raise ErreurDiscord("Discord n'a pas rendu de compte lisible") from souci

    @staticmethod
    def url_de_l_avatar(moi):
        """L'avatar du compte, ou celui que Discord attribue d'office aux comptes sans image."""
        if moi.get("avatar"):
            return f"{CDN}/avatars/{moi['id']}/{moi['avatar']}.png?size=64"
        return f"{CDN}/embed/avatars/{(int(moi['id']) >> 22) % 6}.png"

    @staticmethod
    def _appeler(url, corps=None, entetes=None):
        requete = Request(url, data=corps,
                          headers={"Accept": "application/json", **(entetes or {})})
        try:
            with urlopen(requete, timeout=DELAI) as reponse:
                return json.load(reponse)
        except (HTTPError, URLError, ValueError, TimeoutError) as souci:
            raise ErreurDiscord(f"Discord n'a pas répondu : {souci}") from souci


# Le compte que le client factice sert, à défaut d'un autre. L'identifiant est celui que
# `ConfigDeTest` déclare administrateur et que `tests/conftest.py` assied à la table.
IDENTITE_PAR_DEFAUT = {"discord_id": "100000000000000001", "pseudo": "Joueuse d'essai",
                       "nom_affiche": None, "avatar": None, "courriel": None}


class ClientDiscordFactice:
    """Discord sans Discord : le même protocole, sans sortir du processus.

    Tout est dans `url_d_autorisation`, qui ne renvoie pas vers discord.com mais vers **notre
    propre route de retour**. Le navigateur — celui de Playwright comme celui d'un développeur
    sans application déclarée — suit la redirection, revient avec un code et un état, et la route
    de retour déroule alors le vrai code : vérification de l'état, échange du code, lecture de
    l'identité, ouverture de session. Le flux est éprouvé, pas contourné.

    `identite_servie` se remplace en cours de test pour faire venir un second joueur — c'est ainsi
    que deux navigateurs s'assoient chacun à son camp.
    """

    def __init__(self, identite=None):
        self.identite_servie = dict(identite or IDENTITE_PAR_DEFAUT)
        self.codes_echanges = []

    def url_d_autorisation(self, etat):
        return url_for("jeu.retour_de_connexion", code="code-factice", state=etat)

    def echanger_le_code(self, code):
        self.codes_echanges.append(code)
        return f"jeton-de-{code}"

    def identite(self, jeton):
        return dict(self.identite_servie)
