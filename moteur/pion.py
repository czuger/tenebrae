"""Les pions d'Ave Tenebrae : ce qui est imprimé dessus, et ce que le mouvement en retient.

`game_box/pions/pions.json` porte, pour chacune des 127 photos de `game_box/pions/`, les valeurs
relevées à l'œil sur le carton — force, mouvement, tir, portée, vol, faculté spéciale (voir
`game_box/pions/README.md`). Le fichier est lu une fois, à l'import du module, et le résultat est
tenu pour constant : les pions ont été imprimés en 1986, ils ne changent pas en cours de partie.

Le moteur n'en utilise pour l'instant qu'une valeur, le mouvement, qui remplace le forfait de
5 points sur lequel les déplacements étaient calculés jusqu'ici. Le reste est chargé quand même :
la force et le tir serviront au combat.

Le camp, lui, n'est pas dans `pions.json` : il n'est pas imprimé sur le carton. Il vient de la
répartition en camps de `game_box/pions/README.md`, tenue ici dans `CAMPS`, et sert à savoir qui
est l'adversaire de qui — donc quelles zones de contrôle s'exercent contre qui.
"""

import json
from pathlib import Path

BOITE = Path(__file__).resolve().parent.parent / "game_box"
CHEMIN_DU_CATALOGUE = BOITE / "pions" / "pions.json"

# Mouvement d'un pion qui n'en porte pas : un marqueur ne se déplace pas de lui-même.
IMMOBILE = 0

# Les trois camps. Le neutre n'est l'adversaire de personne : ni il n'exerce de zone de contrôle,
# ni il n'en subit.
ALLIANCE, TENEBRES, NEUTRE = "alliance", "tenebres", "neutre"

# Le camp de chaque faction, d'après la section « Camps » de `game_box/pions/README.md`. Les
# répertoires sans unité — feuilles de suivi, marqueurs, vues d'ensemble — sont neutres faute de
# mieux : rien n'y combat.
CAMPS = {
    "01-yzent": TENEBRES,             # allié d'opportunité du Magiocrate
    "02-reissland": ALLIANCE,
    "03-empire": ALLIANCE,
    "04-templiers": ALLIANCE,
    "05-population": ALLIANCE,
    "06-empire-de-lynn": ALLIANCE,    # scénario 3
    "07-chaos": TENEBRES,
    "08-non-humains": TENEBRES,
    "09-elfes": ALLIANCE,
    "10-nains": ALLIANCE,             # scénario 4
    "11-orques": TENEBRES,
    "12-sahuaguins": TENEBRES,
    "13-dragons": ALLIANCE,
    "14-morts-vivants": TENEBRES,
    "15-demons": TENEBRES,
    "16-volants": NEUTRE,             # scénario 5
    "17-conjurations": NEUTRE,
    "18-machines-de-siege": TENEBRES,  # le Juggernaut
    "19-magiciens": NEUTRE,
    "20-marqueurs": NEUTRE,
    "21-vues-d-ensemble": NEUTRE,
}

# Qui s'oppose à qui. Le neutre n'apparaît pas : il n'a pas d'adversaire.
ADVERSAIRES = {ALLIANCE: TENEBRES, TENEBRES: ALLIANCE}


class Pion:
    """Un pion de la boîte, désigné par le nom de sa photo sans répertoire ni extension.

    Les valeurs absentes du carton — ou illisibles sur la photo — valent `None` ; `remarques` dit
    alors ce qui manque. Seul `points_de_mouvement` tranche, parce que le déplacement a besoin
    d'un nombre.
    """

    __slots__ = ("cle", "image", "faction", "force", "mouvement", "tir", "portee",
                 "mouvement_vol", "facultes_speciales", "symbole", "remarques")

    def __init__(self, cle, valeurs):
        self.cle = cle
        self.image = valeurs["image"]
        self.faction = valeurs["faction"]
        self.force = valeurs["force"]
        self.mouvement = valeurs["mouvement"]
        self.tir = valeurs["tir"]
        self.portee = valeurs["portee"]
        self.mouvement_vol = valeurs["mouvement_vol"]
        self.facultes_speciales = valeurs["facultes_speciales"]
        self.symbole = valeurs["symbole"]
        self.remarques = valeurs["remarques"]

    @property
    def est_une_unite(self):
        """Dit si le pion est une unité, et non un marqueur ou une photo qui n'est pas un pion.

        Une unité porte au moins une valeur chiffrée : les marqueurs (`PA`, `D`, flammes, brume,
        ruines, brèche), les deux feuilles de suivi et les quatre vues d'ensemble n'en ont aucune.
        """
        return any(valeur is not None
                   for valeur in (self.force, self.mouvement, self.mouvement_vol))

    @property
    def points_de_mouvement(self):
        """Le budget de mouvement du pion, en points.

        Le mouvement au sol lu sur le carton, à deux exceptions près : un pion qui n'a qu'un
        mouvement en vol se déplace de ce nombre-là faute de mieux — le vol n'est pas encore une
        règle à part —, et ce qui ne porte aucune valeur ne bouge pas.
        """
        if self.mouvement is not None:
            return self.mouvement
        if self.mouvement_vol is not None:
            return self.mouvement_vol
        return IMMOBILE

    @property
    def camp(self):
        """Le camp de sa faction : `ALLIANCE`, `TENEBRES` ou `NEUTRE` (voir `CAMPS`)."""
        return CAMPS[self.faction]

    @property
    def exerce_une_zone_de_controle(self):
        """Dit si le pion tient sous son contrôle les six cases qui l'environnent.

        Toute unité d'un camp le fait. Les marqueurs n'exercent rien puisqu'ils ne sont pas des
        unités, et les neutres non plus faute d'adversaire. Le fascicule dispense en outre les
        leaders, les jeteurs de sorts, les démons et les morts-vivants ordinaires : ces exceptions
        ne sont pas appliquées, elles sont consignées dans `moteur/README.md`.
        """
        return self.est_une_unite and self.camp != NEUTRE

    def en_dict(self):
        """Rend le pion sous une forme directement convertible en JSON pour le navigateur."""
        return {"cle": self.cle, "image": self.image, "faction": self.faction,
                "camp": self.camp,
                "force": self.force, "mouvement": self.mouvement, "tir": self.tir,
                "portee": self.portee, "mouvement_vol": self.mouvement_vol,
                "facultes_speciales": self.facultes_speciales, "symbole": self.symbole,
                "remarques": self.remarques,
                "points_de_mouvement": self.points_de_mouvement}

    def __repr__(self):
        return f"Pion({self.cle!r}, {self.points_de_mouvement} PM)"


def lire_le_catalogue(chemin=CHEMIN_DU_CATALOGUE):
    """Rend « clé → Pion » pour tout ce que porte `pions.json`, marqueurs et vues compris."""
    with Path(chemin).open(encoding="utf-8") as fichier:
        return {cle: Pion(cle, valeurs) for cle, valeurs in json.load(fichier).items()}


# Tous les pions de la boîte, y compris ce qui n'en est pas un : le tri revient à l'appelant,
# par `est_une_unite`.
CATALOGUE = lire_le_catalogue()


def pion(cle):
    """Le pion de clé `cle` ; `KeyError` si la boîte ne le connaît pas."""
    return CATALOGUE[cle]
