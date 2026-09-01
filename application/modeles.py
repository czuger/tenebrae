"""Les documents MongoDB de l'application : une partie en cours, et rien d'autre.

Ce qui va en base est le seul état qui change en jouant — les positions, la phase, ce que la phase
de combat a déjà consommé. Les référentiels n'y sont pas : la carte, le catalogue des pions et les
scénarios vivent en fichiers dans `game_box/` et `scenarios/`, qui sont la source de vérité du
dépôt (voir le `CLAUDE.md` racine). Les y recopier ferait deux vérités pour une.

Une unité posée n'a pas d'identité propre : le moteur la désigne par sa **case**, un même carton
valant pour toutes les unités qu'il représente (`orques-01-15-infanteries` est posé quinze fois
dans le scénario n° 4). Le document suit cette règle — il n'invente pas d'identifiant d'unité.
"""

from mongoengine import (DateTimeField, Document, IntField, ListField, MapField,
                         StringField)

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
