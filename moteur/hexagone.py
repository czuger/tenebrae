"""La grille d'hexagones d'Ave Tenebrae et les déplacements qu'elle autorise.

La carte du jeu est la transcription du scan (`game_box/carte_details.json`) recouverte par les
corrections relevées à l'œil (`game_box/map_fix.json`). Les deux fichiers sont lus une fois, à
l'import du module, et le résultat est tenu pour constant : le plateau a été imprimé en 1986, il
ne change pas en cours de partie. Corriger la carte demande donc de relancer le programme.

Le coût du mouvement suit le *Tableau des terrains* du fascicule ; les réserves d'interprétation
sont consignées dans `moteur/README.md`. Le budget de mouvement, lui, vient du pion : c'est
`moteur.pion` qui le lit sur le carton, et `deplacements()` le reçoit en argument. À ce stade,
toutes les unités sont terrestres : ni vol, ni pouvoirs, ni empilement, ni zones de contrôle.
"""

import heapq
import json
from fractions import Fraction
from pathlib import Path

BOITE = Path(__file__).resolve().parent.parent / "game_box"

# Tous les éléments de chaque hexagone, le terrain principal en tête. On lit `carte_details.json`
# et non `carte.json` : sa tête de liste donne le même terrain principal, mais lui seul garde les
# 58 routes et chemins que la règle de priorité de la carte masque sous un bois ou un massif.
with (BOITE / "carte_details.json").open(encoding="utf-8") as fichier:
    CARTE_TRANSCRITE = {cle: tuple(elements) for cle, elements in json.load(fichier).items()}

# Les corrections relevées à l'œil sur /admin/map_fix : « q,r,s » → terrain principal. Fichier à
# part, tenu à la main ; la transcription, elle, sort du script et n'est jamais retouchée.
CHEMIN_DES_CORRECTIONS = BOITE / "map_fix.json"


def lire_les_corrections():
    """Rend les corrections relevées ; un dictionnaire vide si le fichier n'existe pas."""
    try:
        with CHEMIN_DES_CORRECTIONS.open(encoding="utf-8") as fichier:
            return json.load(fichier)
    except FileNotFoundError:
        return {}


def corriger(transcription, corrections):
    """La transcription recouverte par les corrections, sans la modifier.

    Une correction ne porte que sur le terrain principal : le terrain corrigé prend la tête à la
    place de celui que la priorité de la carte y avait mis, et les éléments secondaires suivent.
    C'est ce qui permet à un bois corrigé en colline de garder la route qu'il masquait. Une clé
    inconnue de la transcription est ignorée : on ne crée pas d'hexagone hors carte.
    """
    carte = dict(transcription)
    for cle, terrain in corrections.items():
        if cle not in carte:
            continue
        secondaires = (element for element in carte[cle][1:] if element != terrain)
        carte[cle] = (terrain, *secondaires)
    return carte


# Les corrections effectivement en vigueur, et la carte sur laquelle le jeu se joue. Relever une
# correction de plus ne les change pas : il faut relancer le programme.
CORRECTIONS_APPLIQUEES = lire_les_corrections()
CARTE = corriger(CARTE_TRANSCRITE, CORRECTIONS_APPLIQUEES)

# Les six voisins d'un hexagone, en coordonnées cubiques.
DIRECTIONS = ((1, -1, 0), (1, 0, -1), (0, 1, -1), (0, -1, 1), (-1, 1, 0), (-1, 0, 1))

# Points de mouvement dépensés pour entrer sur la case. Les terrains absents coûtent 1 point.
COUT_ORDINAIRE = Fraction(1)
COUTS = {
    "bois": Fraction(2),      # BOIS — 2 points sauf Elfes
    "colline": Fraction(2),   # COLLINES — 2 points sauf élémentaire Terre
    "ruines": Fraction(2),    # RUINES — × 2
}

# Tarif des voies, quand on les suit d'une case à l'autre : ROUTES × 3, CHEMINS × 2.
COUTS_DES_VOIES = {"route": Fraction(1, 3), "chemin": Fraction(1, 2)}

# Infranchissables par une unité terrestre : lacs et rivières (sauf ponts, non relevés sur la
# carte), Faille de Tsaroth, forts et châteaux (sauf par combat ou par alliés).
INFRANCHISSABLES = frozenset({"lac", "riviere", "faille", "fort", "chateau"})

# La montagne ne s'aborde que par une colline, une autre montagne, ou une voie qui la traverse.
ACCES_A_LA_MONTAGNE = frozenset({"colline", "montagne"})

# Terrains qu'une unité terrestre ne peut pas occuper, et donc d'où elle ne part jamais. Les forts
# et les châteaux n'en sont pas : on ne les traverse pas, mais on peut y tenir garnison.
INHABITABLES = frozenset({"lac", "riviere", "faille"})

# Forfait de mouvement, pour qui ne dit pas de quel pion il parle : les valeurs des cartons vont
# de 1 à 20 points, et 5 est la valeur qui servait avant qu'on les lise (voir `moteur.pion`).
MOUVEMENT_PAR_DEFAUT = 5


