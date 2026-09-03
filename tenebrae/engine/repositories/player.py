"""The player repository: the accounts the game knows.

The repository returns **dicts** - `PlayerRecord`, `{discord_id, nickname, display_name, avatar,
email}` - and never a document: that is the form in which a player travels to the routes and to the
template, and it is what the application's connection entity
(`tenebrae/application/models/connection.py`) receives when it asks "who is in session".
"""

from datetime import datetime, timezone
from typing import NotRequired, Optional, TypedDict

from tenebrae.engine.models.player import Player


class PlayerRecord(TypedDict):
    """A player as the routes see them, and an identity as Discord reports it.

    The identifier and the nickname are always there. The other three are what Discord may add:
    an identity may leave them out, and the repositories then record `None` and give back the
    five fields every time.
    """

    discord_id: str
    nickname: str
    display_name: NotRequired[Optional[str]]
    avatar: NotRequired[Optional[str]]
    email: NotRequired[Optional[str]]


class MongoPlayerRepository:
    """The known Discord accounts, in MongoDB - one document per player."""

    def record(self, identity: PlayerRecord) -> PlayerRecord:
        """Creates the player or updates what Discord has just said about them.

        A read then a write, rather than an `upsert`: the table holds only two players, and the
        unique index on `discord_id` remains the safety net.

        Args:
            identity: What Discord reported: `discord_id`, `nickname`, and optionally
                `display_name`, `avatar`, `email`.

        Returns:
            The player as recorded.
        """
        player = Player.objects(discord_id=identity["discord_id"]).first()
        if player is None:
            player = Player(discord_id=identity["discord_id"], created_at=self._now())
        player.nickname = identity["nickname"]
        player.display_name = identity.get("display_name")
        player.avatar = identity.get("avatar")
        player.email = identity.get("email")
        player.last_login_at = self._now()
        player.save()
        return self._to_dict(player)

    def by_discord_id(self, discord_id: str) -> Optional[PlayerRecord]:
        """Finds a player by Discord identifier.

        Args:
            discord_id: The identifier, as a string.

        Returns:
            The player, or `None` if none is known by that identifier.
        """
        player = Player.objects(discord_id=discord_id).first()
        return self._to_dict(player) if player else None

    @staticmethod
    def _to_dict(player: Player) -> PlayerRecord:
        """Reduces the document to what the routes receive: no document, no dates.

        Args:
            player: The document.

        Returns:
            The five fields of a `PlayerRecord`.
        """
        return {"discord_id": player.discord_id, "nickname": player.nickname,
                "display_name": player.display_name, "avatar": player.avatar,
                "email": player.email}

    @staticmethod
    def _now() -> datetime:
        """The current time, timezone-aware.

        Returns:
            Now, in UTC.
        """
        return datetime.now(timezone.utc)
