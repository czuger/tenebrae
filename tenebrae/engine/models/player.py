"""The player, as a game entity: the account the game knows, and nothing of the web session.

The MongoDB field names stay as they were (`pseudo`, `nom_affiche`, `courriel`, `cree_le`,
`derniere_connexion_le`), pinned by `db_field`: renaming a stored field would orphan the accounts
already in base, and the `joueurs` collection is not renamed either. Only the Python side is
English.
"""

from mongoengine import DateTimeField, Document, EmailField, StringField


class Player(Document):
    """A Discord account the game knows: enough to say who holds a side, and to display it.

    The document does not know what this player is playing - it is the game that keeps who
    occupies it, through `seats`. A player stays in base when leaving their seat: they come back
    to sit down, and their nickname is already known.

    Nor does it know that a web session exists: opening, holding and closing a session is the
    application's business, which places an entity of its own for that
    (`tenebrae/application/models/connection.py`) and designates this player only by `discord_id`.
    The dependency only runs that way - the engine imports nothing from the application.

    `discord_id` is a **string**, never an integer: Discord hands out 64-bit identifiers that
    JavaScript cannot represent without rounding them, and its own documentation treats them as
    strings. It is that identifier, and it alone, that circulates - in the session, in the seats,
    in the state dict - so that there is a single notion of identity in the project.

    `avatar` carries the ready-made URL rather than the hash Discord returns: knowledge of the CDN
    stays in `tenebrae/application/discord_client.py`, and the rest of the code only has to drop it
    into a `src`.
    """

    discord_id = StringField(required=True, unique=True)
    nickname = StringField(required=True, db_field="pseudo")
    # Discord's "global_name", absent from accounts that have not chosen one.
    display_name = StringField(db_field="nom_affiche")
    avatar = StringField()
    # Planned, but empty: the game only asks for the "identify" scope, which does not give the
    # address. The field waits for the day something has a use for it - see
    # `tenebrae/application/discord_client.py`.
    email = EmailField(db_field="courriel")

    created_at = DateTimeField(required=True, db_field="cree_le")
    last_login_at = DateTimeField(required=True, db_field="derniere_connexion_le")

    meta = {"collection": "joueurs",
            "indexes": [{"fields": ["discord_id"], "unique": True}]}

    def __repr__(self):
        return f"Player({self.nickname!r}, discord {self.discord_id})"