class Hex:
    """Un hexagone de la carte, en coordonnées cubiques `q + r + s = 0`.

    S'initialise avec les trois coordonnées, avec `q` et `r` seuls — `s` s'en déduit —, ou sans
    rien du tout : `Hex()` est un hexagone vide, sans position.
    """

    __slots__ = ("q", "r", "s")

    def __init__(self, q=None, r=None, s=None):
        if q is None and r is None and s is None:
            self.q = self.r = self.s = None
            return
        if q is None or r is None:
            raise ValueError("un hexagone se donne par q et r, ou par q, r et s, ou vide")
        if s is None:
            s = -q - r
        if q + r + s != 0:
            raise ValueError(f"coordonnées cubiques incohérentes : {q} + {r} + {s} ≠ 0")
        self.q, self.r, self.s = q, r, s

    @classmethod
    def depuis_cle(cls, cle):
        """Construit un hexagone depuis une clé de `carte.json`, de la forme « q,r,s »."""
        return cls(*(int(valeur) for valeur in cle.split(",")))

    @property
    def est_vide(self):
        return self.q is None

    @property
    def cle(self):
        """La clé « q,r,s » sous laquelle la carte connaît cet hexagone."""
        self._exiger_une_position()
        return f"{self.q},{self.r},{self.s}"

    @property
    def est_sur_la_carte(self):
        return not self.est_vide and self.cle in CARTE

    @property
    def elements(self):
        """Tout ce que porte l'hexagone, le terrain principal en tête ; vide s'il est hors carte."""
        self._exiger_une_position()
        return CARTE.get(self.cle, ())

    @property
    def terrain(self):
        """Le terrain principal de l'hexagone, ou `None` s'il est hors carte."""
        elements = self.elements
        return elements[0] if elements else None

    def voisins(self):
        """Les six hexagones adjacents, réduits à ceux qui sont sur la carte."""
        self._exiger_une_position()
        voisins = (Hex(self.q + dq, self.r + dr, self.s + ds) for dq, dr, ds in DIRECTIONS)
        return [voisin for voisin in voisins if voisin.est_sur_la_carte]

    def cout_depuis(self, depart):
        """Points de mouvement pour entrer sur cet hexagone depuis `depart`.

        Rend `None` si le passage est interdit à une unité terrestre.
        """
        if not self.est_sur_la_carte or not depart.est_sur_la_carte:
            return None

        elements, terrain = self.elements, self.terrain
        if terrain in INFRANCHISSABLES:
            return None
        if terrain == "montagne" and depart.terrain not in ACCES_A_LA_MONTAGNE:
            if not COUTS_DES_VOIES.keys() & set(elements):
                return None

        # Suivre une voie ne vaut que si on s'y trouve déjà : une unité qui rejoint la route paie
        # d'abord le terrain qui l'en sépare.
        elements_du_depart = set(depart.elements)
        for voie, cout in COUTS_DES_VOIES.items():
            if voie in elements and voie in elements_du_depart:
                return cout

        return COUTS.get(terrain, COUT_ORDINAIRE)

    def deplacements(self, mouvement=MOUVEMENT_PAR_DEFAUT):
        """Les hexagones atteignables avec `mouvement` points, cet hexagone excepté.

        Parcours de Dijkstra sur les coûts de terrain. Les coûts sont des fractions exactes :
        une route vaut un tiers de point, et cinq tiers ne doivent pas dériver. Une unité posée
        sur un terrain qu'elle ne peut pas occuper — un lac, une rivière, la faille — ne va nulle
        part.
        """
        self._exiger_une_position()
        if not self.est_sur_la_carte or self.terrain in INHABITABLES:
            return []

        budget = Fraction(mouvement)
        depenses = {self.cle: Fraction(0)}
        attente = [(Fraction(0), self.q, self.r, self)]
        while attente:
            depense, _, _, hexagone = heapq.heappop(attente)
            if depense > depenses[hexagone.cle]:
                continue
            for voisin in hexagone.voisins():
                cout = voisin.cout_depuis(hexagone)
                if cout is None:
                    continue
                total = depense + cout
                if total <= budget and total < depenses.get(voisin.cle, budget + 1):
                    depenses[voisin.cle] = total
                    heapq.heappush(attente, (total, voisin.q, voisin.r, voisin))

        del depenses[self.cle]
        return [Hex.depuis_cle(cle) for cle in depenses]

    def en_dict(self):
        """Rend l'hexagone sous une forme directement convertible en JSON pour le navigateur."""
        if self.est_vide:
            return {"q": None, "r": None, "s": None, "terrain": None}
        return {"q": self.q, "r": self.r, "s": self.s, "terrain": self.terrain}

    def _exiger_une_position(self):
        if self.est_vide:
            raise ValueError("cet hexagone est vide : il n'a pas de position sur la carte")

    def __eq__(self, autre):
        return isinstance(autre, Hex) and (self.q, self.r, self.s) == (autre.q, autre.r, autre.s)

    def __hash__(self):
        return hash((self.q, self.r, self.s))

    def __repr__(self):
        if self.est_vide:
            return "Hex()"
        return f"Hex({self.q}, {self.r}, {self.s})"
