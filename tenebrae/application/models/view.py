"""The map view: where a player was, and how close they had zoomed in.

The map is 6173 x 5102 pixels, and it is played zoomed in. This document keeps the zoom and the
place one was manoeuvring at, so that a reload does not bring everyone back to the fit scale.

**Why here, and not in `tenebrae/engine/models/`?** Because it is not part of the game. The engine
does not know that an image, pixels or a window exist. A piece's tilt belongs to the board - both
players see it the same way; a map view belongs to **one** pair of eyes. So this is the
application's second model, beside the connection, and it too designates the engine's player by its
`discord_id` alone.

What is kept is **not the scroll**: `x` and `y` are the point of `map.jpg`, in pixels of the
image, that was at the **centre** of the window - a scroll in screen pixels would mean nothing at
the next scale. `fitted` says the map was still set to the window: no scale is then frozen, and a
window of a different size finds its own fit.

The MongoDB field names stay as they were, pinned by `db_field`: renaming a stored field would
orphan the views already saved, and the `vues` collection is not renamed either.
"""

from mongoengine import BooleanField, DateTimeField, Document, FloatField, StringField


class View(Document):
    """What a player was seeing of the map at their last adjustment.

    One document per player, overwritten at each change: no zoom history is kept.
    """

    discord_id = StringField(required=True, unique=True)

    # 1 is the size of the scan; `static/zoom.js` bounds it for good.
    scale = FloatField(required=True, db_field="echelle")

    # The point of `map.jpg` at the centre of the window, in pixels of the image.
    x = FloatField(required=True)
    y = FloatField(required=True)

    fitted = BooleanField(default=False, db_field="ajustee")

    updated_at = DateTimeField(required=True, db_field="modifiee_le")

    meta = {"collection": "vues",
            "indexes": [{"fields": ["discord_id"], "unique": True}]}

    def __repr__(self) -> str:
        """The player, the scale as a percentage and the centre."""
        return (f"View(discord {self.discord_id}, {round(self.scale * 100)} % "
                f"on ({round(self.x)}, {round(self.y)}))")
