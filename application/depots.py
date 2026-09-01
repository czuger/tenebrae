"""La couche d'accès à la partie sauvegardée : les routes ne parlent qu'à un dépôt.

Un dépôt échange des **dicts d'état** — le format de `photographier_la_partie()` dans `app.py` :
`{scenario, placement, camp_actif, type_de_phase, numero_de_tour, attaquants_engages,
cibles_engagees}` — jamais un Document MongoEngine. C'est ce qui tient Mongo hors des routes :
`app.py` n'importe ni `modeles` ni `mongoengine`, il appelle `charger`, `sauvegarder` et
`nouvelle_partie`, point.

Deux dépôts : le vrai, sur MongoDB, et le nul, qui ne retient rien — c'est lui que la
configuration de test branche, et l'application se comporte alors comme avant la persistance.
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
                "cibles_engagees": list(partie.cibles_engagees)}

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
