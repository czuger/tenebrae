"""The view repository: where each player was on the map, in base or in memory.

A repository exchanges **dicts** - `{scale, x, y, fitted}` -, never a MongoEngine Document: that
is the form in which the view arrives from the browser, is stored, and goes back to the template.
`app.py` therefore has to know neither `tenebrae.application.models.view` nor mongoengine.

Both repositories **keep**, like the player ones and unlike the game one: a view has no other home
in memory - there is no module global holding it - and a repository that kept nothing would make
the feature inoperative instead of making it volatile.
"""

from datetime import datetime, timezone

# What a view carries, and nothing else. The browser may send more: it will not be stored.
FIELDS = ("scale", "x", "y", "fitted")


class MongoViewRepository:
    """Each player's view in MongoDB: one document per player, overwritten at each adjustment."""

    def __init__(self):
        # The import is done here and not at the top: building the in-memory repository must not
        # require mongoengine, which the base-less engine have no reason to load.
        from tenebrae.application.models.view import View
        self._View = View

    def by_discord_id(self, discord_id):
        """This player's view, or `None` if they have never adjusted one."""
        view = self._View.objects(discord_id=discord_id).first()
        return self._to_dict(view) if view else None

    def record(self, discord_id, view):
        """Stores this player's view - creates it at the first adjustment - and returns what was
        stored.

        A read then a write, like the player repository: mongomock renders mongoengine's `upsert`
        poorly, and the unique index on `discord_id` remains the safety net.
        """
        document = self._View.objects(discord_id=discord_id).first()
        if document is None:
            document = self._View(discord_id=discord_id)
        for field in FIELDS:
            setattr(document, field, view[field])
        document.updated_at = datetime.now(timezone.utc)
        document.save()
        return self._to_dict(document)

    @staticmethod
    def _to_dict(view):
        """What the template receives: no document, no date - nobody has a use for them."""
        return {"scale": view.scale, "x": view.x, "y": view.y, "fitted": view.fitted}


class InMemoryViewRepository:
    """The views in a dictionary, for the lifetime of the process.

    Held by `PERSISTENCE=none` and by the engine: the view holds for this run, and vanishes with
    it. Reloading the page finds it again, which is all that is asked of it; restarting the server
    forgets it.
    """

    def __init__(self):
        self._by_discord_id = {}

    def by_discord_id(self, discord_id):
        view = self._by_discord_id.get(discord_id)
        return dict(view) if view else None

    def record(self, discord_id, view):
        stored = {field: view[field] for field in FIELDS}
        self._by_discord_id[discord_id] = stored
        return dict(stored)

    def clear(self):
        """Forgets every view. The repository living as long as the application - which the engine
        build once for the whole session -, this is what starting from scratch takes."""
        self._by_discord_id.clear()
