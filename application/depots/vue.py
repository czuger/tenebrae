"""Le dépôt des vues : où chaque joueur en était sur la carte, en base ou en mémoire.

Un dépôt échange des **dicts** — `{echelle, x, y, ajustee}` —, jamais un Document MongoEngine :
c'est sous cette forme que la vue arrive du navigateur, qu'elle est rangée, et qu'elle repart au
gabarit. `app.py` n'a donc à connaître ni `models.vue` ni mongoengine.

Les deux dépôts **retiennent** l'un comme l'autre, comme ceux des joueurs et non comme celui de
la partie : une vue n'a pas d'autre domicile en mémoire — il n'y a pas de module-global qui la
tienne —, et un dépôt qui ne retiendrait rien rendrait la fonction inopérante au lieu de la
rendre volatile.
"""

from datetime import datetime, timezone

# Ce qu'une vue porte, et rien d'autre. Le navigateur peut en envoyer davantage : il ne sera pas
# rangé.
CHAMPS = ("echelle", "x", "y", "ajustee")


class DepotDeVuesMongo:
    """La vue de chaque joueur dans MongoDB : un document par joueur, écrasé à chaque réglage."""

    def __init__(self):
        # L'import est fait ici et pas en tête : construire le dépôt de mémoire ne doit pas
        # demander mongoengine, que les tests sans base n'ont pas à charger.
        from models.vue import Vue
        self._Vue = Vue

    def par_discord_id(self, discord_id):
        """La vue de ce joueur, ou `None` s'il n'en a jamais réglé."""
        vue = self._Vue.objects(discord_id=discord_id).first()
        return self._en_dict(vue) if vue else None

    def enregistrer(self, discord_id, vue):
        """Range la vue de ce joueur — la crée au premier réglage —, et rend ce qui a été rangé.

        Lecture puis écriture, comme le dépôt de joueurs : mongomock rend mal l'`upsert` de
        mongoengine, et l'index unique sur `discord_id` reste le filet.
        """
        document = self._Vue.objects(discord_id=discord_id).first()
        if document is None:
            document = self._Vue(discord_id=discord_id)
        for champ in CHAMPS:
            setattr(document, champ, vue[champ])
        document.modifiee_le = datetime.now(timezone.utc)
        document.save()
        return self._en_dict(document)

    @staticmethod
    def _en_dict(vue):
        """Ce que le gabarit reçoit : ni document, ni date — personne n'en a l'usage."""
        return {"echelle": vue.echelle, "x": vue.x, "y": vue.y, "ajustee": vue.ajustee}


class DepotDeVuesEnMemoire:
    """Les vues dans un dictionnaire, le temps du processus.

    Tenue par `PERSISTANCE=aucune` et par les tests : la vue vaut pour ce lancement, et disparaît
    avec lui. Recharger la page la retrouve, ce qui est tout ce qu'on lui demande ; redémarrer le
    serveur l'oublie.
    """

    def __init__(self):
        self._par_discord_id = {}

    def par_discord_id(self, discord_id):
        vue = self._par_discord_id.get(discord_id)
        return dict(vue) if vue else None

    def enregistrer(self, discord_id, vue):
        rangee = {champ: vue[champ] for champ in CHAMPS}
        self._par_discord_id[discord_id] = rangee
        return dict(rangee)

    def vider(self):
        """Oublie toutes les vues. Le dépôt vivant aussi longtemps que l'application — que les
        tests construisent une fois pour toute la session —, c'est de quoi repartir de zéro."""
        self._par_discord_id.clear()
