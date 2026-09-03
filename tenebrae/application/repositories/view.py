"""The view repository: where each player was on the map, in base or in memory.

A repository exchanges **dicts** - `ViewRecord`, `{scale, x, y, fitted}` -, never a MongoEngine
Document: that is the form in which the view arrives from the browser, is stored, and goes back to
the template. `app.py` therefore has to know neither `tenebrae.application.models.view` nor
mongoengine.

Both repositories **keep**, like the player ones and unlike the game one: a view has no other home
in memory, and a repository that kept nothing would make the feature inoperative instead of making
it volatile.
"""

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tenebrae.application.models.view import View

# What a view carries, and nothing else. The browser may send more: it will not be stored.
FIELDS = ("scale", "x", "y", "fitted")

# A view as it travels: three floats and the `fitted` flag.
ViewRecord = dict[str, float | bool]


class MongoViewRepository:
    """Each player's view in MongoDB: one document per player, overwritten at each adjustment."""

    def __init__(self) -> None:
        """Binds the repository to the `View` document.

        The import is done here and not at the top: building the in-memory repository must not
        require mongoengine.
        """
        from tenebrae.application.models.view import View
        self._View = View

    def by_discord_id(self, discord_id: str) -> Optional[ViewRecord]:
        """Finds a player's view.

        Args:
            discord_id: The player's Discord identifier.

        Returns:
            The view, or `None` if they have never adjusted one.
        """
        view = self._View.objects(discord_id=discord_id).first()
        return self._to_dict(view) if view else None

    def record(self, discord_id: str, view: Mapping[str, float | bool]) -> ViewRecord:
        """Stores a player's view, creating it at the first adjustment.

        A read then a write, like the player repository: mongomock renders mongoengine's `upsert`
        poorly, and the unique index on `discord_id` remains the safety net.

        Args:
            discord_id: The player's Discord identifier.
            view: `scale`, `x`, `y`, `fitted`; anything else is ignored.

        Returns:
            What was stored.
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
    def _to_dict(view: "View") -> ViewRecord:
        """Reduces the document to what the template receives: no document, no date.

        Args:
            view: The document.

        Returns:
            The four fields of a `ViewRecord`.
        """
        return {"scale": view.scale, "x": view.x, "y": view.y, "fitted": view.fitted}


class InMemoryViewRepository:
    """The views in a dictionary, for the lifetime of the process.

    Held by `PERSISTENCE=none` and by the tests: reloading the page finds the view again,
    restarting the server forgets it.
    """

    _by_discord_id: dict[str, ViewRecord]

    def __init__(self) -> None:
        """Opens an empty register of views."""
        self._by_discord_id = {}

    def by_discord_id(self, discord_id: str) -> Optional[ViewRecord]:
        """Finds a player's view.

        Args:
            discord_id: The player's Discord identifier.

        Returns:
            A copy of the view, or `None` if they have never adjusted one.
        """
        view = self._by_discord_id.get(discord_id)
        return dict(view) if view else None

    def record(self, discord_id: str, view: Mapping[str, float | bool]) -> ViewRecord:
        """Stores a player's view.

        Args:
            discord_id: The player's Discord identifier.
            view: `scale`, `x`, `y`, `fitted`; anything else is ignored.

        Returns:
            A copy of what was stored.
        """
        stored = {field: view[field] for field in FIELDS}
        self._by_discord_id[discord_id] = stored
        return dict(stored)

    def clear(self) -> None:
        """Forgets every view: what starting a test session from scratch takes."""
        self._by_discord_id.clear()
