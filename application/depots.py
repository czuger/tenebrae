"""La couche d'accès à la partie sauvegardée : les routes ne parlent qu'à un dépôt.

Un dépôt échange des **dicts d'état** — le format de `photographier_la_partie()` dans `app.py` :
`{scenario, placement, camp_actif, type_de_phase, numero_de_tour, attaquants_engages,
cibles_engagees, places}` — jamais un Document MongoEngine. C'est ce qui tient Mongo hors des
routes : `app.py` n'importe ni `modeles` ni `mongoengine`, il appelle `charger`, `sauvegarder` et
`nouvelle_partie`, point.

Deux dépôts par sujet : le vrai, sur MongoDB, et son homologue sans base, que la configuration de
test branche. Pour la partie, celui-là ne retient **rien** — l'état de jeu vit déjà dans les
module-globaux de `app.py`, il n'y a qu'à ne pas le doubler. Pour les joueurs, il retient **en
mémoire** : un joueur n'a pas d'autre domicile, et un dépôt qui ne garderait rien n'appauvrirait
pas le service, il l'interdirait — personne ne pourrait ouvrir de session, donc prendre place,
donc jouer. Les deux tiennent la même promesse de `PERSISTANCE=aucune` : rien ne survit au
serveur.
"""

from datetime import datetime, timezone


class DepotDePartieMongo:
    """La partie courante dans MongoDB : un document par partie, la plus récente fait foi."""

    def __init__(self):
        # L'import est fait ici et pas en tête : construire un dépôt nul ne doit pas
        # demander mongoengine — les tests sans Mongo importent ce module, eux aussi.
        from modeles import Partie
        self._Partie = Partie

    def _la_plus_recente(self):
        return self._Partie.objects.first()  # `ordering` du modèle : la plus récente d'abord

    def charger(self):
        """L'état de la partie la plus récente, ou `None` s'il n'y a encore rien en base."""
        partie = self._la_plus_recente()
        if partie is None:
            return None
        return {"scenario": partie.scenario,
                "placement": dict(partie.placement),
                "camp_actif": partie.camp_actif,
                "type_de_phase": partie.type_de_phase,
                "numero_de_tour": partie.numero_de_tour,
                "attaquants_engages": list(partie.attaquants_engages),
                "cibles_engagees": list(partie.cibles_engagees),
                "places": dict(partie.places)}

    def sauvegarder(self, etat):
        """Écrit l'état dans la partie la plus récente — la crée si la base est vide."""
        partie = self._la_plus_recente()
        if partie is None:
            return self.nouvelle_partie(etat)
        self._remplir(partie, etat).save()

    def nouvelle_partie(self, etat):
        """Ouvre une nouvelle partie ; les précédentes restent en base, en guise d'historique."""
        partie = self._Partie(creee_le=self._maintenant())
        self._remplir(partie, etat).save()

    def _remplir(self, partie, etat):
        partie.scenario = etat["scenario"]
        partie.placement = etat["placement"]
        partie.camp_actif = etat["camp_actif"]
        partie.type_de_phase = etat["type_de_phase"]
        partie.numero_de_tour = etat["numero_de_tour"]
        partie.attaquants_engages = etat["attaquants_engages"]
        partie.cibles_engagees = etat["cibles_engagees"]
        # Les places sont réécrites comme le reste. C'est pour cela qu'elles voyagent dans le
        # dict d'état plutôt que dans des méthodes à part : `_remplir` réécrit toute la partie à
        # chaque coup, et des places tenues à côté seraient effacées à chaque sauvegarde.
        partie.places = etat.get("places") or {}
        partie.modifiee_le = self._maintenant()
        return partie

    @staticmethod
    def _maintenant():
        return datetime.now(timezone.utc)


class DepotDePartieNul:
    """Le dépôt qui ne retient rien : `charger` ne trouve jamais de partie, sauvegarder ne
    fait rien. Branché par la configuration de test — et par `PERSISTANCE=aucune` —, il rend
    à l'application son comportement d'avant : chaque chargement de « / » repart du scénario."""

    def charger(self):
        return None

    def sauvegarder(self, etat):
        pass

    def nouvelle_partie(self, etat):
        pass


class DepotDeJoueursMongo:
    """Les comptes Discord connus, dans MongoDB — un document par joueur."""

    def __init__(self):
        # Même raison qu'au-dessus : construire le dépôt de mémoire ne doit pas demander
        # mongoengine, que les tests sans base n'ont pas à charger.
        from modeles import Joueur
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
