"""Le dépôt des joueurs : les comptes connus du jeu, en base ou en mémoire.

Les deux dépôts rendent des **dicts** — `{discord_id, pseudo, nom_affiche, avatar, courriel}` —
et jamais un document : c'est sous cette forme que le joueur circule jusqu'aux routes et jusqu'au
gabarit, et c'est elle que l'entité de connexion de l'application
(`application/models/connexion.py`) reçoit quand elle demande « qui est en session ».
"""

from datetime import datetime, timezone


class DepotDeJoueursMongo:
    """Les comptes Discord connus, dans MongoDB — un document par joueur."""

    def __init__(self):
        # L'import est fait ici et pas en tête : construire le dépôt de mémoire ne doit pas
        # demander mongoengine, que les tests sans base n'ont pas à charger.
        from moteur.models.joueur import Joueur
        self._Joueur = Joueur

    def enregistrer(self, identite):
        """Crée le joueur ou met à jour ce que Discord vient de dire de lui ; rend son dict.

        Lecture puis écriture, plutôt qu'un `upsert` : mongomock rend mal celui de mongoengine,
        la table ne compte que deux joueurs, et l'index unique sur `discord_id` reste le filet.
        """
        joueur = self._Joueur.objects(discord_id=identite["discord_id"]).first()
        if joueur is None:
            joueur = self._Joueur(discord_id=identite["discord_id"], cree_le=self._maintenant())
        joueur.pseudo = identite["pseudo"]
        joueur.nom_affiche = identite.get("nom_affiche")
        joueur.avatar = identite.get("avatar")
        joueur.courriel = identite.get("courriel")
        joueur.derniere_connexion_le = self._maintenant()
        joueur.save()
        return self._en_dict(joueur)

    def par_discord_id(self, discord_id):
        """Le joueur de cet identifiant, ou `None` s'il n'en est plus connu aucun."""
        joueur = self._Joueur.objects(discord_id=discord_id).first()
        return self._en_dict(joueur) if joueur else None

    @staticmethod
    def _en_dict(joueur):
        """Ce que les routes reçoivent : ni document, ni dates — personne n'en a l'usage."""
        return {"discord_id": joueur.discord_id, "pseudo": joueur.pseudo,
                "nom_affiche": joueur.nom_affiche, "avatar": joueur.avatar,
                "courriel": joueur.courriel}

    @staticmethod
    def _maintenant():
        return datetime.now(timezone.utc)


class DepotDeJoueursEnMemoire:
    """Les joueurs dans un dictionnaire, le temps du processus.

    Ce n'est pas un dépôt *nul*, et la nuance compte : son homologue pour la partie ne retient
    rien parce que l'état de jeu a déjà un domicile en mémoire, les module-globaux de `app.py`.
    Un joueur n'en a aucun. Ne rien retenir ici rendrait la connexion impossible, et le jeu avec
    elle. Il tient donc la promesse de `PERSISTANCE=aucune` sans interdire de jouer : les comptes
    valent pour ce lancement, et disparaissent avec lui.
    """

    def __init__(self):
        self._par_discord_id = {}

    def enregistrer(self, identite):
        joueur = {"discord_id": identite["discord_id"], "pseudo": identite["pseudo"],
                  "nom_affiche": identite.get("nom_affiche"),
                  "avatar": identite.get("avatar"), "courriel": identite.get("courriel")}
        self._par_discord_id[joueur["discord_id"]] = joueur
        return dict(joueur)

    def par_discord_id(self, discord_id):
        joueur = self._par_discord_id.get(discord_id)
        return dict(joueur) if joueur else None
