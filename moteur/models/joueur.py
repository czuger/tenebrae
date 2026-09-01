"""Le joueur, en tant qu'entité de jeu : le compte connu du jeu, et rien de la session web."""

from mongoengine import DateTimeField, Document, EmailField, StringField


class Joueur(Document):
    """Un compte Discord connu du jeu : de quoi dire qui tient un camp, et l'afficher.

    Le document ne sait pas à quoi ce joueur joue — c'est la partie qui retient qui l'occupe, par
    `places`. Un joueur reste en base quand il quitte sa place : il revient s'y asseoir, et son
    pseudo est déjà connu.

    Il ne sait pas non plus qu'une session web existe : ouvrir, tenir et fermer une session est
    l'affaire de l'application, qui pose pour cela une entité à elle
    (`application/models/connexion.py`) et ne désigne ce joueur que par `discord_id`. La
    dépendance ne va que dans ce sens — le moteur n'importe rien de l'application.

    `discord_id` est une **chaîne**, jamais un entier : Discord distribue des identifiants de
    64 bits que JavaScript ne sait pas représenter sans les arrondir, et sa propre documentation
    les traite en chaînes. C'est cet identifiant, et lui seul, qui circule — dans la session, dans
    les places, dans le dict d'état — pour qu'il n'y ait qu'une notion d'identité dans le projet.

    `avatar` porte l'URL toute faite plutôt que le hash rendu par Discord : la connaissance du
    CDN reste dans `application/client_discord.py`, et le reste du code n'a qu'à la poser dans un
    `src`.
    """

    discord_id = StringField(required=True, unique=True)
    pseudo = StringField(required=True)
    # Le « global_name » de Discord, absent des comptes qui n'en ont pas choisi.
    nom_affiche = StringField()
    avatar = StringField()
    # Prévu, mais vide : le jeu ne demande que la portée « identify », qui ne donne pas l'adresse.
    # Le champ attend le jour où quelque chose en aurait l'usage — voir `client_discord.py`.
    courriel = EmailField()

    cree_le = DateTimeField(required=True)
    derniere_connexion_le = DateTimeField(required=True)

    meta = {"collection": "joueurs",
            "indexes": [{"fields": ["discord_id"], "unique": True}]}

    def __repr__(self):
        return f"Joueur({self.pseudo!r}, discord {self.discord_id})"
