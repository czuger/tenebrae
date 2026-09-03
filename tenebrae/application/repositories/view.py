"""The view repository: where each player was on the map.

The repository exchanges **dicts** - `ViewRecord`, `{scale, x, y, fitted}` -, never a MongoEngine
Document: that is the form in which the view arrives from the browser, is stored, and goes back to
the template. The routes therefore have to know neither `tenebrae.application.models.view` nor
mongoengine.
"""

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Optional

from tenebrae.application.models.view import View

# What a view carries, and nothing else. The browser may send more: it will not be stored.
FIELDS = ("scale", "x", "y", "fitted")

# A view as it travels: three floats and the `fitted` flag.
ViewRecord = dict[str, float | bool]


class MongoViewRepository:
    """Each player's view in MongoDB: one document per player, overwritten at each adjustment."""

    def by_discord_id(self, discord_id: str) -> Optional[ViewRecord]:
        """Finds a player's view.

        Args:
            discord_id: The player's Discord identifier.

        Returns:
            The view, or `None` if they have never adjusted one.
        """
        view = View.objects(discord_id=discord_id).first()
        return self._to_dict(view) if view else None

    def record(self, discord_id: str, view: Mapping[str, float | bool]) -> ViewRecord:
        """Stores a player's view, creating it at the first adjustment.

        A read then a write, like the player repository: the unique index on `discord_id` remains
        the safety net.

        Args:
            discord_id: The player's Discord identifier.
            view: `scale`, `x`, `y`, `fitted`; anything else is ignored.

        Returns:
            What was stored.
        """
        document = View.objects(discord_id=discord_id).first()
        if document is None:
            document = View(discord_id=discord_id)
        for field in FIELDS:
            setattr(document, field, view[field])
        document.updated_at = datetime.now(timezone.utc)
        document.save()
        return self._to_dict(document)

    @staticmethod
    def _to_dict(view: View) -> ViewRecord:
        """Reduces the document to what the template receives: no document, no date.

        Args:
            view: The document.

        Returns:
            The four fields of a `ViewRecord`.
        """
        return {"scale": view.scale, "x": view.x, "y": view.y, "fitted": view.fitted}
