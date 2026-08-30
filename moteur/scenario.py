"""Les scénarios : une mise en place fixée, lue dans `scenarios/`.

Le fascicule décrit chaque scénario en une phrase — « l'armée naine se masse au sud du volcan de
Toth » — sans dire quel pion va sur quelle case. Le passage de la phrase aux hexagones a été fait
une fois pour toutes, et le résultat vit dans `scenarios/*.json` (voir `scenarios/README.md`) :
le moteur ne fait que le lire.

Un scénario donne un `Plateau` prêt à jouer, où chaque camp est déjà en place.
"""

import json
from pathlib import Path

from moteur.hexagone import Hex
from moteur.pion import CATALOGUE
from moteur.plateau import Plateau

SCENARIOS = Path(__file__).resolve().parent.parent / "scenarios"


class Scenario:
    """Une mise en place : les armées en présence, et le pion posé sur chaque case."""

    __slots__ = ("numero", "nom", "source", "armees", "placement")

    def __init__(self, valeurs):
        self.numero = valeurs["numero"]
        self.nom = valeurs["nom"]
        self.source = valeurs["source"]
        self.armees = tuple(valeurs["armees"])
        self.placement = dict(valeurs["placement"])

    @property
    def camps(self):
        """Les camps en présence, dans l'ordre des joueurs."""
        return tuple(armee["camp"] for armee in self.armees)

    def plateau(self):
        """Un `Plateau` neuf, chaque pion sur sa case.

        Une clé de pion inconnue du catalogue, ou une case hors carte, arrête la lecture : mieux
        vaut un scénario refusé qu'une armée amputée sans que personne ne le voie.
        """
        return Plateau((Hex.depuis_cle(case), CATALOGUE[cle])
                       for case, cle in self.placement.items())

    def __len__(self):
        return len(self.placement)

    def __repr__(self):
        return f"Scenario({self.numero}, {self.nom!r}, {len(self.placement)} unités)"


def lire(chemin):
    """Lit un scénario dans son fichier JSON."""
    with Path(chemin).open(encoding="utf-8") as fichier:
        return Scenario(json.load(fichier))


def scenarios_disponibles():
    """« numéro → chemin » pour tous les scénarios fixés, dans l'ordre des numéros."""
    fichiers = {}
    for chemin in sorted(SCENARIOS.glob("scenario-*.json")):
        fichiers[int(chemin.stem.split("-")[1])] = chemin
    return fichiers


def scenario(numero):
    """Le scénario de ce numéro ; `KeyError` s'il n'a pas encore été fixé."""
    return lire(scenarios_disponibles()[numero])
