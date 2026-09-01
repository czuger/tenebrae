"""L'extension MongoDB de l'application : une seule instance, partagée par tout le projet.

Le todo demandait Flask-MongoEngine. Sa dernière version publiée (1.0.0, 2022) importe
`flask.json.JSONEncoder`, retiré de Flask depuis la 2.3 : elle ne s'importe même pas sous le
Flask 3 de ce dépôt. On garde donc son *interface* — `db = MongoEngine()`, `db.init_app(app)`,
`MONGODB_SETTINGS` dans la config — au-dessus de `mongoengine` seul, qui est ce que
Flask-MongoEngine enveloppait de toute façon. Le reste de l'application ne connaît que `db` et les
Documents : si l'extension redevient un jour installable, ce fichier est le seul à changer.
"""

import mongoengine


class MongoEngine:
    """Le branchement de mongoengine sur une application Flask.

    `init_app` lit `MONGODB_SETTINGS` dans la configuration et ouvre la connexion. Mongoengine
    tient lui-même un registre global de connexions, par alias : réinitialiser deux applications
    sur le même alias sans déconnecter la première lèverait une erreur — d'où la déconnexion
    préalable, qui rend l'appel idempotent.
    """

    def __init__(self):
        self.connexion = None
        self.reglages = None

    def init_app(self, application):
        self.reglages = dict(application.config.get("MONGODB_SETTINGS") or {})
        alias = self.reglages.pop("alias", mongoengine.DEFAULT_CONNECTION_NAME)
        # Sans ce réglage, pymongo avertit qu'il retombe sur sa représentation d'UUID héritée.
        # Le jeu n'enregistre aucun UUID ; on fixe la valeur moderne pour n'en plus parler.
        self.reglages.setdefault("uuidRepresentation", "standard")
        mongoengine.disconnect(alias)
        self.connexion = mongoengine.connect(alias=alias, **self.reglages)
        application.extensions["mongoengine"] = self
        return self.connexion


# L'instance unique : tout le projet importe celle-ci, jamais une autre.
db = MongoEngine()
