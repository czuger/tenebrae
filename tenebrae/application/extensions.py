"""The application's MongoDB extension: a single instance, shared by the whole project.

The todo asked for Flask-MongoEngine. Its last published version (1.0.0, 2022) imports
`flask.json.JSONEncoder`, removed from Flask since 2.3: it does not even import under this
repository's Flask 3. We therefore keep its *interface* - `db = MongoEngine()`, `db.init_app(app)`,
`MONGODB_SETTINGS` in the config - on top of `mongoengine` alone, which is what Flask-MongoEngine
wrapped anyway. The rest of the application knows only `db` and the Documents: if the extension
ever becomes installable again, this file is the only one to change.
"""

import mongoengine


class MongoEngine:
    """The wiring of mongoengine onto a Flask application.

    `init_app` reads `MONGODB_SETTINGS` from the configuration and opens the connection.
    Mongoengine keeps a global registry of connections itself, by alias: initialising two
    applications on the same alias without disconnecting the first would raise an error - hence
    the preliminary disconnect, which makes the call idempotent.
    """

    def __init__(self):
        self.connection = None
        self.settings = None

    def init_app(self, application):
        self.settings = dict(application.config.get("MONGODB_SETTINGS") or {})
        alias = self.settings.pop("alias", mongoengine.DEFAULT_CONNECTION_NAME)
        # Without this setting, pymongo warns that it falls back on its legacy UUID
        # representation. The game stores no UUID; we set the modern value to hear no more of it.
        self.settings.setdefault("uuidRepresentation", "standard")
        mongoengine.disconnect(alias)
        self.connection = mongoengine.connect(alias=alias, **self.settings)
        application.extensions["mongoengine"] = self
        return self.connection


# The single instance: the whole project imports this one, never another.
db = MongoEngine()
