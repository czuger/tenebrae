"""The map view: where a player was, and how close they had zoomed in.

The map is 6173 x 5102 pixels, and it is played zoomed in. Until now, every page reload brought
everyone back to the fit scale, the whole map inside the window: one had to redo one's zoom and
find the place one was manoeuvring at, every time. That is what this document keeps.

**Why here, and not in `engine/models/`?** Because it is not part of the game. The engine does not
know that an image, pixels or a window exist: a game plays from an interpreter, and zoom means
nothing there. A piece's tilt, on the other hand, belongs to the board - the counter really does
lie askew, and both players see it the same way; a map view belongs to **one** pair of eyes. So
this is the application's second model, beside the connection, and it too designates the engine's
player by its `discord_id` alone.

What is kept is **not the scroll**: `x` and `y` are the point of `map.jpg`, in pixels of the
image, that was at the **centre** of the window. A scroll in screen pixels would mean nothing at
the next scale, nor on another screen; that point does.

`fitted` says the map was still set to the window - the opening state, that of the "ajuster"
button. No scale is then frozen: we fit again, and a window of a different size finds its own fit
rather than a zoom inherited from another screen.

The MongoDB field names stay as they were, pinned by `db_field`: renaming a stored field would
orphan the views already saved, and the `vues` collection is not renamed either.
"""

from mongoengine import BooleanField, DateTimeField, Document, FloatField, StringField


class View(Document):
    """What a player was seeing of the map at their last adjustment.

    One document per player, overwritten at each change: no zoom history is kept.
    """

    discord_id = StringField(required=True, unique=True)

    # The map's scale, 1 being the size of the scan (see `MIN_SCALE`/`MAX_SCALE` in
    # `static/zoom.js`, which bounds it for good).
    scale = FloatField(required=True, db_field="echelle")

    # The point of `map.jpg` that was at the centre of the window, in pixels of the image.
    x = FloatField(required=True)
    y = FloatField(required=True)

    # Was the map still set to the window? If so, we will fit again rather than restore `scale`.
    fitted = BooleanField(default=False, db_field="ajustee")

    updated_at = DateTimeField(required=True, db_field="modifiee_le")

    meta = {"collection": "vues",
            "indexes": [{"fields": ["discord_id"], "unique": True}]}

    def __repr__(self):
        return (f"View(discord {self.discord_id}, {round(self.scale * 100)} % "
                f"on ({round(self.x)}, {round(self.y)}))")
