"""The player repository: the accounts the game knows, in base or in memory.

Both repositories return **dicts** - `{discord_id, nickname, display_name, avatar, email}` - and
never a document: that is the form in which a player travels to the routes and to the template,
and it is what the application's connection entity
(`tenebrae/application/models/connection.py`) receives when it asks "who is in session".
"""

from datetime import datetime, timezone


class MongoPlayerRepository:
    """The known Discord accounts, in MongoDB - one document per player."""

    def __init__(self):
        # The import is done here and not at the top: building the in-memory repository must not
        # require mongoengine, which the base-less engine have no reason to load.
        from tenebrae.engine.models.player import Player
        self._Player = Player

    def record(self, identity):
        """Creates the player or updates what Discord has just said about them; returns their dict.

        A read then a write, rather than an `upsert`: mongomock renders mongoengine's poorly, the
        table holds only two players, and the unique index on `discord_id` remains the safety net.
        """
        player = self._Player.objects(discord_id=identity["discord_id"]).first()
        if player is None:
            player = self._Player(discord_id=identity["discord_id"], created_at=self._now())
        player.nickname = identity["nickname"]
        player.display_name = identity.get("display_name")
        player.avatar = identity.get("avatar")
        player.email = identity.get("email")
        player.last_login_at = self._now()
        player.save()
        return self._to_dict(player)

    def by_discord_id(self, discord_id):
        """The player with that identifier, or `None` if none is known any more."""
        player = self._Player.objects(discord_id=discord_id).first()
        return self._to_dict(player) if player else None

    @staticmethod
    def _to_dict(player):
        """What the routes receive: no document, no dates - nobody has a use for them."""
        return {"discord_id": player.discord_id, "nickname": player.nickname,
                "display_name": player.display_name, "avatar": player.avatar,
                "email": player.email}

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)


class InMemoryPlayerRepository:
    """The players in a dictionary, for the lifetime of the process.

    This is not a *null* repository, and the nuance matters: its counterpart for the game keeps
    nothing because the game state already has a home in memory, the module globals of `app.py`. A
    player has none. Keeping nothing here would make connecting impossible, and playing with it.
    It therefore keeps the promise of `PERSISTENCE=none` without forbidding play: accounts hold
    for this run, and vanish with it.
    """

    def __init__(self):
        self._by_discord_id = {}

    def record(self, identity):
        player = {"discord_id": identity["discord_id"], "nickname": identity["nickname"],
                  "display_name": identity.get("display_name"),
                  "avatar": identity.get("avatar"), "email": identity.get("email")}
        self._by_discord_id[player["discord_id"]] = player
        return dict(player)

    def by_discord_id(self, discord_id):
        player = self._by_discord_id.get(discord_id)
        return dict(player) if player else None
