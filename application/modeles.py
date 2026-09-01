"""Les documents MongoDB de l'application : une partie en cours, et les joueurs qui la tiennent.

Ce qui va en base est le seul état qui change en jouant — les positions, la phase, ce que la phase
de combat a déjà consommé, qui est assis à quel camp —, plus les comptes Discord admis à la table. Les référentiels n'y sont pas : la carte, le catalogue des pions et les
scénarios vivent en fichiers dans `game_box/` et `scenarios/`, qui sont la source de vérité du
dépôt (voir le `CLAUDE.md` racine). Les y recopier ferait deux vérités pour une.

Une unité posée n'a pas d'identité propre : le moteur la désigne par sa **case**, un même carton
valant pour toutes les unités qu'il représente (`orques-01-15-infanteries` est posé quinze fois
dans le scénario n° 4). Le document suit cette règle — il n'invente pas d'identifiant d'unité.
"""

from mongoengine import (DateTimeField, Document, EmailField, IntField, ListField,
                         MapField, StringField)

from moteur.phase import COMBAT, MOUVEMENT


class Partie(Document):
    """Une partie sauvegardée : de quoi rouvrir le plateau là où on l'a laissé.

    `placement` est le format du moteur, « q,r,s » → clé de pion — celui de `Plateau.en_dict()` et
    de `Scenario.placement`. Les clés d'un `MapField` deviennent des clés de document Mongo, qui
    interdit le point et le dollar en tête ; les coordonnées cubiques n'usent que de chiffres, de
    virgules et du signe moins, elles passent telles quelles.

    Les pions éliminés disparaissent simplement du placement : le moteur ne tient pas de cimetière.
    """

    scenario = IntField(required=True)
    placement = MapField(StringField(), required=True)

    # La phase courante. Le couple (camp, type) suffit à replacer le tour dans sa séquence ; la
    # magie n'y figure pas, le serveur la franchit toujours.
    camp_actif = StringField(required=True)
    type_de_phase = StringField(required=True, choices=(MOUVEMENT, COMBAT))
    numero_de_tour = IntField(required=True, min_value=1)

    # Ce que la phase de combat en cours a consommé : des cases, pas des pions. Vide dès qu'on
    # change de phase.
    attaquants_engages = ListField(StringField())
    cibles_engagees = ListField(StringField())

    # Qui tient quel camp : « alliance » ou « tenebres » → identifiant Discord. Un camp libre n'a
    # pas de clé. C'est un identifiant et non une `ReferenceField` vers `Joueur` parce que les
    # dépôts n'échangent que des dicts d'état : une référence obligerait à faire sortir un
    # document de `depots.py`, ou à promener un DBRef. La partie reste ainsi lisible seule.
    #
    # Le champ n'est pas requis : les parties enregistrées avant les joueurs n'en ont pas, et
    # elles doivent rester reprenables — la table est alors simplement vide.
    places = MapField(StringField())

    creee_le = DateTimeField(required=True)
    modifiee_le = DateTimeField(required=True)

    # `ordering` fait de la partie la plus récente la première trouvée : c'est celle que le
    # serveur reprend au chargement de « / ». L'identifiant départage : deux parties ouvertes dans
    # le même tick d'horloge portent la même date, et l'ordre serait sinon indécis — un
    # « recommencer » suivi d'un rechargement pourrait reprendre la partie abandonnée.
    # Les ObjectId croissent avec le temps, le plus grand est donc le plus récent.
    meta = {"collection": "parties", "indexes": ["-modifiee_le"],
            "ordering": ["-modifiee_le", "-id"]}

    def __repr__(self):
        return (f"Partie(scénario {self.scenario}, tour {self.numero_de_tour}, "
                f"{len(self.placement)} pions posés)")


class Joueur(Document):
    """Un compte Discord connu du jeu : de quoi dire qui tient un camp, et l'afficher.

    Le document ne sait pas à quoi ce joueur joue — c'est la partie qui retient qui l'occupe, par
    `places`. Un joueur reste en base quand il quitte sa place : il revient s'y asseoir, et son
    pseudo est déjà connu.

    `discord_id` est une **chaîne**, jamais un entier : Discord distribue des identifiants de
    64 bits que JavaScript ne sait pas représenter sans les arrondir, et sa propre documentation
    les traite en chaînes. C'est cet identifiant, et lui seul, qui circule — dans la session, dans
    les places, dans le dict d'état — pour qu'il n'y ait qu'une notion d'identité dans le projet.

    `avatar` porte l'URL toute faite plutôt que le hash rendu par Discord : la connaissance du
    CDN reste dans `client_discord.py`, et le reste du code n'a qu'à la poser dans un `src`.
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
