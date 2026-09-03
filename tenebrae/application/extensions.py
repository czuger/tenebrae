"""The application's MongoDB extension: a single instance, shared by the whole project.

Flask-MongoEngine's last published version (1.0.0, 2022) imports `flask.json.JSONEncoder`, removed
from Flask since 2.3: it does not even import under this repository's Flask 3. We therefore keep
its *interface* - `db = MongoEngine()`, `db.init_app(app)`, `MONGODB_SETTINGS` in the config - on
top of `mongoengine` alone. The rest of the application knows only `db` and the Documents: if the
extension ever becomes installable again, this file is the only one to change.
"""

from typing import Optional

import mongoengine
from flask import Flask
from pymongo import MongoClient


class MongoEngine:
    """The wiring of mongoengine onto a Flask application."""

    connection: Optional[MongoClient]
    settings: Optional[dict[str, object]]

    def __init__(self) -> None:
        """Creates the extension, not yet connected."""
        self.connection = None
        self.settings = None

    def init_app(self, application: Flask) -> MongoClient:
        """Reads `MONGODB_SETTINGS` from the configuration and opens the connection.

        Mongoengine keeps a global registry of connections by alias: initialising twice on the same
        alias without disconnecting first would raise. The preliminary disconnect makes the call
        idempotent.

        Args:
            application: The Flask application to connect.

        Returns:
            The pymongo client mongoengine opened.
        """
        self.settings = dict(application.config.get("MONGODB_SETTINGS") or {})
        alias = self.settings.pop("alias", mongoengine.DEFAULT_CONNECTION_NAME)
        # Silences pymongo's warning about its legacy UUID representation; the game stores no UUID.
        self.settings.setdefault("uuidRepresentation", "standard")
        mongoengine.disconnect(alias)
        self.connection = mongoengine.connect(alias=alias, **self.settings)
        application.extensions["mongoengine"] = self
        return self.connection


# The single instance: the whole project imports this one, never another.
db = MongoEngine()
