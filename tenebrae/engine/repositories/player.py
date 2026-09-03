"""The player repository: the accounts the game knows, in base or in memory.

Both repositories return **dicts** - `PlayerRecord`, `{discord_id, nickname, display_name, avatar,
email}` - and never a document: that is the form in which a player travels to the routes and to the
template, and it is what the application's connection entity
(`tenebrae/application/models/connection.py`) receives when it asks "who is in session".
"""

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from tenebrae.engine.models.player import Player

# A player as the routes see them, and an identity as Discord reports it: the same five fields,
# every value a string or `None`.
PlayerRecord = dict[str, Optional[str]]


class MongoPlayerRepository:
    """The known Discord accounts, in MongoDB - one document per player."""

    def __init__(self) -> None:
        """Binds the repository to the `Player` document.

        The import is done here and not at the top: building the in-memory repository must not
        require mongoengine.
        """
        from tenebrae.engine.models.player import Player
        self._Player = Player

    def record(self, identity: Mapping[str, Optional[str]]) -> PlayerRecord:
        """Creates the player or updates what Discord has just said about them.

        A read then a write, rather than an `upsert`: mongomock renders mongoengine's poorly, the
        table holds only two players, and the unique index on `discord_id` remains the safety net.

        Args:
            identity: What Discord reported: `discord_id`, `nickname`, and optionally
                `display_name`, `avatar`, `email`.

        Returns:
            The player as recorded.
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

    def by_discord_id(self, discord_id: str) -> Optional[PlayerRecord]:
        """Finds a player by Discord identifier.

        Args:
            discord_id: The identifier, as a string.

        Returns:
            The player, or `None` if none is known by that identifier.
        """
        player = self._Player.objects(discord_id=discord_id).first()
        return self._to_dict(player) if player else None

    @staticmethod
    def _to_dict(player: "Player") -> PlayerRecord:
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


class InMemoryPlayerRepository:
    """The players in a dictionary, for the lifetime of the process.

    Not a *null* repository: the game repository keeps nothing because the game state already has a
    home in memory, but a player has none, and keeping nothing here would make connecting
    impossible. Accounts hold for this run, and vanish with it.
    """

    _by_discord_id: dict[str, PlayerRecord]

    def __init__(self) -> None:
        """Opens an empty register of players."""
        self._by_discord_id = {}

    def record(self, identity: Mapping[str, Optional[str]]) -> PlayerRecord:
        """Creates or updates a player from what Discord reported.

        Args:
            identity: `discord_id`, `nickname`, and optionally `display_name`, `avatar`, `email`.

        Returns:
            A copy of the player as recorded.
        """
        player = {"discord_id": identity["discord_id"], "nickname": identity["nickname"],
                  "display_name": identity.get("display_name"),
                  "avatar": identity.get("avatar"), "email": identity.get("email")}
        self._by_discord_id[player["discord_id"]] = player
        return dict(player)

    def by_discord_id(self, discord_id: str) -> Optional[PlayerRecord]:
        """Finds a player by Discord identifier.

        Args:
            discord_id: The identifier, as a string.

        Returns:
            A copy of the player, or `None` if none is known by that identifier.
        """
        player = self._by_discord_id.get(discord_id)
        return dict(player) if player else None
