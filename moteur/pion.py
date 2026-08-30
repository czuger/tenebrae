"""Les pions d'Ave Tenebrae : ce qui est imprimé dessus, et ce que le mouvement en retient.

`game_box/pions/pions.json` porte, pour chacune des 127 photos de `game_box/pions/`, les valeurs
relevées à l'œil sur le carton — force, mouvement, tir, portée, vol, faculté spéciale (voir
`game_box/pions/README.md`). Le fichier est lu une fois, à l'import du module, et le résultat est
tenu pour constant : les pions ont été imprimés en 1986, ils ne changent pas en cours de partie.

Le moteur n'en utilise pour l'instant qu'une valeur, le mouvement, qui remplace le forfait de
5 points sur lequel les déplacements étaient calculés jusqu'ici. Le reste est chargé quand même :
la force et le tir serviront au combat.
"""

import json
from pathlib import Path

BOITE = Path(__file__).resolve().parent.parent / "game_box"
CHEMIN_DU_CATALOGUE = BOITE / "pions" / "pions.json"

# Mouvement d'un pion qui n'en porte pas : un marqueur ne se déplace pas de lui-même.
IMMOBILE = 0


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

    def en_dict(self):
        """Rend le pion sous une forme directement convertible en JSON pour le navigateur."""
        return {"cle": self.cle, "image": self.image, "faction": self.faction,
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
